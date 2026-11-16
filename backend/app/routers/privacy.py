"""Personal data: GET /privacy/tags, PUT /privacy/tags/{entity}/{column}, POST /privacy/suggest."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app import privacy as P

router = APIRouter()


class TagBody(BaseModel):
    category: str | None = None          # None = not personal data


@router.get("/tags")
async def tags():
    return await run_in_threadpool(P.summary)


@router.put("/tags/{entity}/{column}")
async def set_tag(entity: str, column: str, body: TagBody):
    try:
        return await run_in_threadpool(P.set_tag, entity, column, body.category)
    except KeyError as e:
        raise HTTPException(404, f"Unknown field {e}") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/suggest")
async def suggest():
    await run_in_threadpool(P.resuggest)
    return await run_in_threadpool(P.summary)
