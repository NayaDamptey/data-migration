"""
validation/duplicates.py

Suspected duplicates as reviewable PAIRS, and the reviewer's decisions.

The duplicate rules (dup.person, dup.associate, dup.account, dup.job, dup.timesheet_line) each return the
later record of a pair with "... of <first id>". A pair can be decided as
  merge          keep one record, optionally take some field values from the other; the migration loads
                 one record and re-links everything attached to the other one to it
  not_duplicate  they are different records; both are migrated and the pair is never flagged again
Decisions live in mapping/merge_decisions.json (per data source), so the SQL generator can apply merges.
The legacy source itself is never changed.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from validation.baseline_rules import PK, RULES, SCHEMA

ROOT = Path(__file__).resolve().parent.parent
DECISIONS_FILE = ROOT / "mapping" / "merge_decisions.json"
_lock = threading.Lock()


@dataclass(frozen=True)
class Entity:
    key: str
    label: str
    table: str
    rule_id: str
    poly_type: str | None        # ObjectType used by Notes / Documents / TagEntity / Log for this table


ENTITIES = [
    Entity("person", "People", "Person", "dup.person", "Person"),
    Entity("contact", "Contacts", "Associates", "dup.associate", "Associate"),
    Entity("company", "Companies", "Accounts", "dup.account", "Account"),
    Entity("job", "Jobs", "Req", "dup.job", "Req"),
    Entity("timesheet_line", "Timesheet lines", "TimesheetItems", "dup.timesheet_line", None),
]
BY_RULE = {e.rule_id: e for e in ENTITIES}
BY_KEY = {e.key: e for e in ENTITIES}
SPLIT_RULE = "dup.account.split_history"
DUP_RULE_IDS = set(BY_RULE) | {SPLIT_RULE}

_RULES = {r.id: r for r in RULES}
_POLY = [("Notes", "ObjectType", "ObjectId"), ("Documents", "ObjectType", "Doc_AssocID"),
         ("TagEntity", "EntityType", "EntityID"), ("Log", "Entity_Type", "Entity_ID")]


def _partner(detail: str) -> str | None:
    m = re.findall(r"\d+", detail or "")
    return m[-1] if m else None


def pair_key(entity: str, x: str, y: str) -> str:
    a, b = sorted([str(x), str(y)], key=lambda v: (len(v), v))
    return f"{entity}:{a}:{b}"


def pairs_from_results(results: dict[str, list]) -> list[dict]:
    """Pairs from failing duplicate-rule rows: (pk of later record, '... of <first id>')."""
    out, seen = [], set()
    for rule_id, ent in BY_RULE.items():
        for row in results.get(rule_id, []):
            later, first = str(row[0]), _partner(str(row[1]) if len(row) > 1 else "")
            if not first or first == later:
                continue
            k = pair_key(ent.key, first, later)
            if k in seen:
                continue
            seen.add(k)
            a, b = k.split(":")[1:]
            out.append({"key": k, "entity": ent.key, "label": ent.label, "table": ent.table, "a": a, "b": b,
                        "reason": _RULES[rule_id].description})
    return out


# ── decisions ──────────────────────────────────────────────────────────────────

def _load_all() -> dict:
    if DECISIONS_FILE.exists():
        return json.loads(DECISIONS_FILE.read_text(encoding="utf-8"))
    return {"version": 1, "sources": {}}


def load_decisions(source: str) -> dict[str, dict]:
    return _load_all()["sources"].get(source, {})


def save_decision(source: str, key: str, decision: str, keep: str | None = None,
                  fields: dict[str, str] | None = None, by: str = "reviewer") -> dict | None:
    """decision: merge | not_duplicate | undecided (removes the decision)."""
    entity, a, b = key.split(":")
    if entity not in BY_KEY:
        raise ValueError(f"unknown entity {entity}")
    if decision not in ("merge", "not_duplicate", "undecided"):
        raise ValueError("decision must be merge, not_duplicate or undecided")
    if decision == "merge" and keep not in ("a", "b"):
        raise ValueError("merge needs keep = 'a' or 'b'")
    cols = set(SCHEMA[BY_KEY[entity].table][i]["col"] for i in range(len(SCHEMA[BY_KEY[entity].table])))
    bad = [c for c, side in (fields or {}).items() if c not in cols or side not in ("a", "b")]
    if bad:
        raise ValueError(f"invalid field choices: {bad}")
    with _lock:
        data = _load_all()
        src = data["sources"].setdefault(source, {})
        if decision == "undecided":
            src.pop(key, None)
            rec = None
        else:
            rec = {"decision": decision, "entity": entity, "a": a, "b": b,
                   "keep": keep if decision == "merge" else None,
                   "fields": {c: s for c, s in (fields or {}).items() if decision == "merge"},
                   "by": by, "at": datetime.now().isoformat(timespec="seconds")}
            src[key] = rec
        DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DECISIONS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return rec


def apply_decisions(results: dict[str, list], decisions: dict[str, dict]) -> dict[str, list]:
    """Drop duplicate findings the reviewer has decided (merged or not a duplicate)."""
    if not decisions:
        return results
    decided_accounts = {i for k, d in decisions.items() if d["entity"] == "company" for i in (d["a"], d["b"])}
    out = dict(results)
    for rule_id, ent in BY_RULE.items():
        if rule_id in out:
            keep = [r for r in out[rule_id]
                    if pair_key(ent.key, str(r[0]), _partner(str(r[1]) if len(r) > 1 else "") or "") not in decisions]
            if keep:
                out[rule_id] = keep
            else:
                out.pop(rule_id)
    if SPLIT_RULE in out:   # a job sitting on a duplicate company is resolved once that company pair is decided
        keep = [r for r in out[SPLIT_RULE] if _partner(str(r[1])) not in decided_accounts]
        if keep:
            out[SPLIT_RULE] = keep
        else:
            out.pop(SPLIT_RULE)
    return out


def merges(source: str) -> list[dict]:
    """Merge instructions for the SQL generator: table, survivor id, duplicate id, columns taken from the duplicate."""
    out = []
    for d in load_decisions(source).values():
        if d["decision"] != "merge":
            continue
        survivor, duplicate = (d["a"], d["b"]) if d["keep"] == "a" else (d["b"], d["a"])
        other = "b" if d["keep"] == "a" else "a"
        out.append({"table": BY_KEY[d["entity"]].table, "survivor": survivor, "duplicate": duplicate,
                    "take_from_duplicate": sorted(c for c, side in d["fields"].items() if side == other)})
    return out


# ── side-by-side detail ────────────────────────────────────────────────────────

def _links(con, table: str, pk_value: str, poly_type: str | None, fks) -> list[dict]:
    """What is attached to one record: every FK child + polymorphic notes/documents/tags/log."""
    pk = PK[table]
    out = []
    for child, col, parent, pcol in fks:
        if parent != table or pcol != pk:
            continue
        n = con.execute(f'SELECT COUNT(*) FROM "{child}" WHERE CAST("{col}" AS VARCHAR) = ?', [pk_value]).fetchone()[0]
        if n:
            out.append({"table": child, "column": col, "count": n})
    if poly_type:
        for t, tcol, idcol in _POLY:
            n = con.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{tcol}" = ? AND CAST("{idcol}" AS VARCHAR) = ?',
                            [poly_type, pk_value]).fetchone()[0]
            if n:
                out.append({"table": t, "column": f"{tcol}={poly_type}", "count": n})
    return out


def pair_detail(con, pair: dict, fks) -> dict:
    ent = BY_KEY[pair["entity"]]
    pk = PK[ent.table]
    recs = {}
    for side in ("a", "b"):
        cur = con.execute(f'SELECT * FROM "{ent.table}" WHERE CAST("{pk}" AS VARCHAR) = ?', [pair[side]])
        row = cur.fetchone()
        recs[side] = {d[0]: (None if v is None else str(v)) for d, v in zip(cur.description, row)} if row else None
    fields = []
    if recs["a"] and recs["b"]:
        for c in recs["a"]:
            fields.append({"column": c, "a": recs["a"][c], "b": recs["b"][c], "same": recs["a"][c] == recs["b"][c],
                           "key": c == pk})
    return {**pair, "fields": fields,
            "links": {s: _links(con, ent.table, pair[s], ent.poly_type, fks) for s in ("a", "b")}}
