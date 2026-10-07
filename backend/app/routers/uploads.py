"""Bulk source uploads: many files, straight to object storage, in resumable parts.

Flow (the browser does this per file, a few files at a time):
  1. POST /projects/{id}/uploads           list the files → a signed token per accepted file
  2. POST /projects/{id}/uploads/parts     token + part numbers → short-lived PUT URLs
  3. PUT each part to its URL               (retry any part that fails; keep the ETag header)
  4. POST /projects/{id}/uploads/complete  token + [{part_number, etag}] → file is stored
  POST /projects/{id}/uploads/abort         token → discard a cancelled upload

File bytes never pass through this API. The token carries the project, storage
key, multipart upload id and declared size, signed with UPLOAD_TOKEN_SECRET, so
a client can't point an upload at another project or key. On completion the
stored size must equal the declared size, or the object is deleted.

The bucket needs a CORS rule allowing PUT from the frontend origin and exposing
the ETag header.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import re
import time
import uuid
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import Caller, require_project_access

router = APIRouter()

MiB = 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".txt", ".zip"}
MIN_PART = 8 * MiB          # S3 minimum is 5 MiB (except the last part)
MAX_PARTS = 10_000          # S3 limit
MAX_FILES_PER_REQUEST = 1000
MAX_URLS_PER_REQUEST = 100
URL_TTL_SECONDS = 15 * 60
TOKEN_TTL_SECONDS = 24 * 3600
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._ -]")


def max_file_bytes() -> int:
    return int(os.getenv("MAX_UPLOAD_FILE_BYTES", str(5 * 1024 * MiB)))  # 5 GiB


def bucket() -> str:
    name = os.getenv("STORAGE_BUCKET")
    if not name:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Storage is not configured")
    return name


@lru_cache
def s3():
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "eu-west-2"))


# ---- signed upload tokens ----

def _secret() -> bytes:
    secret = os.getenv("UPLOAD_TOKEN_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "UPLOAD_TOKEN_SECRET must be set (32+ characters)")
    return secret.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_token(payload: dict[str, Any]) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_token(token: str, project_id: str) -> dict[str, Any]:
    invalid = HTTPException(status.HTTP_403_FORBIDDEN, "Invalid upload token")
    try:
        body, sig = token.split(".")
        expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise invalid
        payload = json.loads(_unb64(body))
    except HTTPException:
        raise
    except Exception:
        raise invalid from None
    if payload.get("v") != 1 or payload.get("pid") != project_id:
        raise invalid
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Upload token expired; start the upload again")
    return payload


# ---- helpers ----

def safe_file_name(name: str) -> str:
    """Last path segment only, restricted characters. Never trust the client's name in a key."""
    base = re.split(r"[\\/]", name)[-1].strip().lstrip(".")
    base = SAFE_NAME_RE.sub("_", base)[:120]
    return base or "file"


def part_size_for(size: int) -> int:
    per_part = math.ceil(size / MAX_PARTS)
    return max(MIN_PART, math.ceil(per_part / MiB) * MiB)


# ---- schemas ----

class FileIn(BaseModel):
    name: str = Field(min_length=1, max_length=1024)
    size: int = Field(ge=0)
    relative_path: str | None = Field(default=None, max_length=2048)  # from folder uploads; display only


class InitRequest(BaseModel):
    files: list[FileIn] = Field(min_length=1, max_length=MAX_FILES_PER_REQUEST)


class AcceptedFile(BaseModel):
    client_index: int
    name: str
    size: int
    part_size: int
    part_count: int
    token: str


class RejectedFile(BaseModel):
    client_index: int
    name: str
    reason: str


class InitResponse(BaseModel):
    batch_id: str
    accepted: list[AcceptedFile]
    rejected: list[RejectedFile]


class PartsRequest(BaseModel):
    token: str = Field(max_length=4096)
    part_numbers: list[int] = Field(min_length=1, max_length=MAX_URLS_PER_REQUEST)


class PartsResponse(BaseModel):
    urls: dict[int, str]
    expires_in: int


class CompletedPart(BaseModel):
    part_number: int = Field(ge=1, le=MAX_PARTS)
    etag: str = Field(min_length=1, max_length=200)


class CompleteRequest(BaseModel):
    token: str = Field(max_length=4096)
    parts: list[CompletedPart] = Field(min_length=1, max_length=MAX_PARTS)


class CompleteResponse(BaseModel):
    name: str
    size: int
    status: str


class AbortRequest(BaseModel):
    token: str = Field(max_length=4096)


# ---- routes ----

@router.post("/projects/{project_id}/uploads", response_model=InitResponse)
def start_uploads(project_id: str, body: InitRequest, caller: Caller = Depends(require_project_access)):
    batch_id = uuid.uuid4().hex
    accepted: list[AcceptedFile] = []
    rejected: list[RejectedFile] = []
    limit = max_file_bytes()
    sse = os.getenv("STORAGE_SSE", "AES256")  # set to aws:kms in production

    for i, f in enumerate(body.files):
        name = safe_file_name(f.name)
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            rejected.append(RejectedFile(client_index=i, name=name, reason="Only .csv, .tsv, .txt and .zip files can be uploaded"))
            continue
        if f.size == 0:
            rejected.append(RejectedFile(client_index=i, name=name, reason="File is empty"))
            continue
        if f.size > limit:
            rejected.append(RejectedFile(client_index=i, name=name, reason=f"File is larger than {limit // (1024 * MiB)} GB"))
            continue

        key = f"uploads/{caller.organisation_id}/{project_id}/{batch_id}/{uuid.uuid4().hex}/{name}"
        mpu = s3().create_multipart_upload(
            Bucket=bucket(), Key=key, ServerSideEncryption=sse,
            ContentType="application/octet-stream",  # never trust the browser's type
            Metadata={"project": project_id, "uploaded-by": caller.user_id},
        )
        part_size = part_size_for(f.size)
        token = sign_token({
            "v": 1, "pid": project_id, "key": key, "uid": mpu["UploadId"],
            "size": f.size, "name": name, "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        })
        accepted.append(AcceptedFile(client_index=i, name=name, size=f.size, part_size=part_size, part_count=math.ceil(f.size / part_size), token=token))

    return InitResponse(batch_id=batch_id, accepted=accepted, rejected=rejected)


@router.post("/projects/{project_id}/uploads/parts", response_model=PartsResponse)
def part_urls(project_id: str, body: PartsRequest, caller: Caller = Depends(require_project_access)):
    t = read_token(body.token, project_id)
    part_count = math.ceil(t["size"] / part_size_for(t["size"]))
    if any(not 1 <= n <= part_count for n in body.part_numbers):
        raise HTTPException(422, f"Part numbers must be 1–{part_count}")
    urls = {
        n: s3().generate_presigned_url(
            "upload_part",
            Params={"Bucket": bucket(), "Key": t["key"], "UploadId": t["uid"], "PartNumber": n},
            ExpiresIn=URL_TTL_SECONDS,
        )
        for n in sorted(set(body.part_numbers))
    }
    return PartsResponse(urls=urls, expires_in=URL_TTL_SECONDS)


@router.post("/projects/{project_id}/uploads/complete", response_model=CompleteResponse)
def complete_upload(project_id: str, body: CompleteRequest, caller: Caller = Depends(require_project_access)):
    t = read_token(body.token, project_id)
    part_count = math.ceil(t["size"] / part_size_for(t["size"]))
    numbers = [p.part_number for p in body.parts]
    if sorted(numbers) != list(range(1, part_count + 1)):
        raise HTTPException(422, f"Expected parts 1–{part_count}, each once")
    parts = [{"PartNumber": p.part_number, "ETag": p.etag} for p in sorted(body.parts, key=lambda p: p.part_number)]
    try:
        s3().complete_multipart_upload(Bucket=bucket(), Key=t["key"], UploadId=t["uid"], MultipartUpload={"Parts": parts})
    except ClientError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Upload could not be completed: {e.response['Error'].get('Code', 'error')}") from None

    stored = s3().head_object(Bucket=bucket(), Key=t["key"])["ContentLength"]
    if stored != t["size"]:
        s3().delete_object(Bucket=bucket(), Key=t["key"])
        raise HTTPException(422, "Uploaded size doesn't match the declared size; file discarded")

    # Next: record the file against the project and queue scanning + ingest (worker.ingest).
    return CompleteResponse(name=t["name"], size=stored, status="received")


@router.post("/projects/{project_id}/uploads/abort", status_code=status.HTTP_204_NO_CONTENT)
def abort_upload(project_id: str, body: AbortRequest, caller: Caller = Depends(require_project_access)):
    t = read_token(body.token, project_id)
    try:
        s3().abort_multipart_upload(Bucket=bucket(), Key=t["key"], UploadId=t["uid"])
    except ClientError:
        pass  # already completed or aborted
