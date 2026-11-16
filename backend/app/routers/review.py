"""Review by records: GET /review/{entity}, GET /review/{entity}/{id}, GET /review/{entity}/{id}/source/{column}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app import review as R

router = APIRouter()


def _err(e: Exception) -> HTTPException:
    if isinstance(e, KeyError):
        return HTTPException(404, f"Not found: {e}")
    return HTTPException(503, f"{e}")


@router.get("/{entity}")
async def records(entity: str, q: str | None = None, flagged: bool = False):
    try:
        return await run_in_threadpool(R.records, entity, q, flagged)
    except Exception as e:
        raise _err(e) from e


@router.get("/{entity}/{rid}")
async def record(entity: str, rid: str):
    try:
        return await run_in_threadpool(R.record, entity, rid)
    except Exception as e:
        raise _err(e) from e


@router.get("/{entity}/{rid}/source/{column}")
async def source(entity: str, rid: str, column: str):
    try:
        return await run_in_threadpool(R.source, entity, rid, column)
    except Exception as e:
        raise _err(e) from e
