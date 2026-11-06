"""Bridge from the API to the migration engine in ../engine.

The engine (validation rules, relational mapping, SQL generation) lives in
engine/ and is plain Python. This module puts it on the path and turns its
results into JSON-friendly dicts for the routers.

Data sources the dashboard can check
  legacy           the legacy SQL Server DB (RecruitCRM_Legacy), with its real defects
  baseline         the clean baseline CSVs (engine/sample_data/source) — should score 100%
  upload:<project> the CSV files a project uploaded (storage/projects/<id>/source)
"""
from __future__ import annotations

import csv
import os
import re
import sys
import threading
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENGINE = Path(os.getenv("ENGINE_DIR", REPO / "engine")).resolve()
STORAGE = Path(os.getenv("LOCAL_STORAGE_DIR", REPO / "storage")).resolve()

for p in (ENGINE, ENGINE / "sample_data", ENGINE / "mapping"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

CATEGORY_LABELS = {
    "INTEGRITY": "Duplicate or missing keys",
    "ORPHAN_FK": "Broken links between records",
    "MISSING_REQUIRED": "Missing required values",
    "INVALID_EMAIL": "Invalid email addresses",
    "INVALID_POSTCODE": "Invalid postcodes",
    "INVALID_PHONE": "Invalid phone numbers",
    "INVALID_NI_NUMBER": "Invalid NI numbers",
    "INVALID_SORT_CODE": "Invalid sort codes",
    "NON_STANDARD_DOMAIN": "Inconsistent coded values",
    "WHITESPACE_CASE": "Stray spaces or wrong case",
    "SENTINEL_DATE": "Placeholder or impossible dates",
    "DATE_LOGIC": "Dates in the wrong order",
    "OUT_OF_RANGE": "Values out of range",
    "ENCODING": "Garbled characters",
    "SOFT_DELETE_CONFLICT": "Deleted records still in use",
    "DUPLICATE_ACCOUNT": "Duplicate companies",
    "DUPLICATE_PERSON": "Duplicate people",
    "DUPLICATE_ASSOCIATE": "Duplicate contacts",
    "DUPLICATE_TRANSACTION": "Double-entered transactions",
    "SPLIT_HISTORY": "History split across duplicates",
    "DUPLICATE_JOB": "Duplicate jobs",
    "ORPHAN_CONTACT": "Contacts linked to no company",
    "ORPHAN_CANDIDATE": "Candidates linked to no job",
    "ORPHAN_DOCUMENT": "Documents linked to no record",
    "ORPHAN_NOTE": "Notes linked to no record",
    "CONSISTENCY": "Records that contradict each other",
    "ROLE": "People in the wrong role",
    "FINANCE": "Money that doesn't add up",
}
# Categories that block a clean migration if left unfixed
CRITICAL = {"INTEGRITY", "ORPHAN_FK", "MISSING_REQUIRED", "DUPLICATE_ACCOUNT", "DUPLICATE_PERSON",
            "DUPLICATE_ASSOCIATE", "DUPLICATE_TRANSACTION", "SPLIT_HISTORY", "FINANCE", "DUPLICATE_JOB",
            "ORPHAN_CONTACT", "ORPHAN_CANDIDATE", "ORPHAN_DOCUMENT", "ORPHAN_NOTE", "SOFT_DELETE_CONFLICT"}

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict, object]] = {}     # source -> (built_at, report, duckdb con)
CACHE_SECONDS = 600


def upload_dir(project_id: str) -> Path:
    return STORAGE / "projects" / project_id / "source"


def evaluate_standard(results, ran):
    from validation.standard_checks import evaluate
    return evaluate(results, ran)


@lru_cache
def _engine():
    from validation import validator as V           # noqa: WPS433 (engine import)
    from validation.baseline_rules import RULES, PK
    from build_source_db import load_schema
    return V, RULES, PK, load_schema()


def _connect(source: str):
    V, *_ = _engine()
    if source == "legacy":
        return V.load_sqlserver(), {"label": "Legacy database (RecruitCRM_Legacy on SQL Server)", "kind": "legacy"}
    if source == "baseline":
        return V.load_csv_baseline(), {"label": "Clean baseline (engine sample data)", "kind": "baseline"}
    if source.startswith("upload:"):
        folder = upload_dir(source.split(":", 1)[1])
        if not folder.exists() or not any(folder.glob("*.csv")):
            raise FileNotFoundError("No CSV files uploaded for this project yet")
        _, _, _, schema = _engine()
        known = {t.lower() for t in schema}
        unknown = sorted(p.stem for p in folder.glob("*.csv") if p.stem.lower() not in known)
        return V.load_csv_baseline(folder, lenient=True), {
            "label": f"Uploaded files ({folder.parent.name})", "kind": "upload",
            "unrecognised_files": unknown,
            "note": "Rules run on files named like the legacy tables (e.g. Accounts.csv). Values that don't fit a column's type are read as empty."}
    raise ValueError(f"Unknown source {source!r}")


def _table_stats(con, schema: dict, present: set[str]) -> dict[str, dict]:
    stats = {}
    for t, cols in schema.items():
        if t not in present:
            continue
        rows = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        filled = 0
        if rows:
            expr = " + ".join(f'COUNT("{c["col"]}")' for c in cols)
            filled = con.execute(f'SELECT {expr} FROM "{t}"').fetchone()[0]
        cells = rows * len(cols)
        stats[t] = {"rows": rows, "columns": len(cols), "completeness": round(100 * filled / cells, 1) if cells else None}
    return stats


def _run_checks(source: str) -> dict:
    """The expensive part: run every standard-check rule once. Cached per source."""
    V, RULES, PK, schema = _engine()
    started = time.time()
    con, meta = _connect(source)

    # which tables actually hold data (uploads may cover only part of the schema)
    present = set()
    for t in schema:
        try:
            if con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] > 0:
                present.add(t)
        except Exception:                                    # noqa: BLE001
            pass

    # The dashboard shows the STANDARD CHECKS only (validation/standard_checks.py). Every other rule guards the
    # source data itself and is enforced by the engine's tests, not shown in the UI.
    from validation.standard_checks import STANDARD_CHECKS
    standard_ids = set().union(*(c.rule_ids for c in STANDARD_CHECKS))
    results: dict[str, list] = {}           # rule id -> violating rows (failing rules only)
    ran: set[str] = set()                   # every rule that ran
    not_applicable = []
    for r in (r for r in RULES if r.id in standard_ids):
        # a rule only applies if every table it reads holds data (partial uploads: a link to an
        # un-uploaded parent table is unknown, not broken)
        needed = {t for t in re.findall(r'\b(?:FROM|JOIN)\s+"?([A-Za-z_]\w*)"?', r.sql) if t in schema} | {r.table}
        if not needed <= present:
            not_applicable.append({"id": r.id, "missing_tables": sorted(needed - present)})
            continue
        try:
            rows = con.execute(r.sql).fetchall()
        except Exception:                                    # noqa: BLE001
            continue
        ran.add(r.id)
        if rows:
            results[r.id] = rows
    return {"source": source, "meta": meta, "started": started, "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": round(time.time() - started, 1), "results": results, "ran": ran,
            "not_applicable": not_applicable, "stats": _table_stats(con, schema, present),
            "answer_key": _score_answer_key(con) if source == "legacy" else None, "con": con}


def _assemble(raw: dict) -> dict:
    """Cheap: turn cached rule results into the dashboard report, after applying the reviewer's decisions."""
    _, RULES, _, _ = _engine()
    from validation import duplicates as D
    decisions = D.load_decisions(raw["source"])
    all_pairs = D.pairs_from_results(raw["results"])
    results = D.apply_decisions(raw["results"], decisions)
    rule_by_id = {r.id: r for r in RULES}

    rules_out, affected = [], set()
    by_table = defaultdict(lambda: {"violations": 0, "failed_rules": 0, "records": set()})
    for rid, rows in results.items():
        r = rule_by_id[rid]
        bt = by_table[r.table]
        bt["violations"] += len(rows)
        bt["failed_rules"] += 1
        for row in rows:
            bt["records"].add(str(row[0]))
            affected.add((r.table, str(row[0])))
        rules_out.append({"id": r.id, "category": r.category, "category_label": CATEGORY_LABELS.get(r.category, r.category),
                          "critical": r.category in CRITICAL, "table": r.table, "description": r.description,
                          "violations": len(rows), "is_duplicate": rid in D.DUP_RULE_IDS,
                          "sample": [{"key": str(x[0]), "detail": (str(x[1]) if len(x) > 1 and x[1] is not None else "")[:160]}
                                     for x in rows[:5]]})
    stats = raw["stats"]
    total_rows = sum(s["rows"] for s in stats.values())
    applicable, failed = len(raw["ran"]), len(rules_out)
    review = {"total": len(all_pairs), "merged": 0, "not_duplicate": 0}
    for p in all_pairs:
        d = decisions.get(p["key"])
        if d:
            review["merged" if d["decision"] == "merge" else "not_duplicate"] += 1
    review["to_review"] = review["total"] - review["merged"] - review["not_duplicate"]
    return {
        "source": {**raw["meta"], "id": raw["source"], "checked_at": raw["checked_at"], "seconds": raw["seconds"]},
        "totals": {
            "tables": len(stats), "rows": total_rows,
            "rules": applicable, "passed": applicable - failed, "failed": failed,
            "violations": sum(r["violations"] for r in rules_out),
            "critical_violations": sum(r["violations"] for r in rules_out if r["critical"]),
            "affected_records": len(affected),
            "score": round(100 * (applicable - failed) / applicable, 1) if applicable else None,
            "clean_records_pct": round(100 * (1 - len(affected) / total_rows), 1) if total_rows else None,
        },
        "categories": [],
        "tables": sorted(
            [{"table": t, **s, "violations": by_table[t]["violations"], "failed_rules": by_table[t]["failed_rules"],
              "affected_records": len(by_table[t]["records"]),
              "clean_pct": round(100 * (1 - len(by_table[t]["records"]) / s["rows"]), 1) if s["rows"] else None}
             for t, s in stats.items()],
            key=lambda x: (-x["violations"], x["table"])),
        "standard_checks": evaluate_standard(results, raw["ran"]),
        "duplicate_review": review,
        "rules": sorted(rules_out, key=lambda r: (not r["critical"], -r["violations"])),
        "not_applicable": {"count": len(raw["not_applicable"]),
                           "missing_tables": sorted({t for n in raw["not_applicable"] for t in n["missing_tables"]})},
        "answer_key": raw["answer_key"],
    }


def _score_answer_key(con) -> dict | None:
    """How many of the planted (known) defects the rules find — proves the checks work."""
    V, *_ = _engine()
    manifest = ENGINE / "sql" / "source" / "defect_manifest.csv"
    if not manifest.exists():
        return None
    hits = {(v.table, v.pk) for v in V.run_rules(con)}
    rows = list(csv.DictReader(open(manifest, encoding="utf-8")))
    found = sum((m["table"], m["pk_value"]) in hits for m in rows)
    return {"planted": len(rows), "found": found}


def _raw(source: str, refresh: bool = False) -> dict:
    with _lock:
        hit = _cache.get(source)
        if hit and not refresh and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        raw = _run_checks(source)
        _cache[source] = (time.time(), raw, raw["con"])
        return raw


def report(source: str, refresh: bool = False) -> dict:
    return _assemble(_raw(source, refresh))


def duplicate_pairs(source: str, entity: str | None = None) -> dict:
    """Every suspected duplicate pair with both records side by side, what is linked to each, and the decision."""
    from validation import duplicates as D
    from relationships import all_foreign_keys
    _, _, _, schema = _engine()
    raw = _raw(source)
    decisions = D.load_decisions(source)
    fks = all_foreign_keys(schema)
    pairs = [p for p in D.pairs_from_results(raw["results"]) if not entity or p["entity"] == entity]
    out = [{**D.pair_detail(raw["con"], p, fks), "decision": decisions.get(p["key"])} for p in pairs]
    counts = {}
    for e in D.ENTITIES:
        ps = [p for p in D.pairs_from_results(raw["results"]) if p["entity"] == e.key]
        counts[e.key] = {"label": e.label, "total": len(ps), "to_review": sum(1 for p in ps if p["key"] not in decisions)}
    return {"source": source, "entities": counts, "pairs": out}


def decide(source: str, key: str, decision: str, keep: str | None, fields: dict | None) -> dict | None:
    from validation import duplicates as D
    raw = _raw(source)
    if key not in {p["key"] for p in D.pairs_from_results(raw["results"])}:
        raise KeyError(key)
    return D.save_decision(source, key, decision, keep, fields)


def invalidate(source: str):
    with _lock:
        _cache.pop(source, None)


def rule_rows(source: str, rule_id: str, limit: int = 200) -> dict:
    """Every violation of one rule, with the full source record for the first rows."""
    _, RULES, PK, _ = _engine()
    rule = next((r for r in RULES if r.id == rule_id), None)
    if not rule:
        raise KeyError(rule_id)
    con = _raw(source)["con"]
    rows = con.execute(rule.sql).fetchall()
    pk = PK.get(rule.table)
    records = []
    for key, *rest in rows[:limit]:
        rec = None
        if pk and len(records) < 25:
            cur = con.execute(f'SELECT * FROM "{rule.table}" WHERE CAST("{pk}" AS VARCHAR) = ?', [str(key)])
            got = cur.fetchone()
            if got:
                rec = {d[0]: (None if v is None else str(v)) for d, v in zip(cur.description, got)}
        records.append({"key": str(key), "detail": str(rest[0]) if rest and rest[0] is not None else "", "record": rec})
    return {"rule": {"id": rule.id, "category": rule.category, "category_label": CATEGORY_LABELS.get(rule.category, rule.category),
                     "table": rule.table, "key_column": pk, "description": rule.description, "sql": rule.sql.strip()},
            "total": len(rows), "rows": records}


def legacy_available() -> bool:
    try:
        import pyodbc
        from build_source_db import DEFAULT_DB, DEFAULT_SERVER
        pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DEFAULT_SERVER};DATABASE={DEFAULT_DB};"
                       "Trusted_Connection=yes;", timeout=3).close()
        return True
    except Exception:                                      # noqa: BLE001
        return False
