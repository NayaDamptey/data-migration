"""Version review (Dolt): GET /versions, GET /versions/{commit}/diff/{table}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app import versions as V

router = APIRouter()


@router.get("")
async def versions(limit: int = 50):
    try:
        return await run_in_threadpool(V.log, limit)
    except Exception as e:
        raise HTTPException(503, f"Dolt: {e}") from e


@router.get("/{commit}/diff/{table}")
async def diff(commit: str, table: str):
    try:
        return await run_in_threadpool(V.diff, commit, table)
    except KeyError:
        raise HTTPException(404, f"Unknown version {commit!r}") from None
    except Exception as e:
        raise HTTPException(503, f"Dolt: {e}") from e
