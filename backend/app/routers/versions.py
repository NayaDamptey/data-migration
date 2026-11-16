"""Version review (runs): GET /versions."""

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
        raise HTTPException(503, f"{e}") from e
