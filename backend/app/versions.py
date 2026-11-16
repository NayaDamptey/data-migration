"""Version review: every run is a version (engine/transform/runs.py).

A version shows what it was (a fresh load, duplicate decisions applied, field changes made in it), an
audit trail of source and target row counts, and, for each merge it applied for the first time, both
records as they were and the record they became (from that run's staging and middle-tier tables).
"""

from __future__ import annotations

from app import layers

# merge kind -> middle-tier entity
KIND_ENTITY = {"candidate": "candidates", "contact": "contacts", "client": "clients", "job": "jobs", "timesheet_line": "timesheet_lines"}


def _row(con, sql: str, *params) -> dict | None:
    cur = con.execute(sql, list(params))
    r = cur.fetchone()
    if r is None:
        return None
    return {d[0]: (None if v is None else str(v)[:-9] if str(v).endswith(" 00:00:00") else str(v)) for d, v in zip(cur.description, r)}


def _merges(run: dict) -> list[dict]:
    B, RU = layers._engine()
    key = lambda m: (m["kind"], m["duplicate"], m["survivor"])          # noqa: E731
    before = {key(m) for m in RU.merges_of(run["previous"])} if run.get("previous") else set()
    out = []
    con = RU.connect(run["id"])
    for m in RU.merges_of(run["id"]):
        if key(m) in before or m["kind"] not in KIND_ENTITY:
            continue
        ent = next(e for e in B.load_spec("middle")["entities"] if e["key"] == KIND_ENTITY[m["kind"]])
        idc = next(iter(ent["selects"][0]["columns"]))
        try:
            kept = _row(con, f'SELECT * FROM staging."stg_{ent["key"]}" WHERE {idc} = ?', m["survivor"])
            dup = _row(con, f'SELECT * FROM staging."stg_{ent["key"]}" WHERE {idc} = ?', m["duplicate"])
            merged = _row(con, f'SELECT * FROM mid."{ent["table"]}" WHERE {idc} = ?', m["survivor"])
        except Exception:                                    # noqa: BLE001
            continue
        out.append({"entity": ent["label"], "id_column": idc, "kept": kept, "duplicate": dup, "merged": merged,
                    "taken_from_duplicate": []})
    return out


def log(limit: int = 50) -> dict:
    _, RU = layers._engine()
    out = []
    for r in RU.history()[:limit]:
        if "counts" not in r:                            # a run that never finished building
            continue
        out.append({"hash": r["id"], "message": r.get("message", ""), "date": (r.get("built_at") or r.get("created", ""))[:16],
                    "tables": [], "counts": r.get("reconciliation", []), "changes": r.get("changes", []),
                    "merges": _merges(r)})
    return {"available": True, "commits": out}
