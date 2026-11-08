"""The two script layers of the migration (engine/mapping/tiers.py) for the UI:
middle tier (source -> Migration_Staging.mid) and target (mid -> RecruitPlatform_Target).

Run a layer, read its tables, show its scripts, and let a developer change any field's expression.
"""

from __future__ import annotations

import threading

from app import engine_bridge as bridge  # noqa: F401  (puts engine/mapping on sys.path)
from app import versions

_lock = threading.RLock()
_rows: dict[str, dict[str, list[dict]]] = {}
_ran: set[str] = set()


def _tiers():
    import tiers as TI                    # engine/mapping/tiers.py
    return TI


def _layer(name: str):
    TI = _tiers()
    if name not in TI.LAYERS:
        raise KeyError(name)
    return TI, TI.LAYERS[name]


def run(name: str) -> dict:
    TI, layer = _layer(name)
    with _lock:
        if name == "target" and "middle" not in _ran:     # the target reads the middle tier
            TI.run(TI.MIDDLE)
            _ran.add("middle")
            _rows.pop("middle", None)
        TI.write(layer)
        counts = TI.run(layer)
        _ran.add(name)
        _rows.pop(name, None)
    # new version in Dolt (in the background: the run is done either way)
    versions.snapshot_async(_run_message(name), wait_for=_lock)
    return {"layer": name, "entities": counts}


def _run_message(name: str) -> str:
    """Version message for a run; a middle-tier run names the duplicate merges it applied for the first time."""
    if name != "middle":
        return "Target run"
    import json
    try:
        from validation.duplicates import merges
        now = {f"{m['table']}:{m['duplicate']}:{m['survivor']}" for m in merges("legacy")}
    except Exception:                                        # noqa: BLE001
        return "Middle tier run"
    seen_file = versions.REPO.parent / "applied_merges.json"
    seen = set(json.loads(seen_file.read_text())) if seen_file.exists() else set()
    new, undone = sorted(now - seen), sorted(seen - now)
    seen_file.parent.mkdir(parents=True, exist_ok=True)
    seen_file.write_text(json.dumps(sorted(now)))
    names = {"Person": "person", "Associates": "contact", "Accounts": "company", "Req": "job", "TimesheetItems": "timesheet line"}
    say = lambda keys: ", ".join(f"{names.get(t, t)} {d} into {k}" for t, d, k in (x.split(":") for x in keys))  # noqa: E731
    parts = ([f"Merged duplicate {say(new)}"] if new else []) + ([f"Undid merge of {say(undone)}"] if undone else [])
    return "; ".join(parts) if parts else "Middle tier run"


_pending = threading.Event()


def apply_decisions_async():
    """A duplicate decision was saved: re-run the middle tier (merges) and the target in the background,
    then save a version. Several quick decisions are applied together in one run."""
    if _pending.is_set():
        return
    _pending.set()

    def go():
        TI = _tiers()
        with _lock:
            _pending.clear()
            try:
                TI.write(TI.MIDDLE)
                TI.run(TI.MIDDLE)
                TI.run(TI.TARGET)
                _ran.update({"middle", "target"})
                _rows.clear()
            except Exception as e:                       # noqa: BLE001
                print(f"[layers] applying decisions failed: {e}")
                return
            message = _run_message("middle")
        if message != "Middle tier run":
            versions.snapshot_async(message, wait_for=_lock)
    threading.Thread(target=go, daemon=True).start()


def _ensure(name: str):
    if name not in _ran:
        run(name)


def rows(name: str, key: str, limit: int = 100, q: str | None = None) -> dict:
    TI, layer = _layer(name)
    _ensure(name)
    with _lock:
        cache = _rows.setdefault(name, {})
        if key not in cache:
            cache[key] = TI.read(layer, key)
        data = cache[key]
    found = data
    if q:
        ql = q.lower()
        found = [r for r in data if any(v and ql in v.lower() for v in r.values())]
    return {"entity": key, "total": len(data), "matched": len(found), "rows": found[:limit]}


def summary(name: str) -> dict:
    TI, layer = _layer(name)
    _ensure(name)
    counts = {e.key: rows(name, e.key, limit=1)["total"] for e in layer.entities}
    return {"layer": name, "entities": counts}


def detail(name: str) -> dict:
    """Scripts and field expressions per entity (the developer view)."""
    TI, layer = _layer(name)
    o = TI.load_overrides()
    mine = o.get(name, {})
    cached = _rows.get(name, {})
    ents = []
    for e in layer.entities:
        ents.append({
            "key": e.key, "label": e.label, "table": f"{layer.schema}.{e.table}", "file": TI.script_name(layer, e),
            "sources": sorted({i.source.replace("{src}", "").split()[0] for i in e.inserts}),
            "rows": len(cached[e.key]) if e.key in cached else None,
            "inserts": [{"n": n, "source": i.source.replace("{src}", layer.src), "fields": [
                {"column": c, "expression": TI.expression(layer, e, n, c, o), "default": i.columns[c],
                 "overridden": TI.field_key(e.key, n, c) in mine}
                for c in i.columns]} for n, i in enumerate(e.inserts)],
            "sql": TI.insert_sql(layer, e, o),
        })
    src_db = layer.src.split(".")[0]
    return {"layer": name, "source_db": src_db, "db": layer.db, "entities": ents}


def set_field(name: str, key: str, n: int, column: str, expression: str | None) -> dict:
    """Override one field's expression (None = back to the default), then re-run that entity's script.
    If the script fails, the change is undone and the SQL Server error is raised."""
    TI, layer = _layer(name)
    e = layer.entity(key)
    if n >= len(e.inserts) or column not in e.inserts[n].columns:
        raise KeyError(column)
    with _lock:
        o = TI.load_overrides()
        before = dict(o.get(name, {}))
        fk = TI.field_key(key, n, column)
        default = e.inserts[n].columns[column]
        layer_o = o.setdefault(name, {})
        if expression is None or expression.strip() == "" or expression.strip() == default:
            layer_o.pop(fk, None)
        else:
            layer_o[fk] = expression.strip()
        TI.save_overrides(o)
        try:
            if name not in _ran:
                TI.run(layer)
                _ran.add(name)
            else:
                TI.run(layer, only=key, create=False)
        except Exception as ex:                    # noqa: BLE001 — undo, report the SQL error
            o[name] = before
            TI.save_overrides(o)
            msg = str(ex)
            raise ValueError(msg.split("]")[-1].split("(SQLExecDirectW)")[0].strip() or msg) from None
        TI.write(layer)
        _rows.get(name, {}).pop(key, None)
    what = "middle tier" if name == "middle" else "target"
    versions.snapshot_async(f"Changed {what} {e.table}.{column} to {expression.strip() if expression and expression.strip() else 'its default'}",
                            only=[(name, key)], wait_for=_lock)
    return detail(name)


def rejects() -> list[dict]:
    """Rows the target load rejected (not loaded) or flagged (loaded, needs a look)."""
    TI = _tiers()
    _ensure("target")
    return TI.rejects()
