"""Review by records: the customer's data as records in the canonical (middle-tier) model.

Each record comes with its related records, plain-language flags (what to check first) and, for any
value, where it came from in the legacy source (table, column, row, raw value).
"""

from __future__ import annotations

import re
from collections import defaultdict

from app import engine_bridge as bridge
from app import layers

ENTITIES = ["candidates", "clients", "contacts", "jobs", "placements"]
LABELS = {"candidates": "Candidates", "clients": "Clients", "contacts": "Contacts", "jobs": "Jobs", "placements": "Placements"}
ID = {"candidates": "candidate_id", "clients": "client_id", "contacts": "contact_id", "jobs": "job_id", "placements": "placement_id"}
# legacy table the data quality rules report on -> the entity whose id is that table's key
RULE_TABLE = {"Person": "candidates", "Associates": "contacts", "Accounts": "clients", "Req": "jobs", "Req_Hired": "placements"}
# fields a record should have; a gap is flagged
EXPECTED = {
    "candidates": [("email", "No email address"), ("mobile", "No mobile number"), ("postcode", "No home postcode")],
    "clients": [("postcode", "No postcode"), ("phone", "No phone number")],
    "contacts": [("email", "No email address"), ("client_id", "Not linked to a company")],
    "jobs": [("client_id", "Not linked to a company")],
    "placements": [("fee", "No fee recorded")],
}
REJECT_TABLE = {"Applicant": "candidates", "Contact": "contacts", "Company": "clients", "Position": "jobs", "Placements": "placements"}


def _rows(key: str) -> list[dict]:
    return layers.rows("middle", key, limit=1_000_000)["rows"]


def _index(key: str) -> dict[str, dict]:
    return {r[ID[key]]: r for r in _rows(key)} if key in ID else {}


def _name(r: dict | None, *cols) -> str:
    if not r:
        return "?"
    return " ".join(str(r[c]) for c in cols if r.get(c)) or "?"


def _title(key: str, r: dict, ix: dict) -> tuple[str, str]:
    if key == "candidates":
        job = " at ".join(x for x in (r.get("current_job_title"), r.get("current_employer")) if x)
        return _name(r, "first_name", "last_name"), " · ".join(x for x in (job, r.get("city")) if x)
    if key == "clients":
        return r.get("company_name") or "?", " · ".join(x for x in (r.get("industry"), r.get("city")) if x)
    if key == "contacts":
        co = ix["clients"].get(r.get("client_id") or "")
        return _name(r, "first_name", "last_name"), " · ".join(x for x in (r.get("job_title"), co and co.get("company_name")) if x)
    if key == "jobs":
        co = ix["clients"].get(r.get("client_id") or "")
        return r.get("title") or "?", " · ".join(x for x in ((co or {}).get("company_name"), r.get("status")) if x)
    if key == "placements":
        cand = ix["candidates"].get(r.get("candidate_id") or "")
        job = ix["jobs"].get(r.get("job_id") or "")
        return f"{_name(cand, 'first_name', 'last_name')} → {(job or {}).get('title') or '?'}", \
            " · ".join(x for x in (r.get("placement_type"), r.get("start_date") and f"from {r['start_date']}") if x)
    return r.get(ID[key]) or "?", ""


_flag_cache: dict = {}


def _flags() -> dict[str, dict[str, list[dict]]]:
    """entity -> record id -> [{level, message}] (cached for a minute: checks and rejects change only on a run)."""
    import time
    if _flag_cache.get("at", 0) > time.time() - 60:
        return _flag_cache["flags"]
    _flag_cache.update(flags=_compute_flags(), at=time.time())
    return _flag_cache["flags"]


def _compute_flags() -> dict[str, dict[str, list[dict]]]:
    """entity -> record id -> [{level, message}] from data quality findings, target rejects and gaps."""
    out: dict[str, dict[str, list[dict]]] = {k: defaultdict(list) for k in ENTITIES}
    # data quality findings (decided duplicates are dropped, as on the dashboard)
    try:
        raw = bridge._raw("legacy")
        from validation import duplicates as D
        from validation.baseline_rules import RULES
        from validation.standard_checks import STANDARD_CHECKS
        results = D.apply_decisions(raw["results"], D.load_decisions("legacy"))
        check_of = {rid: c.name for c in STANDARD_CHECKS for rid in c.rule_ids}
        table_of = {r.id: r.table for r in RULES}
        for rid, rows in results.items():
            ent = RULE_TABLE.get(table_of.get(rid, ""))
            if not ent:
                continue
            for row in rows:
                detail = f": {row[1]}" if len(row) > 1 and row[1] else ""
                out[ent][str(row[0])].append({"level": "check", "message": f"{check_of.get(rid, rid)}{detail}"})
    except Exception:                                        # noqa: BLE001 — checks not run yet
        pass
    # rows the target load rejected or flagged
    try:
        for r in layers.rejects():
            ent = REJECT_TABLE.get(r["table"])
            if ent and r["key"]:
                out[ent][r["key"]].append({"level": r["action"], "message": f"{'Not loaded' if r['action'] == 'rejected' else 'Loaded, but'}: {r['reason']}"})
    except Exception:                                        # noqa: BLE001 — target not run yet
        pass
    # missing values the record should have
    for key, expected in EXPECTED.items():
        for r in _rows(key):
            for col, msg in expected:
                if not r.get(col):
                    out[key][r[ID[key]]].append({"level": "gap", "message": msg})
    return out


def records(key: str, q: str | None = None, flagged_only: bool = False) -> dict:
    if key not in ENTITIES:
        raise KeyError(key)
    ix = {k: _index(k) for k in ENTITIES}
    flags = _flags()[key]
    items = []
    for r in _rows(key):
        title, sub = _title(key, r, ix)
        n = len(flags.get(r[ID[key]], []))
        if flagged_only and not n:
            continue
        if q and q.lower() not in f"{title} {sub} {r[ID[key]]}".lower():
            continue
        items.append({"id": r[ID[key]], "title": title, "subtitle": sub, "flags": n})
    items.sort(key=lambda x: (-x["flags"], x["title"]))                 # flags first
    return {"entity": key, "label": LABELS[key], "total": len(_rows(key)), "flagged": sum(1 for v in flags.values() if v),
            "records": items}


def _related(key: str, r: dict, ix: dict) -> list[dict]:
    rid = r[ID[key]]

    def item(k, rec):
        t, s = _title(k, rec, ix)
        return {"entity": k, "id": rec[ID[k]], "title": t, "subtitle": s}

    def rows_where(table_key: str, col: str, value: str):
        return [x for x in _rows(table_key) if x.get(col) == value]

    def one(k, id_):
        rec = ix[k].get(id_ or "")
        return [item(k, rec)] if rec else []

    out = []
    if key == "candidates":
        apps = rows_where("applications", "candidate_id", rid)
        out.append({"label": "Applications", "items": [
            {"entity": "jobs", "id": a["job_id"], "title": (ix["jobs"].get(a["job_id"] or "") or {}).get("title") or f"Job {a['job_id']}",
             "subtitle": " · ".join(x for x in (a.get("stage"), a.get("applied_at")) if x)} for a in apps]})
        out.append({"label": "Placements", "items": [item("placements", p) for p in rows_where("placements", "candidate_id", rid)]})
        out.append({"label": "Work history", "items": [
            {"title": w.get("job_title") or "?", "subtitle": " · ".join(x for x in (w.get("employer"), f"{w.get('start_date') or '?'} to {w.get('end_date') or 'now'}") if x)}
            for w in sorted(rows_where("work_history", "candidate_id", rid), key=lambda w: w.get("start_date") or "", reverse=True)]})
    if key == "clients":
        out.append({"label": "Contacts", "items": [item("contacts", c) for c in rows_where("contacts", "client_id", rid)]})
        out.append({"label": "Jobs", "items": [item("jobs", j) for j in rows_where("jobs", "client_id", rid)]})
    if key == "contacts":
        out.append({"label": "Company", "items": one("clients", r.get("client_id"))})
        out.append({"label": "Jobs", "items": [item("jobs", j) for j in rows_where("jobs", "contact_id", rid)]})
    if key == "jobs":
        out.append({"label": "Company", "items": one("clients", r.get("client_id"))})
        out.append({"label": "Contact", "items": one("contacts", r.get("contact_id"))})
        out.append({"label": "Placements", "items": [item("placements", p) for p in rows_where("placements", "job_id", rid)]})
        out.append({"label": "Applications", "items": [
            {"entity": "candidates", "id": a["candidate_id"], "title": _name(ix["candidates"].get(a["candidate_id"] or ""), "first_name", "last_name"),
             "subtitle": a.get("stage") or ""} for a in rows_where("applications", "job_id", rid)]})
    if key == "placements":
        out.append({"label": "Candidate", "items": one("candidates", r.get("candidate_id"))})
        out.append({"label": "Job", "items": one("jobs", r.get("job_id"))})
        job = ix["jobs"].get(r.get("job_id") or "")
        out.append({"label": "Company", "items": one("clients", (job or {}).get("client_id"))})
    poly = {"candidates": "candidate", "clients": "client", "contacts": "contact", "jobs": "job"}.get(key)
    if poly:
        docs = [d for d in _rows("documents") if d.get("entity_type") == poly and d.get("entity_id") == rid]
        out.append({"label": "Documents", "items": [{"title": d.get("file_name") or "?", "subtitle": d.get("uploaded_at") or ""} for d in docs]})
        notes = [n for n in _rows("notes") if n.get("entity_type") == poly and n.get("entity_id") == rid]
        out.append({"label": "Notes", "items": [{"title": (n.get("body") or "")[:140], "subtitle": n.get("created_at") or ""} for n in notes]})
    return out


def record(key: str, rid: str) -> dict:
    if key not in ENTITIES:
        raise KeyError(key)
    ix = {k: _index(k) for k in ENTITIES}
    r = ix[key].get(rid)
    if r is None:
        raise KeyError(rid)
    title, sub = _title(key, r, ix)
    label = lambda c: c.replace("_user_id", "").replace("_id", "").replace("_", " ").capitalize()   # noqa: E731
    users = {u["user_id"]: _name(u, "first_name", "last_name") for u in _rows("users")}
    show = lambda c, v: f"{users[v]} ({v})" if c.endswith("user_id") and v in users else v   # noqa: E731
    return {"entity": key, "label": LABELS[key], "id": rid, "title": title, "subtitle": sub,
            "fields": [{"column": c, "label": label(c), "value": show(c, v)} for c, v in r.items()],
            "flags": _flags()[key].get(rid, []), "related": _related(key, r, ix)}


def source(key: str, rid: str, column: str) -> dict:
    """Where one value came from: the middle-tier expression, and the legacy table/column/row it reads."""
    import tiers as TI
    e = TI.MIDDLE.entity(key)
    _, _, PK, _ = bridge._engine()
    overrides = TI.load_overrides()
    for n, ins in enumerate(e.inserts):
        if column not in ins.columns:
            continue
        fmt = lambda s: s.replace("{src}", TI.MIDDLE.src)                 # noqa: E731
        expr = TI.expression(TI.MIDDLE, e, n, column, overrides)
        id_expr = TI.expression(TI.MIDDLE, e, n, next(iter(ins.columns)), overrides)
        aliases = {}
        applied = {}                                     # OUTER APPLY alias -> tables it reads
        for frag in [ins.source, *ins.joins]:
            is_apply = frag.lstrip().upper().startswith("OUTER APPLY")
            m = re.search(r"\{src\}(\w+)\s+(\w+)(?:\s|$)", frag)
            if m and not is_apply:
                aliases[m.group(2)] = m.group(1)
            ma = re.search(r"\)\s*(\w+)\s*$", frag)
            if is_apply and ma:
                applied[ma.group(1)] = re.findall(r"\{src\}(\w+)", frag)
        all_refs = re.findall(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", expr)
        refs = [(a, c) for a, c in all_refs if a in aliases]
        derived = [(a, c) for a, c in all_refs if a in applied]
        cols = [f"CAST(({fmt(expr)}) AS NVARCHAR(MAX)) AS [value]"]
        for i, (a, c) in enumerate(refs):
            pk = PK.get(aliases[a])
            cols.append(f"CAST({a}.[{c}] AS NVARCHAR(MAX)) AS [raw{i}]")
            cols.append(f"CAST({a}.[{pk}] AS NVARCHAR(200)) AS [key{i}]" if pk else f"NULL AS [key{i}]")
        sql = (f"SELECT TOP 1 {', '.join(cols)} FROM {fmt(ins.source)} " + " ".join(fmt(j) for j in ins.joins)
               + f" WHERE CAST(({fmt(id_expr)}) AS NVARCHAR(200)) = ?")
        cn = TI._connect(TI.SOURCE_DB)
        try:
            row = cn.cursor().execute(sql, rid).fetchone()
        finally:
            cn.close()
        if row is None:
            continue
        schema = bridge._engine()[3]
        has = lambda t, c: any(x["col"] == c for x in schema.get(t, []))   # noqa: E731
        via = [{"table": next((t for t in applied[a] if has(t, c)), applied[a][0]), "column": c, "key_column": None,
                "key": None, "raw": row[0], "derived": True} for a, c in derived]
        if via:
            note = "Taken from the most recent related row (latest job / latest application)"
        elif not refs:
            note = "A fixed value set by the mapping, not read from the source"
        else:
            note = None
        return {"column": column, "expression": expr, "value": row[0],
                "sources": [{"table": aliases[a], "column": c, "key_column": PK.get(aliases[a]), "key": row[2 + 2 * i],
                             "raw": row[1 + 2 * i]} for i, (a, c) in enumerate(refs)] + via,
                "note": note}
    return {"column": column, "expression": None, "value": None, "sources": [],
            "note": "This record was merged or comes from a duplicate; its source row isn't the one shown"}
