"""Bulk upload API tests against a mocked S3. Run: cd backend && python -m pytest tests"""
import time

import boto3
import pytest
import requests
from fastapi.testclient import TestClient
from moto import mock_aws

from app.main import app
from app.routers import uploads

MiB = 1024 * 1024
BUCKET = "test-uploads"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("STORAGE_BUCKET", BUCKET)
    monkeypatch.setenv("AWS_REGION", "eu-west-2")
    monkeypatch.setenv("UPLOAD_TOKEN_SECRET", "x" * 48)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    with mock_aws():
        uploads.s3.cache_clear()
        boto3.client("s3", region_name="eu-west-2").create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})
        yield TestClient(app)
        uploads.s3.cache_clear()


def upload(client, project, name, data: bytes):
    r = client.post(f"/projects/{project}/uploads", json={"files": [{"name": name, "size": len(data)}]})
    assert r.status_code == 200, r.text
    f = r.json()["accepted"][0]
    numbers = list(range(1, f["part_count"] + 1))
    urls = client.post(f"/projects/{project}/uploads/parts", json={"token": f["token"], "part_numbers": numbers}).json()["urls"]
    parts = []
    for n in numbers:
        chunk = data[(n - 1) * f["part_size"]: n * f["part_size"]]
        put = requests.put(urls[str(n)], data=chunk)
        assert put.status_code == 200
        parts.append({"part_number": n, "etag": put.headers["ETag"]})
    return f, client.post(f"/projects/{project}/uploads/complete", json={"token": f["token"], "parts": parts})


def stored_keys():
    return [o["Key"] for o in boto3.client("s3", region_name="eu-west-2").list_objects_v2(Bucket=BUCKET).get("Contents", [])]


def test_multipart_upload_round_trip(client):
    data = b"CandidateID,Forename\n" + b"C-1,Amara\n" * (17 * MiB // 10)
    f, r = upload(client, "proj-1", "CANDIDATE.csv", data)
    assert f["part_count"] == 3
    assert r.status_code == 200 and r.json() == {"name": "CANDIDATE.csv", "size": len(data), "status": "received"}
    key = stored_keys()[0]
    assert key.startswith("uploads/dev-org/proj-1/") and key.endswith("/CANDIDATE.csv")
    body = boto3.client("s3", region_name="eu-west-2").get_object(Bucket=BUCKET, Key=key)["Body"].read()
    assert body == data


def test_many_files_in_one_request(client):
    files = [{"name": f"TABLE_{i}.csv", "size": 100} for i in range(250)]
    r = client.post("/projects/p/uploads", json={"files": files})
    assert len(r.json()["accepted"]) == 250


def test_bad_files_rejected_individually(client):
    r = client.post("/projects/p/uploads", json={"files": [
        {"name": "ok.csv", "size": 10},
        {"name": "malware.exe", "size": 10},
        {"name": "report.xlsx", "size": 10},
        {"name": "empty.csv", "size": 0},
        {"name": "huge.csv", "size": 6 * 1024 * MiB},
    ]}).json()
    assert [a["name"] for a in r["accepted"]] == ["ok.csv"]
    assert {x["client_index"] for x in r["rejected"]} == {1, 2, 3, 4}


@pytest.mark.parametrize("name,expected", [
    ("../../etc/passwd.csv", "passwd.csv"),
    ("..\\..\\windows\\x.csv", "x.csv"),
    ("folder/sub/CANDIDATE.csv", "CANDIDATE.csv"),
    (".hidden.csv", "hidden.csv"),
    ("na<me>|\"*?.csv", "na_me_____.csv"),
    ("Łódź.csv", "__d_.csv"),
])
def test_names_are_sanitised(name, expected):
    assert uploads.safe_file_name(name) == expected


def test_tampered_token_rejected(client):
    f = client.post("/projects/p/uploads", json={"files": [{"name": "a.csv", "size": 10}]}).json()["accepted"][0]
    body, sig = f["token"].split(".")
    forged = uploads._b64(uploads._unb64(body).replace(b'"pid":"p"', b'"pid":"q"')) + "." + sig
    for token in (forged, body + ".AAAA", "garbage", f["token"] + "x"):
        r = client.post("/projects/p/uploads/parts", json={"token": token, "part_numbers": [1]})
        assert r.status_code == 403


def test_token_cannot_be_used_on_another_project(client):
    f = client.post("/projects/agency-a/uploads", json={"files": [{"name": "a.csv", "size": 10}]}).json()["accepted"][0]
    r = client.post("/projects/agency-b/uploads/parts", json={"token": f["token"], "part_numbers": [1]})
    assert r.status_code == 403


def test_expired_token_rejected(client, monkeypatch):
    f = client.post("/projects/p/uploads", json={"files": [{"name": "a.csv", "size": 10}]}).json()["accepted"][0]
    monkeypatch.setattr(time, "time", lambda: 10**12)
    assert client.post("/projects/p/uploads/parts", json={"token": f["token"], "part_numbers": [1]}).status_code == 403


def test_part_numbers_out_of_range(client):
    f = client.post("/projects/p/uploads", json={"files": [{"name": "a.csv", "size": 10}]}).json()["accepted"][0]
    assert client.post("/projects/p/uploads/parts", json={"token": f["token"], "part_numbers": [2]}).status_code == 422


def test_size_mismatch_discards_file(client):
    r = client.post("/projects/p/uploads", json={"files": [{"name": "a.csv", "size": 10}]})
    f = r.json()["accepted"][0]
    url = client.post("/projects/p/uploads/parts", json={"token": f["token"], "part_numbers": [1]}).json()["urls"]["1"]
    put = requests.put(url, data=b"much more data than was declared")
    r = client.post("/projects/p/uploads/complete", json={"token": f["token"], "parts": [{"part_number": 1, "etag": put.headers["ETag"]}]})
    assert r.status_code == 422
    assert stored_keys() == []


def test_abort(client):
    f = client.post("/projects/p/uploads", json={"files": [{"name": "a.csv", "size": 10}]}).json()["accepted"][0]
    assert client.post("/projects/p/uploads/abort", json={"token": f["token"]}).status_code == 204


def test_refused_outside_development(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    r = client.post("/projects/p/uploads", json={"files": [{"name": "a.csv", "size": 10}]})
    assert r.status_code == 501


def test_bad_project_id(client):
    assert client.post("/projects/..%2Fx/uploads", json={"files": [{"name": "a.csv", "size": 10}]}).status_code == 404


def test_missing_secret_fails_closed(client, monkeypatch):
    monkeypatch.setenv("UPLOAD_TOKEN_SECRET", "short")
    assert client.post("/projects/p/uploads", json={"files": [{"name": "a.csv", "size": 10}]}).status_code == 503


def test_part_size_respects_s3_limits():
    assert uploads.part_size_for(1) == 8 * MiB
    big = 5 * 1024**4  # 5 TiB
    assert big / uploads.part_size_for(big) <= 10_000
