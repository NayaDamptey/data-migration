"""
privacy/pii.py

Personal data (PII) in the migration: which fields hold it, and masking it wherever data is shown.

Tags
    Every middle-tier field can carry a PII category. Tags are suggested automatically, from the column
    name and from Microsoft Presidio's pattern detectors run on sample values (email, phone, UK NI number,
    UK postcode, IBAN, plus sort code and date-of-birth rules), then confirmed or changed by a person.
    They live with the mapping spec (transform/spec/pii.yml). Source and target fields inherit the tag of
    the middle-tier field they feed or are fed by; source columns that no field reads are tagged from
    their name and values.

Masking
    High-sensitivity categories (date of birth, NI number, bank account, sort code) are masked by default
    on every page: only the last two characters stay, e.g. 'WP963308B' -> '•••••••8B'. Other personal data
    (names, contact details, addresses) is shown, since reviewers need it to check records.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
TAGS_FILE = ENGINE / "transform" / "spec" / "pii.yml"

CATEGORIES = {
    "name": ("Name", "personal"),
    "email": ("Email", "personal"),
    "phone": ("Phone", "personal"),
    "address": ("Address", "personal"),
    "free_text": ("Free text (may mention people)", "personal"),
    "dob": ("Date of birth", "high"),
    "ni_number": ("NI number", "high"),
    "bank_account": ("Bank account", "high"),
    "sort_code": ("Sort code", "high"),
}
HIGH = {k for k, (_, level) in CATEGORIES.items() if level == "high"}

# column name -> category (first match wins)
NAME_RULES = [
    (r"(^|_)(dob|date_?of_?birth|birth_?date)($|_)", "dob"),
    (r"(^|_)(ni|nino|ni_?number|national_?insurance)($|_)", "ni_number"),
    (r"sort_?code", "sort_code"),
    (r"bank|iban|account_?number|acc_?no", "bank_account"),
    (r"e_?mail", "email"),
    (r"phone|mobile|telephone|(^|_)tel($|_)|fax", "phone"),
    (r"address_?line|postcode|zip_?code|post_?code", "address"),
    (r"(^|_)(first|last|middle|full|sur|fore)_?name($|_)|^fullname$|^(first|last)name$", "name"),
    (r"(^|_)(body|notes?|notetext|subject|feedback|reference(_text)?|profile_?notes)$", "free_text"),
]


def category_from_name(column: str) -> str | None:
    c = column.lower()
    if re.search(r"(_ok|_flag|_consent|_opt_?in|_opt_?out)$|^(is|has)_", c):   # yes/no flags about a value, not the value
        return None
    for pattern, cat in NAME_RULES:
        if re.search(pattern, c):
            return cat
    return None


_recognizers = None


def _detectors():
    """Presidio pattern recognizers (no language model needed), plus two UK rules of our own."""
    global _recognizers
    if _recognizers is None:
        from presidio_analyzer import Pattern, PatternRecognizer
        from presidio_analyzer.predefined_recognizers import (EmailRecognizer, IbanRecognizer, PhoneRecognizer,
                                                              UkNinoRecognizer, UkPostcodeRecognizer)
        sort_code = PatternRecognizer(supported_entity="UK_SORT_CODE",
                                      patterns=[Pattern("sort code", r"^\d{2}-\d{2}-\d{2}$", 0.7)])
        _recognizers = [(EmailRecognizer(), "EMAIL_ADDRESS", "email"),
                        (PhoneRecognizer(supported_regions=("GB",)), "PHONE_NUMBER", "phone"),
                        (UkNinoRecognizer(), "UK_NINO", "ni_number"),
                        (UkPostcodeRecognizer(), "UK_POSTCODE", "address"),
                        (IbanRecognizer(), "IBAN_CODE", "bank_account"),
                        (sort_code, "UK_SORT_CODE", "sort_code")]
    return _recognizers


def category_from_values(values: list) -> tuple[str | None, float]:
    """The category most sample values match, and the share that match (Presidio detectors)."""
    vals = [str(v).strip() for v in values if v is not None and str(v).strip()][:50]
    if not vals:
        return None, 0.0
    best, share = None, 0.0
    for rec, entity, cat in _detectors():
        hits = 0
        for v in vals:
            res = rec.analyze(v, [entity], None)
            if any(r.score >= 0.4 and r.end - r.start >= len(v) * 0.6 for r in res):
                hits += 1
        if hits / len(vals) > share:
            best, share = cat, hits / len(vals)
    return (best, share) if share >= 0.6 else (None, share)


def suggest(column: str, values: list) -> dict | None:
    """A suggested tag for one field: from its name, confirmed or found by its values."""
    by_name = category_from_name(column)
    by_value, share = category_from_values(values)
    if by_name and (by_value in (None, by_name)):
        return {"category": by_name, "why": "column name" + (f" and {round(share * 100)}% of sample values" if by_value else "")}
    if by_value:
        return {"category": by_value, "why": f"{round(share * 100)}% of sample values look like {CATEGORIES[by_value][0].lower()}"}
    if by_name:
        return {"category": by_name, "why": "column name"}
    return None


# ── tags (with the mapping spec) ─────────────────────────────────────────────
def load_tags() -> dict:
    """{entity: {column: {category, status: suggested|confirmed, why}}} for the middle tier."""
    return (yaml.safe_load(TAGS_FILE.read_text(encoding="utf-8")) or {}) if TAGS_FILE.exists() else {}


def save_tags(tags: dict):
    TAGS_FILE.write_text(yaml.safe_dump(tags, sort_keys=True, allow_unicode=True), encoding="utf-8")


def suggest_all(middle_spec: dict, sample) -> dict:
    """Suggest tags for every middle-tier field. sample(entity_key, column) -> list of values.
    Confirmed tags are kept as they are."""
    tags = load_tags()
    for e in middle_spec["entities"]:
        cur = tags.setdefault(e["key"], {})
        for col in e["selects"][0]["columns"]:
            if cur.get(col, {}).get("status") == "confirmed":
                continue
            s = suggest(col, sample(e["key"], col))
            if s:
                cur[col] = {"category": s["category"], "status": "suggested", "why": s["why"]}
            else:
                cur.pop(col, None)
        if not cur:
            tags.pop(e["key"], None)
    save_tags(tags)
    return tags


def set_tag(entity: str, column: str, category: str | None) -> dict:
    """A person confirms, changes or removes a field's tag (category None = not personal data)."""
    tags = load_tags()
    cur = tags.setdefault(entity, {})
    cur[column] = {"category": category, "status": "confirmed", "why": "set by a person"}
    save_tags(tags)
    return tags


def middle_categories(tags: dict | None = None) -> dict[str, dict[str, str]]:
    tags = load_tags() if tags is None else tags
    return {e: {c: t["category"] for c, t in cols.items() if t.get("category")} for e, cols in tags.items()}


def _aliases(sel: dict, prefix: str) -> dict[str, str]:
    out = {}
    for frag in [sel["from"], *(sel.get("joins") or [])]:
        if "LATERAL" in frag:
            continue
        m = re.search(prefix + r"(\w+)\s+AS\s+(\w+)", frag)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def target_categories(target_spec: dict, middle_spec: dict, tags: dict | None = None) -> dict[str, dict[str, str]]:
    """A target field inherits the category of the middle-tier field(s) its expression reads."""
    mid = middle_categories(tags)
    key_of = {e["table"]: e["key"] for e in middle_spec["entities"]}
    out: dict[str, dict[str, str]] = {}
    for e in target_spec["entities"]:
        for sel in e["selects"]:
            al = _aliases(sel, r"mid__")
            for col, ex in sel["columns"].items():
                for a, c in re.findall(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", str(ex)):
                    cat = mid.get(key_of.get(al.get(a, ""), ""), {}).get(c)
                    if cat:
                        out.setdefault(e["key"], {})[col] = cat
                        break
    return out


def source_categories(middle_spec: dict, schema: dict, tags: dict | None = None) -> dict[str, dict[str, str]]:
    """Legacy columns: the category of the middle-tier field reading them; otherwise by column name."""
    mid = middle_categories(tags)
    out: dict[str, dict[str, str]] = {}
    for t, cols in schema.items():
        for c in cols:
            cat = category_from_name(c["col"])
            if cat:
                out.setdefault(t, {})[c["col"]] = cat
    for e in middle_spec["entities"]:
        for sel in e["selects"]:
            al = _aliases(sel, r"src__")
            for col, ex in sel["columns"].items():
                cat = mid.get(e["key"], {}).get(col)
                m = re.fullmatch(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)", str(ex).strip())
                if cat and m and m.group(1) in al:
                    out.setdefault(al[m.group(1)], {})[m.group(2)] = cat
    return out


# ── masking ──────────────────────────────────────────────────────────────────
def mask(value) -> str | None:
    """Keep the last two letters or digits; the rest become •, separators kept."""
    if value is None:
        return None
    s = str(value)
    alnum = [i for i, ch in enumerate(s) if ch.isalnum()]
    keep = set(alnum[-2:])
    return "".join(ch if (i in keep or not ch.isalnum()) else "•" for i, ch in enumerate(s))


def mask_row(row: dict, categories: dict[str, str]) -> dict:
    """A copy of row with high-sensitivity fields masked."""
    return {c: (mask(v) if categories.get(c) in HIGH and v is not None else v) for c, v in row.items()}
