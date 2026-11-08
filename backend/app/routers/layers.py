"""Middle tier and target layers: GET /layers/{layer}, POST /layers/{layer}/run,
GET /layers/{layer}/{entity}/rows, PUT /layers/{layer}/{entity}/fields."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app import layers as L

router = APIRouter()


class FieldPatch(BaseModel):
    insert: int = 0
    column: str
    expression: str | None = None


def _err(e: Exception):
    if isinstance(e, KeyError):
        return HTTPException(404, f"Unknown {e}")
    if isinstance(e, ValueError):
        return HTTPException(400, str(e))
    return HTTPException(503, f"SQL Server: {e}")


@router.get("/{layer}")
async def detail(layer: str):
    try:
        return await run_in_threadpool(L.detail, layer)
    except Exception as e:
        raise _err(e) from e


@router.get("/target/rejects")
async def rejects():
    try:
        return await run_in_threadpool(L.rejects)
    except Exception as e:
        raise _err(e) from e


@router.get("/{layer}/summary")
async def summary(layer: str):
    try:
        return await run_in_threadpool(L.summary, layer)
    except Exception as e:
        raise _err(e) from e


@router.post("/{layer}/run")
async def run(layer: str):
    try:
        return await run_in_threadpool(L.run, layer)
    except Exception as e:
        raise _err(e) from e


@router.get("/{layer}/{entity}/rows")
async def rows(layer: str, entity: str, limit: int = Query(100, ge=1, le=2000), q: str | None = None):
    try:
        return await run_in_threadpool(L.rows, layer, entity, limit, q)
    except StopIteration:
        raise HTTPException(404, f"Unknown entity {entity!r}") from None
    except Exception as e:
        raise _err(e) from e


@router.put("/{layer}/{entity}/fields")
async def set_field(layer: str, entity: str, body: FieldPatch):
    try:
        return await run_in_threadpool(L.set_field, layer, entity, body.insert, body.column, body.expression)
    except StopIteration:
        raise HTTPException(404, f"Unknown entity {entity!r}") from None
    except Exception as e:
        raise _err(e) from e
