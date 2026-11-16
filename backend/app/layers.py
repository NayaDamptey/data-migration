"""The middle tier and the target for the UI, on the dbt engine (engine/transform):
the mapping spec -> generated dbt models -> dbt build on the current run's DuckDB warehouse.

Run a layer, read its tables, show each entity's dbt model, and let a developer change any field's
expression (the spec is updated and the affected models rebuilt; a failing change is undone).
"""

from __future__ import annotations

import threading

from app import engine_bridge as bridge  # noqa: F401  (puts engine/ on sys.path)

_lock = threading.RLock()
_rows: dict[tuple, list[dict]] = {}
LAYERS = ("middle", "target")


def _engine():
    import sys
    t = str(bridge.ENGINE / "transform")
    if t not in sys.path:
        sys.path.insert(0, t)
    import build_dbt as B
    import runs as RU
    return B, RU


def _check(name: str):
    if name not in LAYERS:
        raise KeyError(name)


def _current() -> str:
    """The run the app shows; the first time, a run is made from the legacy database."""
    B, RU = _engine()
    rid = RU.current()
    if rid is None:
        with _lock:
            rid = RU.current()
            if rid is None:
                rid = RU.new_run("Initial load", source="legacy")
                RU.build(rid, "all")
                _name_merges(rid)
    return rid


def _name_merges(rid: str):
    """A run's message names the duplicate merges it applied that the previous run didn't."""
    B, RU = _engine()
    data = RU.info(rid)
    prev = data.get("previous")
    key = lambda m: (m["kind"], m["duplicate"], m["survivor"])                     # noqa: E731
    now = {key(m) for m in RU.merges_of(rid)}
    before = {key(m) for m in RU.merges_of(prev)} if prev else set()
    new, undone = sorted(now - before), sorted(before - now)
    if not prev:
        return
    parts = ([f"Merged duplicate {', '.join(f'{k} {d} into {s}' for k, d, s in new)}"] if new else []) \
        + ([f"Undid merge of {', '.join(f'{k} {d} into {s}' for k, d, s in undone)}"] if undone else [])
    if parts:
        data["message"] = "; ".join(parts)
        RU._save(rid, data)


def run(name: str) -> dict:
    """Run canonical layer: a new run from the legacy database (middle tier). Run target: the target on
    the current run."""
    _check(name)
    B, RU = _engine()
    with _lock:
        if name == "middle":
            rid = RU.new_run("Run canonical layer", source="legacy")
            data = RU.build(rid, "all")      # the target always follows the middle tier it reads
            _name_merges(rid)
        else:
            rid = _current()
            data = RU.build(rid, "target")
        _rows.clear()
    return {"layer": name, "run": rid, "entities": _counts(name, data)}


_pending = threading.Event()


def apply_decisions_async():
    """A duplicate decision was saved: a new run on the same source with the merges applied, built in the
    background. Several quick decisions are applied together."""
    if _pending.is_set():
        return
    _pending.set()

    def go():
        B, RU = _engine()
        with _lock:
            _pending.clear()
            try:
                rid = RU.new_run("Duplicate decisions applied", source="copy")
                RU.build(rid, "all")
                _name_merges(rid)
                _rows.clear()
            except Exception as e:                       # noqa: BLE001
                print(f"[layers] applying decisions failed: {e}")
    threading.Thread(target=go, daemon=True).start()


def _schema(name: str) -> str:
    return "mid" if name == "middle" else "target"


def _spec(name: str, with_overrides: bool = True) -> dict:
    B, _ = _engine()
    return B.load_spec(name, with_overrides)


def _entity(name: str, key: str) -> dict:
    e = next((x for x in _spec(name)["entities"] if x["key"] == key), None)
    if e is None:
        raise KeyError(key)
    return e


def _counts(name: str, data: dict) -> dict:
    by_table = data.get("counts", {}).get(_schema(name), {})
    return {e["key"]: by_table.get(e["table"]) for e in _spec(name)["entities"]}


def rows(name: str, key: str, limit: int = 100, q: str | None = None, raw: bool = False) -> dict:
    _check(name)
    B, RU = _engine()
    rid = _current()
    e = _entity(name, key)
    ck = (rid, name, key)
    with _lock:
        if ck not in _rows:
            con = RU.connect(rid)
            cur = con.execute(f'SELECT * FROM {_schema(name)}."{e["table"]}"')
            cols = [d[0] for d in cur.description]
            out = []
            for r in cur.fetchall():
                rec = {}
                for c, v in zip(cols, r):
                    if v is None:
                        rec[c] = None
                    elif isinstance(v, bool):
                        rec[c] = "true" if v else "false"
                    else:
                        s = str(v)
                        rec[c] = s[:-9] if s.endswith(" 00:00:00") else s
                out.append(rec)
            first = cols[0]
            out.sort(key=lambda r: (len(r[first] or ""), r[first] or ""))
            _rows[ck] = out
        data = _rows[ck]
    if not raw:                                          # high-sensitivity personal data is masked
        from app import privacy
        data = privacy.mask_rows(name, key, data)
    found = data
    if q:
        ql = q.lower()
        found = [r for r in data if any(v and ql in v.lower() for v in r.values())]
    return {"entity": key, "total": len(data), "matched": len(found), "rows": found[:limit]}


def summary(name: str) -> dict:
    _check(name)
    _, RU = _engine()
    return {"layer": name, "entities": _counts(name, RU.info(_current()))}


def _model_file(name: str, e: dict):
    B, _ = _engine()
    return (B.DBT / "models" / "staging" / f"stg_{e['key']}.sql") if name == "middle" \
        else (B.DBT / "models" / "target" / f"target_{e['table'].lower()}.sql")


def detail(name: str) -> dict:
    """Each entity's dbt model and its field expressions (the developer view)."""
    _check(name)
    B, RU = _engine()
    rid = _current()
    spec, base = _spec(name), _spec(name, with_overrides=False)
    mine = B.load_overrides().get(name, {})
    counts = _counts(name, RU.info(rid))
    from app import privacy
    P = privacy._pii()
    tags = privacy.ensure_tags()
    ents = []
    for e in spec["entities"]:
        be = next(x for x in base["entities"] if x["key"] == e["key"])
        cats = privacy.categories(name, e["key"])
        mine_tags = tags.get(e["key"], {}) if name == "middle" else {}
        pii_of = lambda c: ({"category": cats[c], "label": P.CATEGORIES[cats[c]][0], "level": P.CATEGORIES[cats[c]][1],   # noqa: E731
                             "status": mine_tags.get(c, {}).get("status", "inherited"), "why": mine_tags.get(c, {}).get("why")}
                            if c in cats else ({"category": None, "status": "confirmed"} if mine_tags.get(c, {}).get("status") == "confirmed" else None))
        f = _model_file(name, e)
        import re
        sources = sorted({m for s in e["selects"] for m in re.findall(r"\b(?:src|mid)__(\w+)", s["from"])})
        ents.append({
            "key": e["key"], "label": e["label"], "table": f"{_schema(name)}.{e['table']}",
            "file": f.relative_to(B.DBT).as_posix(), "sources": sources, "rows": counts.get(e["key"]),
            "inserts": [{"n": n, "source": s["from"], "fields": [
                {"column": c, "expression": str(x), "default": str(be["selects"][n]["columns"][c]),
                 "overridden": f"{e['key']}:{n}:{c}" in mine, "pii": pii_of(c)}
                for c, x in s["columns"].items()]} for n, s in enumerate(e["selects"])],
            "sql": f.read_text(encoding="utf-8") if f.exists() else "",
        })
    return {"layer": name, "source_db": "source Parquet" if name == "middle" else "mid",
            "db": f"run {rid} · {_schema(name)}", "entities": ents}


def set_field(name: str, key: str, n: int, column: str, expression: str | None) -> dict:
    """Change one field's expression in the mapping spec (None = back to the default), then rebuild the
    affected dbt models on the current run. If dbt fails, the change is undone and the error raised."""
    _check(name)
    B, RU = _engine()
    e = _entity(name, key)
    base = next(x for x in _spec(name, with_overrides=False)["entities"] if x["key"] == key)
    if n >= len(e["selects"]) or column not in e["selects"][n]["columns"]:
        raise KeyError(column)
    rid = _current()
    with _lock:
        o = B.load_overrides()
        before = {k: dict(v) for k, v in o.items()}
        fk = f"{key}:{n}:{column}"
        default = str(base["selects"][n]["columns"][column])
        mine = o.setdefault(name, {})
        if expression is None or not expression.strip() or expression.strip() == default:
            mine.pop(fk, None)
        else:
            mine[fk] = expression.strip()
        B.save_overrides(o)
        select = [f"stg_{key}+"] if name == "middle" else [f"target_{e['table'].lower()}", "migration_rejects"]
        try:
            RU.build(rid, select=select)
        except Exception as ex:                          # noqa: BLE001 — undo, report dbt's error
            B.save_overrides(before)
            try:
                RU.build(rid, select=select)
            except Exception:                            # noqa: BLE001
                pass
            msg = str(ex)
            raise ValueError(msg[msg.find("Binder Error"):] if "Binder Error" in msg else msg[-600:]) from None
        what = "middle tier" if name == "middle" else "target"
        RU.log_change(rid, f"Changed {what} {e['table']}.{column} to {expression.strip() if expression and expression.strip() else 'its default'}")
        _rows.clear()
    return detail(name)


def rejects() -> list[dict]:
    """Rows the target load rejected (not loaded) or flagged (loaded, needs a look)."""
    _, RU = _engine()
    con = RU.connect(_current())
    return [{"table": t, "key": k, "action": a, "reason": r} for t, k, a, r in
            con.execute("SELECT target_table, source_key, action, reason FROM audit.migration_rejects "
                        "ORDER BY action DESC, target_table, source_key").fetchall()]
