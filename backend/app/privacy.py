"""Personal data for the API (engine/privacy/pii.py): PII tags on the mapping spec, and masking of
high-sensitivity values (date of birth, NI number, bank account, sort code) in everything the API returns.

Tags are suggested the first time they are needed (from the current run's middle-tier values) and then
confirmed or changed in the developer view.
"""

from __future__ import annotations

import re
import sys
import threading

from app import engine_bridge as bridge

_lock = threading.Lock()


def _pii():
    p = str(bridge.ENGINE / "privacy")
    if p not in sys.path:
        sys.path.insert(0, p)
    import pii
    return pii


def _specs():
    from app import layers
    B, _ = layers._engine()
    return B.load_spec("middle"), B.load_spec("target")


def ensure_tags() -> dict:
    """The tags; suggested from the current run's values the first time."""
    P = _pii()
    with _lock:
        tags = P.load_tags()
        if not tags:
            from app import layers
            middle, _ = _specs()
            sample = lambda key, col: [r.get(col) for r in layers.rows("middle", key, limit=50, raw=True)["rows"]]   # noqa: E731
            tags = P.suggest_all(middle, sample)
    return tags


def resuggest() -> dict:
    from app import layers
    P = _pii()
    middle, _ = _specs()
    with _lock:
        sample = lambda key, col: [r.get(col) for r in layers.rows("middle", key, limit=50, raw=True)["rows"]]   # noqa: E731
        return P.suggest_all(middle, sample)


_cache: dict = {}


def _all() -> dict:
    """Categories for every layer, worked out once and kept until a tag or the spec changes."""
    P = _pii()
    tags = ensure_tags()
    from app import layers
    B, _ = layers._engine()
    stamp = (P.TAGS_FILE.stat().st_mtime if P.TAGS_FILE.exists() else 0,
             max((f.stat().st_mtime for f in (B.HERE / "spec").glob("*")), default=0))
    if _cache.get("stamp") != stamp:
        middle, target = _specs()
        _cache.update(stamp=stamp, middle=P.middle_categories(tags), target=P.target_categories(target, middle, tags),
                      source=P.source_categories(middle, bridge._engine()[3], tags))
    return _cache


def categories(layer: str, key: str) -> dict[str, str]:
    """column -> category for a middle-tier entity ('middle'), a target table ('target') or a legacy table."""
    a = _all()
    return a.get(layer if layer in ("middle", "target") else "source", {}).get(key, {})


def mask_rows(layer: str, key: str, rows: list[dict]) -> list[dict]:
    P = _pii()
    cats = categories(layer, key)
    if not any(c in P.HIGH for c in cats.values()):
        return rows
    return [P.mask_row(r, cats) for r in rows]


def mask_value(layer: str, key: str, column: str, value):
    P = _pii()
    return P.mask(value) if categories(layer, key).get(column) in P.HIGH and value is not None else value


def masks_detail(table: str, sql: str) -> bool:
    """Does a data quality rule's detail text show a high-sensitivity column of its table?"""
    P = _pii()
    high = [c for c, cat in categories("source", table).items() if cat in P.HIGH]
    return any(re.search(rf"\b{re.escape(c)}\b", sql) for c in high)


def summary() -> dict:
    """Every middle-tier field with its tag (for the developer view and the PII overview)."""
    P = _pii()
    tags = ensure_tags()
    middle, _ = _specs()
    fields = []
    for e in middle["entities"]:
        for col in e["selects"][0]["columns"]:
            t = tags.get(e["key"], {}).get(col)
            if t:
                label, level = P.CATEGORIES.get(t["category"], (None, None)) if t.get("category") else (None, None)
                fields.append({"entity": e["key"], "column": col, "category": t.get("category"), "label": label,
                               "level": level, "status": t.get("status"), "why": t.get("why")})
    return {"categories": [{"key": k, "label": v[0], "level": v[1]} for k, v in P.CATEGORIES.items()],
            "fields": fields,
            "to_confirm": sum(1 for f in fields if f["status"] == "suggested"),
            "masked": sum(1 for f in fields if f["category"] in P.HIGH)}


def set_tag(entity: str, column: str, category: str | None) -> dict:
    P = _pii()
    if category is not None and category not in P.CATEGORIES:
        raise ValueError(f"Unknown category {category!r}")
    middle, _ = _specs()
    e = next((x for x in middle["entities"] if x["key"] == entity), None)
    if e is None or column not in e["selects"][0]["columns"]:
        raise KeyError(f"{entity}.{column}")
    ensure_tags()
    with _lock:
        P.set_tag(entity, column, category)
    return summary()
