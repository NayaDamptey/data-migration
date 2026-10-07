"""Propose a source → canonical mapping spec from a profile (outline).

Flow (see docs/ai-mapping.md):
  1. load profile.json + canonical/model.yaml (+ past approved mappings)
  2. classify tables → canonical entities            (LLM, JSON out)
  3. per canonical field, shortlist candidate columns (names, patterns, history)
  4. pick column + transform per field               (LLM, JSON out)
  5. write mappings/<project>.yaml with confidence, status and questions

Only steps 1, 3 and 5 are filled in. Steps 2 and 4 are LLM calls to wire up.
Requires: pip install pyyaml anthropic
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

import yaml

REVIEW_THRESHOLD = 0.85

# Which detected profile patterns fit which canonical field types
TYPE_PATTERNS = {
    "email": {"email"},
    "phone": {"uk_phone"},
    "postcode": {"uk_postcode"},
    "url": {"url"},
    "date": {"date_dmy", "date_iso", "date_mixed_formats"},
    "datetime": {"date_dmy", "date_iso", "date_mixed_formats"},
    "money": {"money", "integer"},
    "boolean": {"boolean"},
}

# Common aliases; grows over time from approved mappings
ALIASES = {
    "first_name": ["forename", "firstname", "given_name"],
    "last_name": ["surname", "lastname", "family_name"],
    "mobile": ["mobiletel", "mobile_phone", "cell"],
    "current_job_title": ["currentposition", "job_title", "position"],
    "company_name": ["name", "companyname", "client_name"],
    "owner_user_id": ["consultantid", "ownerid", "userid"],
    "created_at": ["dateregistered", "createdon", "date_added"],
}


def name_score(field: str, column: str) -> float:
    col = column.lower().replace("_", "")
    options = [field.replace("_", "")] + ALIASES.get(field, [])
    return max(SequenceMatcher(None, o.replace("_", ""), col).ratio() for o in options)


def shortlist(field: str, spec: dict, table: dict, top_n: int = 5) -> list[dict]:
    """Rank a table's columns as candidates for one canonical field (step 3)."""
    wanted = TYPE_PATTERNS.get(spec["type"], set())
    scored = []
    for col in table["columns"]:
        n = name_score(field, col["column"])
        p = 1.0 if wanted and wanted & set(col["patterns"]) else (0.5 if not wanted else 0.0)
        scored.append({"column": col["column"], "score": round(0.6 * n + 0.4 * p, 3),
                       "patterns": col["patterns"], "samples": col["samples"][:5]})
    return sorted(scored, key=lambda c: c["score"], reverse=True)[:top_n]


def classify_tables(profile: dict, model: dict) -> dict:
    """Step 2: LLM call. Returns {table: {entity, confidence, reason}}.

    Prompt with: each table's name, row count, columns + patterns, the foreign
    keys, and each canonical entity's description. Ask for strict JSON.
    """
    raise NotImplementedError("Wire up the Claude API here")


def choose_fields(entity: str, candidates: dict) -> dict:
    """Step 4: LLM call. Given the shortlist per field, return
    {field: {from, transform, confidence, reason}}, using ONLY the transforms
    listed in mappings/README.md, plus any questions for the agency."""
    raise NotImplementedError("Wire up the Claude API here")


def status_for(confidence: float) -> str:
    return "proposed" if confidence >= REVIEW_THRESHOLD else "needs_review"


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parents[2]
    profile = json.loads(Path(sys.argv[1]).read_text())
    model = yaml.safe_load((root / "canonical/model.yaml").read_text())
    # Demo of step 3 without the LLM: shortlist for candidates ← CANDIDATE
    table = profile["tables"].get("CANDIDATE")
    if table:
        for field, spec in model["entities"]["candidates"]["fields"].items():
            best = shortlist(field, spec, table, top_n=1)[0]
            print(f"{field:18} ← {best['column']:16} score {best['score']}")
