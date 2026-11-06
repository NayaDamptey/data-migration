"""Local source uploads (no object storage needed): for running Migryr on one machine.

  POST   /projects/{id}/files          multipart upload of one or more .csv/.tsv/.txt/.zip files
  GET    /projects/{id}/files          the project's source files with rows and columns
  DELETE /projects/{id}/files/{name}   remove one file

Files land in storage/projects/<id>/source/. Zips are unpacked (CSV-like members
only, flattened, names made safe). File names are reduced to a safe last path
segment, so a client can never write outside the project folder. Uploading a file
invalidates the project's cached data-quality report.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app import engine_bridge as eb
from app.auth import Caller, require_project_access
from app.routers.uploads import ALLOWED_EXTENSIONS, safe_file_name

router = APIRouter()
CHUNK = 1024 * 1024


def max_bytes() -> int:
    return int(os.getenv("MAX_LOCAL_UPLOAD_BYTES", str(2 * 1024 ** 3)))   # 2 GiB per file


def _describe(path: Path) -> dict:
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(64 * 1024)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample.split("\n", 1)[0], delimiters=",;\t|")
            delim = dialect.delimiter
        except csv.Error:
            delim = ","
        reader = csv.reader(f, delimiter=delim)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    return {"name": path.name, "size": path.stat().st_size, "rows": rows, "columns": header, "delimiter": delim,
            "table": path.stem}


def _save_stream(src, dest: Path, limit: int) -> int:
    written = 0
    with open(dest, "wb") as out:
        while chunk := src.read(CHUNK):
            written += len(chunk)
            if written > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{dest.name} is larger than {limit // 1024 ** 2} MB")
            out.write(chunk)
    return written


@router.post("/projects/{project_id}/files")
def upload(project_id: str, files: list[UploadFile], caller: Caller = Depends(require_project_access)) -> dict:
    folder = eb.upload_dir(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    saved, rejected = [], []
    for f in files:
        name = safe_file_name(f.filename or "file")
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            rejected.append({"name": name, "reason": "Only .csv, .tsv, .txt and .zip files can be uploaded."})
            continue
        if ext == ".zip":
            tmp = folder / f".upload-{name}"
            _save_stream(f.file, tmp, max_bytes())
            try:
                with zipfile.ZipFile(tmp) as z:
                    for member in z.infolist():
                        inner = safe_file_name(member.filename)
                        if member.is_dir() or os.path.splitext(inner)[1].lower() not in (".csv", ".tsv", ".txt"):
                            continue
                        if member.file_size > max_bytes():
                            rejected.append({"name": inner, "reason": "File inside the zip is too large."})
                            continue
                        dest = folder / (os.path.splitext(inner)[0] + ".csv")
                        with z.open(member) as src:
                            _save_stream(src, dest, max_bytes())
                        saved.append(_describe(dest))
            except zipfile.BadZipFile:
                rejected.append({"name": name, "reason": "This isn't a valid zip file."})
            finally:
                tmp.unlink(missing_ok=True)
        else:
            dest = folder / (os.path.splitext(name)[0] + ".csv")
            _save_stream(f.file, dest, max_bytes())
            saved.append(_describe(dest))
    eb.invalidate(f"upload:{project_id}")
    return {"saved": saved, "rejected": rejected}


@router.get("/projects/{project_id}/files")
def list_files(project_id: str, caller: Caller = Depends(require_project_access)) -> list[dict]:
    folder = eb.upload_dir(project_id)
    return [_describe(p) for p in sorted(folder.glob("*.csv"))] if folder.exists() else []


@router.delete("/projects/{project_id}/files/{name}", status_code=204)
def delete_file(project_id: str, name: str, caller: Caller = Depends(require_project_access)):
    path = eb.upload_dir(project_id) / safe_file_name(name)
    if path.suffix.lower() != ".csv" or not path.is_file():
        raise HTTPException(404, "No such file")
    path.unlink()
    eb.invalidate(f"upload:{project_id}")


@router.delete("/projects/{project_id}/files", status_code=204)
def delete_all(project_id: str, caller: Caller = Depends(require_project_access)):
    shutil.rmtree(eb.upload_dir(project_id), ignore_errors=True)
    eb.invalidate(f"upload:{project_id}")
