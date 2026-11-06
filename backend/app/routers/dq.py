"""Data quality dashboard: the engine's rules run against the legacy DB, the clean
baseline, or a project's uploaded CSVs.

  GET /dq/sources                       which sources can be checked right now
  GET /dq/report?source=legacy          score, totals, issues by category / table / rule
  GET /dq/rules/{rule_id}?source=...    every violation of one rule + the offending records
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app import engine_bridge as eb
from app.auth import PROJECT_ID_RE

router = APIRouter()


def _check_source(source: str) -> str:
    if source in ("legacy", "baseline"):
        return source
    if source.startswith("upload:") and PROJECT_ID_RE.fullmatch(source.split(":", 1)[1]):
        return source
    raise HTTPException(400, "source must be legacy, baseline or upload:<project_id>")


@router.get("/sources")
async def sources(project_id: str | None = None) -> list[dict]:
    out = [{"id": "legacy", "label": "Legacy database", "detail": "RecruitCRM_Legacy on SQL Server",
            "available": await run_in_threadpool(eb.legacy_available)},
           {"id": "baseline", "label": "Clean baseline", "detail": "Engine sample data with no planted problems", "available": True}]
    if project_id and PROJECT_ID_RE.fullmatch(project_id):
        files = list(eb.upload_dir(project_id).glob("*.csv")) if eb.upload_dir(project_id).exists() else []
        out.append({"id": f"upload:{project_id}", "label": "Uploaded files",
                    "detail": f"{len(files)} CSV file{'s' if len(files) != 1 else ''} uploaded", "available": bool(files)})
    return out


@router.get("/report")
async def report(source: str = Query("legacy"), refresh: bool = False) -> dict:
    src = _check_source(source)
    try:
        return await run_in_threadpool(eb.report, src, refresh)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from None
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(503, f"Could not check {src}: {e}") from None


class Decision(BaseModel):
    source: str = "legacy"
    key: str = Field(max_length=200, pattern=r"^[a-z_]+:\d+:\d+$")
    decision: Literal["merge", "not_duplicate", "undecided"]
    keep: Literal["a", "b"] | None = None             # merge: which record stays
    fields: dict[str, Literal["a", "b"]] = {}         # merge: per column, whose value to keep


@router.get("/duplicates")
async def duplicates(source: str = Query("legacy"), entity: str | None = None) -> dict:
    """Suspected duplicate pairs, side by side, with what is linked to each record and any decision."""
    src = _check_source(source)
    return await run_in_threadpool(eb.duplicate_pairs, src, entity)


@router.post("/duplicates/decision")
async def decide(body: Decision) -> dict:
    """Merge a pair (keep one record, choose field values) or mark it as not a duplicate. 'undecided' undoes it."""
    src = _check_source(body.source)
    try:
        rec = await run_in_threadpool(eb.decide, src, body.key, body.decision, body.keep, body.fields)
    except KeyError:
        raise HTTPException(404, "No such duplicate pair") from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return {"key": body.key, "decision": rec}


@router.get("/rules/{rule_id}")
async def rule(rule_id: str, source: str = Query("legacy"), limit: int = Query(200, ge=1, le=2000)) -> dict:
    src = _check_source(source)
    try:
        return await run_in_threadpool(eb.rule_rows, src, rule_id, limit)
    except KeyError:
        raise HTTPException(404, f"No rule {rule_id}") from None
