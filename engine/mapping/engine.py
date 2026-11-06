"""
mapping/engine.py

Core of the relational mapping: schemas, relationships, transform catalog,
the mapping file (mapping/migration_mapping.json) and the validator that
flags mappings that are not correct.

Used by
  * dashboard/app.py          — the mapping UI (edit, see flags, save)
  * mapping/generate_sql.py   — turns the saved mapping into T-SQL

Mapping file shape
{
  "_meta":  {...},
  "tables": [
    {
      "id": "Associates->Contact",
      "target_table": "Contact",
      "source_table": "Associates",                 # driving table, alias "s"
      "joins":  [{"alias": "p", "table": "Person", "type": "LEFT", "on": "p.Person_ID = s.Person_ID"}],
      "filter": "s.Deleted = 0",                    # optional T-SQL predicate
      "status": "draft" | "approved",
      "notes":  "",
      "columns": [
        {"target": "ID",        "source": "s.AssociateID", "transform": "key"},
        {"target": "FirstName", "source": "p.First_Name",  "transform": "direct"},
        {"target": "CompanyID", "source": "aa.AccountID",  "transform": "fk_lookup"},
        {"target": "Status",    "source": "s.Active",      "transform": "value_map",
         "params": {"map": {"1": "Active", "0": "Inactive"}, "default": null}},
        ...
      ]
    }
  ]
}
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sample_data"))
sys.path.insert(0, str(ROOT / "mapping"))

from build_source_db import load_schema as load_source_schema   # noqa: E402
from relationships import all_foreign_keys as source_fks         # noqa: E402
from target_relationships import TARGET_AUDIT_COLUMNS, TARGET_FOREIGN_KEYS  # noqa: E402

MAPPING_FILE = ROOT / "mapping" / "migration_mapping.json"
TARGET_SCHEMA_FILE = ROOT / "Target Schema.csv"
SOURCE_DB = "Cobaltdesk_Legacy"
TARGET_DB = "RecruitPlatform_Target"
DRIVING_ALIAS = "s"


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS & RELATIONSHIPS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Col:
    table: str
    name: str
    type: str
    pk: bool = False
    fk_to: tuple[str, str] | None = None     # (parent_table, parent_column)


@dataclass
class Schema:
    tables: dict[str, dict[str, Col]]         # table -> column -> Col (ordered)

    def pk(self, table: str) -> str | None:
        return next((c.name for c in self.tables.get(table, {}).values() if c.pk), None)

    def col(self, table: str, column: str) -> Col | None:
        return self.tables.get(table, {}).get(column)

    def children_of(self, table: str) -> list[Col]:
        return [c for cols in self.tables.values() for c in cols.values() if c.fk_to and c.fk_to[0] == table]


def load_target_schema() -> Schema:
    tables: dict[str, dict[str, Col]] = {}
    with open(TARGET_SCHEMA_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if not row or not row[0].strip():
                continue
            row += [""] * 5
            t, c, typ, key = row[0].strip(), row[1].strip(), row[2].strip().upper(), row[4].strip().upper()
            tables.setdefault(t, {})[c] = Col(t, c, typ, pk=(key == "PK"))
    for child, col, parent, pcol in TARGET_FOREIGN_KEYS:
        if col in tables.get(child, {}):
            tables[child][col].fk_to = (parent, pcol)
    for t, cols in tables.items():
        for c in cols.values():
            if c.name in TARGET_AUDIT_COLUMNS and not c.fk_to and t != "User":
                c.fk_to = ("User", "UserID")
    return Schema(tables)


def load_source_model() -> Schema:
    raw = load_source_schema()
    tables = {t: {c["col"]: Col(t, c["col"], c["type"], pk=c["key"].lower() == "primary key") for c in cs}
              for t, cs in raw.items()}
    for child, col, parent, pcol in source_fks(raw):
        if col in tables.get(child, {}):
            tables[child][col].fk_to = (parent, pcol)
    return Schema(tables)


# ══════════════════════════════════════════════════════════════════════════════
# TYPES
# ══════════════════════════════════════════════════════════════════════════════

def type_kind(t: str) -> tuple[str, int | None]:
    """('string', 50) / ('string', None)=MAX / ('int',) / ('decimal', (p, s)) ..."""
    t = (t or "").upper()
    m = re.match(r"N?VARCHAR\((\d+|MAX)\)", t)
    if m:
        return "string", (None if m.group(1) == "MAX" else int(m.group(1)))
    if t.startswith("DECIMAL"):
        p, s = (list(map(int, re.findall(r"\d+", t))) + [18, 0])[:2]
        return "decimal", (p, s)
    return {"INT": ("int", None), "BIT": ("bit", None), "FLOAT": ("float", None), "DATE": ("date", None),
            "DATETIME": ("datetime", None), "TIME": ("time", None)}.get(t, ("unknown", None))


# compatibility of a value of kind A stored into kind B: ok | info | warn | error
_COMPAT = {
    ("int", "int"): "ok", ("int", "decimal"): "ok", ("int", "float"): "ok", ("int", "string"): "info",
    ("int", "bit"): "warn",
    ("bit", "bit"): "ok", ("bit", "int"): "ok", ("bit", "string"): "warn",
    ("float", "float"): "ok", ("float", "decimal"): "warn", ("float", "int"): "warn", ("float", "string"): "warn",
    ("decimal", "decimal"): "ok", ("decimal", "float"): "info", ("decimal", "int"): "warn", ("decimal", "string"): "warn",
    ("date", "date"): "ok", ("date", "datetime"): "ok", ("date", "string"): "warn",
    ("datetime", "datetime"): "ok", ("datetime", "date"): "info", ("datetime", "string"): "warn",
    ("time", "time"): "ok", ("time", "string"): "warn",
    ("string", "string"): "ok",
}


def compat(src_kind: str, tgt_kind: str) -> str:
    if "unknown" in (src_kind, tgt_kind):
        return "warn"
    return _COMPAT.get((src_kind, tgt_kind), "error")


# ══════════════════════════════════════════════════════════════════════════════
# TRANSFORMS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Transform:
    name: str
    label: str
    needs_source: bool = True
    params: tuple[str, ...] = ()
    output: str | None = None      # output kind; None = same as source / target for key+fk
    help: str = ""


TRANSFORMS: dict[str, Transform] = {t.name: t for t in [
    Transform("direct", "Copy as is", help="Value copied unchanged (implicit conversion only)."),
    Transform("key", "Primary key (new ID)", output="target",
              help="Target PK. A new ID is generated per source row and recorded in mig.KeyMap so children can find it."),
    Transform("fk_lookup", "Foreign key (look up new ID)", output="target",
              help="Translates the legacy ID into the new ID of the parent row via mig.KeyMap. Rows whose parent is missing are rejected."),
    Transform("cast_to_nvarchar", "Cast to text", output="string"),
    Transform("cast_to_int", "Cast to integer", output="int", help="TRY_CAST; values that fail become NULL and are logged."),
    Transform("cast_to_decimal", "Cast to decimal", output="decimal"),
    Transform("cast_to_float", "Cast to float", output="float"),
    Transform("cast_to_date", "Cast to date (drop time)", output="date"),
    Transform("trim", "Trim spaces", output="string"),
    Transform("truncate", "Cut to target length (accept loss)", output="string",
              help="Explicitly accepts that longer values are cut to the target length. Each cut value is logged."),
    Transform("invert_bool", "Invert flag (1<->0)", output="bit"),
    Transform("value_map", "Map values (CASE)", params=("map", "default"), output="target",
              help='params: {"map": {"legacy": "new", ...}, "default": "..."}'),
    Transform("lookup", "Look up in legacy table", params=("table", "key", "value"), output="string",
              help='params: {"table": "Roles", "key": "Role_ID", "value": "Description"}'),
    Transform("coalesce", "First non-empty", params=("others",), help='params: {"others": ["s.ColB", "p.ColC"]}'),
    Transform("concat", "Join text", params=("parts", "sep"), needs_source=False, output="string",
              help='params: {"parts": ["p.First_Name", "p.Last_Name"], "sep": " "}'),
    Transform("constant", "Fixed value", params=("value",), needs_source=False, output="target"),
    Transform("custom", "Custom SQL expression", params=("sql",), needs_source=False, output="target",
              help="Raw T-SQL using the table aliases. Always flagged for review."),
]}


# ══════════════════════════════════════════════════════════════════════════════
# MAPPING FILE
# ══════════════════════════════════════════════════════════════════════════════

def load_mapping(path: Path = MAPPING_FILE) -> dict:
    if not path.exists():
        return {"_meta": {}, "tables": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_mapping(mapping: dict, path: Path = MAPPING_FILE, user: str = "ui"):
    mapping.setdefault("_meta", {})
    mapping["_meta"].update({"updated_at": datetime.now().isoformat(timespec="seconds"), "updated_by": user,
                             "source_db": SOURCE_DB, "target_db": TARGET_DB, "format": 2})
    mapping["tables"].sort(key=lambda m: (m["target_table"], m["source_table"]))
    path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def mapping_id(m: dict) -> str:
    return m.get("id") or f"{m['source_table']}->{m['target_table']}"


REF_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")


def aliases(m: dict) -> dict[str, str]:
    """alias -> source table for a table mapping."""
    out = {DRIVING_ALIAS: m["source_table"]}
    for j in m.get("joins", []) or []:
        out[j["alias"]] = j["table"]
    return out


def resolve_ref(m: dict, ref: str, src: Schema) -> Col | None:
    mt = REF_RE.match((ref or "").strip())
    if not mt:
        return None
    table = aliases(m).get(mt.group(1))
    return src.col(table, mt.group(2)) if table else None


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Flag:
    severity: str            # error | warn | info
    code: str
    target_table: str
    target_column: str
    mapping: str
    message: str
    hint: str = ""

    def as_dict(self):
        return asdict(self)


SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


@dataclass
class Context:
    src: Schema
    tgt: Schema
    mapping: dict
    data: "DataProbe | None" = None
    by_target: dict = field(default_factory=dict)       # target table -> [mappings]

    def __post_init__(self):
        for m in self.mapping.get("tables", []):
            self.by_target.setdefault(m["target_table"], []).append(m)

    def parent_sources(self, target_table: str) -> set[str]:
        """Legacy tables whose rows become rows of `target_table` (via key)."""
        return {m["source_table"] for m in self.by_target.get(target_table, [])}


def referenced_source_table(m: dict, ref: str, src: Schema) -> str | None:
    """Which legacy table does a source column point at? (declared FK, or the PK of an aliased table)."""
    c = resolve_ref(m, ref, src)
    if not c:
        return None
    if c.fk_to:
        return c.fk_to[0]
    if c.pk:
        return c.table
    return None


def output_kind(col: dict, m: dict, ctx: Context, tcol: Col | None) -> str | None:
    t = TRANSFORMS.get(col.get("transform", "direct"))
    if not t:
        return None
    if t.output == "target":
        return type_kind(tcol.type)[0] if tcol else None
    if t.output:
        return t.output
    c = resolve_ref(m, col.get("source", ""), ctx.src)
    return type_kind(c.type)[0] if c else None


def validate(mapping: dict, src: Schema | None = None, tgt: Schema | None = None,
             data: "DataProbe | None" = None) -> list[Flag]:
    src = src or load_source_model()
    tgt = tgt or load_target_schema()
    ctx = Context(src, tgt, mapping, data)
    flags: list[Flag] = []
    add = lambda sev, code, tt, tc, mid, msg, hint="": flags.append(Flag(sev, code, tt, tc, mid, msg, hint))

    # ── target model problems (not the mapping's fault, but they block FKs) ──
    for t, cols in tgt.tables.items():
        if not tgt.pk(t):
            add("info", "T00", t, "", "", f"Target table {t} has no primary key", "Rows cannot be referenced or deduplicated.")
        for c in cols.values():
            if c.fk_to:
                p = tgt.col(*c.fk_to)
                if not p:
                    add("warn", "T01", t, c.name, "", f"{t}.{c.name} references {c.fk_to[0]}.{c.fk_to[1]} which does not exist")
                elif type_kind(p.type)[0] != type_kind(c.type)[0]:
                    add("warn", "T02", t, c.name, "",
                        f"Target schema: {t}.{c.name} is {c.type} but {p.table}.{p.name} is {p.type}",
                        "The FK cannot be enforced in the target DB; values are converted on load.")

    seen_pairs = Counter((m["target_table"], m["source_table"], (m.get("filter") or "").strip())
                         for m in mapping.get("tables", []))
    for m in mapping.get("tables", []):
        mid, tt, st = mapping_id(m), m["target_table"], m["source_table"]
        if tt not in tgt.tables:
            add("error", "M01", tt, "", mid, f"Target table {tt} does not exist")
            continue
        if st not in src.tables:
            add("error", "M02", tt, "", mid, f"Source table {st} does not exist")
            continue
        if seen_pairs[(tt, st, (m.get("filter") or "").strip())] > 1:
            add("warn", "M08", tt, "", mid, f"{st} is mapped to {tt} more than once with the same filter",
                "Rows would be loaded twice. Give each mapping a different filter or remove one.")
        al = aliases(m)
        for j in m.get("joins", []) or []:
            if j.get("table") not in src.tables:
                add("error", "M03", tt, "", mid, f"Join table {j.get('table')} does not exist")
            if list(al).count(j.get("alias")) > 1 or j.get("alias") == DRIVING_ALIAS:
                add("error", "M03", tt, "", mid, f"Join alias '{j.get('alias')}' is reused")
            for a, c in re.findall(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", j.get("on", "")):
                if a not in al or not src.col(al[a], c):
                    add("error", "M03", tt, "", mid, f"Join condition refers to unknown column {a}.{c}")
        for a, c in re.findall(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", m.get("filter") or ""):
            if a not in al or not src.col(al[a], c):
                add("error", "M03", tt, "", mid, f"Filter refers to unknown column {a}.{c}")

        cols = m.get("columns", [])
        tpk = tgt.pk(tt)
        mapped_targets = Counter(c.get("target") for c in cols)
        pk_map = next((c for c in cols if c.get("target") == tpk), None)
        if tpk and not pk_map:
            add("error", "M04", tt, tpk, mid, f"Primary key {tt}.{tpk} is not mapped",
                "Map it with transform 'key' from the source table's primary key.")
        elif tpk and pk_map.get("transform") != "key":
            add("error", "M04", tt, tpk, mid, f"Primary key {tt}.{tpk} must use transform 'key' (is '{pk_map.get('transform')}')",
                "Legacy IDs are not reused; 'key' issues a new ID and records it in mig.KeyMap.")
        elif tpk:
            kc = resolve_ref(m, pk_map.get("source", ""), src)
            if kc and not (kc.table == st and kc.pk):
                add("warn", "M04", tt, tpk, mid, f"Key comes from {kc.table}.{kc.name}, not {st}'s primary key",
                    "Rows are only unique if that column is unique for the driving table.")
            if data and kc:
                d = data.duplicates(st, kc.name, m.get("filter"))
                if d:
                    add("error", "D04", tt, tpk, mid, f"{d} duplicate key values in {st}.{kc.name} — rows would collide")
        if m.get("status") != "approved":
            add("info", "M06", tt, "", mid, "Mapping not yet approved")

        for c in cols:
            tc_name = c.get("target", "")
            tcol = tgt.col(tt, tc_name)
            tr = TRANSFORMS.get(c.get("transform", "direct"))
            if not tcol:
                add("error", "C01", tt, tc_name, mid, f"Target column {tt}.{tc_name} does not exist")
                continue
            if mapped_targets[tc_name] > 1:
                add("error", "C02", tt, tc_name, mid, f"{tt}.{tc_name} is mapped more than once in this mapping")
            if not tr:
                add("error", "C04", tt, tc_name, mid, f"Unknown transform '{c.get('transform')}'",
                    "Pick a transform from the list, or use 'custom' with explicit SQL.")
                continue
            params = c.get("params") or {}
            missing = [p for p in tr.params if p not in params and p not in ("default", "sep")]
            if missing:
                add("error", "C04", tt, tc_name, mid, f"Transform '{tr.name}' needs parameter(s): {', '.join(missing)}", tr.help)
            scol = None
            if tr.needs_source:
                scol = resolve_ref(m, c.get("source", ""), src)
                if not scol:
                    add("error", "C03", tt, tc_name, mid,
                        f"Source '{c.get('source')}' is not a column of {', '.join(f'{a}={t}' for a, t in al.items())}",
                        "Use alias.Column, e.g. s.Account_name or a joined alias.")
                    continue
            for ref in (params.get("others") or []) + (params.get("parts") or []):
                if not resolve_ref(m, ref, src):
                    add("error", "C03", tt, tc_name, mid, f"Parameter refers to unknown column '{ref}'")
            if tr.name == "lookup" and params:
                lt = src.tables.get(params.get("table", ""))
                if not lt or params.get("key") not in lt or params.get("value") not in lt:
                    add("error", "C04", tt, tc_name, mid, f"Lookup {params.get('table')}.{params.get('key')}->{params.get('value')} does not exist")
            if tr.name == "custom":
                add("warn", "C10", tt, tc_name, mid, "Custom SQL expression — review by hand", params.get("sql", ""))

            # ── relational correctness ─────────────────────────────────────
            if tcol.fk_to and tr.name not in ("fk_lookup", "key"):
                if not (tr.name == "constant" and params.get("value") is None):
                    add("error", "C06", tt, tc_name, mid,
                        f"{tt}.{tc_name} is a foreign key to {tcol.fk_to[0]} but uses '{tr.name}'",
                        "Use 'fk_lookup' so the legacy ID is translated to the parent's new ID.")
            if tr.name == "fk_lookup":
                if not tcol.fk_to:
                    add("warn", "C07", tt, tc_name, mid, f"'fk_lookup' on {tt}.{tc_name}, which is not a foreign key")
                else:
                    parent = tcol.fk_to[0]
                    parents = ctx.parent_sources(parent)
                    ref_tbl = referenced_source_table(m, c.get("source", ""), src)
                    if not parents:
                        add("error", "C06", tt, tc_name, mid,
                            f"{tt}.{tc_name} references {parent}, but {parent} has no mapping",
                            f"Map a source table to {parent} first; otherwise every row is rejected.")
                    elif not ref_tbl:
                        add("error", "C06", tt, tc_name, mid,
                            f"{c.get('source')} is not a reference to any legacy table, so it cannot identify a {parent}",
                            f"{parent} is loaded from {', '.join(sorted(parents))}: map a column that references one of them.")
                    elif ref_tbl not in parents:
                        add("error", "C06", tt, tc_name, mid,
                            f"{c.get('source')} references {ref_tbl}, but {parent} is loaded from {', '.join(sorted(parents))}",
                            "The IDs come from a different legacy table, so the lookup would never match.")
                    elif data:
                        pm = [p for p in ctx.by_target[parent] if p["source_table"] == ref_tbl]
                        orphans = data.orphans(m, c.get("source", ""), ref_tbl, src.pk(ref_tbl), [p.get("filter") for p in pm])
                        if orphans:
                            add("warn", "D06", tt, tc_name, mid,
                                f"{orphans} row(s) reference a {ref_tbl} that is not loaded into {parent} — they will be rejected")
            elif scol and (scol.fk_to or scol.pk) and not tcol.fk_to and not tcol.pk and tr.name in ("direct", "cast_to_nvarchar", "cast_to_int"):
                add("warn", "C08", tt, tc_name, mid,
                    f"Legacy ID {scol.table}.{scol.name} copied into plain column {tt}.{tc_name}",
                    "Legacy IDs mean nothing in the target. Use a lookup to a readable value, or drop the column.")

            # ── types ──────────────────────────────────────────────────────
            if tr.name in ("key", "fk_lookup"):
                pass
            else:
                ok = output_kind(c, m, ctx, tcol)
                tk, tlen = type_kind(tcol.type)
                if ok:
                    level = compat(ok, tk)
                    if level in ("error", "warn"):
                        add(level, "C05", tt, tc_name, mid,
                            f"{(scol.type if scol else ok)} -> {tcol.type} via '{tr.name}' is {'not possible' if level == 'error' else 'lossy'}",
                            "Use a cast_* transform or a value_map." if level == "error" else "Check precision/format on a sample.")
                    elif level == "info" and ok != tk:
                        add("info", "C05", tt, tc_name, mid, f"{(scol.type if scol else ok)} -> {tcol.type}: implicit conversion")
                if scol and tk == "string" and tlen:
                    sk, slen = type_kind(scol.type)
                    if sk == "string" and (slen is None or slen > tlen) and tr.name in ("direct", "trim", "coalesce"):
                        n = data.too_long(scol.table, scol.name, tlen, m.get("filter") if scol.table == st else None) if data else None
                        if n:
                            add("error", "D05", tt, tc_name, mid,
                                f"{n} value(s) of {scol.table}.{scol.name} are longer than {tlen} characters and would be truncated")
                        elif n is None:
                            add("warn", "C05", tt, tc_name, mid, f"{scol.type} -> {tcol.type} may truncate (no data check run)")
                    if tr.name == "truncate" and data:
                        n = data.too_long(scol.table, scol.name, tlen, m.get("filter") if scol.table == st else None)
                        if n:
                            add("info", "D05", tt, tc_name, mid, f"Truncation accepted: {n} value(s) will be cut to {tlen} characters (logged)")
                if scol and data and tr.name in ("cast_to_int", "cast_to_decimal", "cast_to_float", "cast_to_date"):
                    n = data.cast_failures(scol.table, scol.name, tr.output)
                    if n:
                        add("warn", "D07", tt, tc_name, mid, f"{n} value(s) of {scol.table}.{scol.name} cannot be cast to {tr.output} and will be NULL")
                if tr.name == "value_map" and scol and data:
                    keys = {str(k) for k in (params.get("map") or {})}
                    unmapped = [v for v in data.distinct(scol.table, scol.name) if v is not None and str(v) not in keys]
                    if unmapped and params.get("default") is None:
                        add("warn", "D09", tt, tc_name, mid,
                            f"Values not covered by the map (will be NULL): {', '.join(map(str, unmapped[:8]))}"
                            + (" ..." if len(unmapped) > 8 else ""))
            if (c.get("confidence") or 1) < 0.9 and c.get("status") != "approved":
                add("warn", "C11", tt, tc_name, mid, f"Low confidence ({c.get('confidence')}) and not reviewed")

        # ── coverage ───────────────────────────────────────────────────────
        unmapped_t = [n for n in tgt.tables[tt] if n not in mapped_targets]
        if unmapped_t:
            add("info", "M10", tt, "", mid, f"{len(unmapped_t)} target column(s) left empty: {', '.join(unmapped_t)}")
        used = {resolve_ref(m, c.get("source", ""), src).name for c in cols
                if resolve_ref(m, c.get("source", ""), src) and resolve_ref(m, c.get("source", ""), src).table == st}
        dropped = [n for n in src.tables[st] if n not in used]
        if dropped:
            add("info", "M11", tt, "", mid, f"{len(dropped)} {st} column(s) not migrated: {', '.join(dropped)}")

    # ── table-level relational completeness ────────────────────────────────
    for tt, ms in ctx.by_target.items():
        for c in tgt.tables.get(tt, {}).values():
            if c.fk_to and c.fk_to[0] not in ctx.by_target and any(
                    col.get("target") == c.name for m in ms for col in m.get("columns", [])):
                pass   # already reported per column (C06)
    for t in tgt.tables:
        if t not in ctx.by_target:
            needed_by = sorted({ch.table for ch in tgt.children_of(t) if ch.table in ctx.by_target and any(
                col.get("target") == ch.name for m in ctx.by_target[ch.table] for col in m.get("columns", []))})
            if needed_by:
                add("error", "M07", t, "", "", f"{t} is not mapped but {', '.join(needed_by)} reference it",
                    f"Map a source table to {t}, or stop mapping those foreign keys.")
            else:
                add("info", "M09", t, "", "", f"{t} has no mapping (nothing will be migrated into it)")

    flags.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.target_table, f.target_column, f.code))
    return flags


def load_order(mapping: dict, tgt: Schema) -> list[str]:
    """Target tables in dependency order (parents first). Cycles are broken alphabetically."""
    mapped = {m["target_table"] for m in mapping.get("tables", [])}
    deps = {t: {c.fk_to[0] for c in tgt.tables[t].values() if c.fk_to and c.fk_to[0] in mapped and c.fk_to[0] != t}
            for t in mapped if t in tgt.tables}
    order, done = [], set()
    while len(done) < len(deps):
        ready = sorted(t for t in deps if t not in done and deps[t] <= done)
        if not ready:          # cycle: take the table with the fewest unmet deps
            ready = [min((t for t in deps if t not in done), key=lambda t: (len(deps[t] - done), t))]
        for t in ready:
            order.append(t)
            done.add(t)
    return order


# ══════════════════════════════════════════════════════════════════════════════
# DATA PROBE (data-driven checks, DuckDB over the legacy data)
# ══════════════════════════════════════════════════════════════════════════════

class DataProbe:
    """Answers data questions about the legacy source. `con` is a DuckDB connection with the
    legacy tables loaded (validation.validator.load_sqlserver / load_csv_baseline)."""

    def __init__(self, con):
        self.con = con
        self._cache: dict = {}

    def _q(self, key, sql):
        if key not in self._cache:
            try:
                self._cache[key] = self.con.execute(sql).fetchall()
            except Exception:
                self._cache[key] = None
        return self._cache[key]

    @staticmethod
    def _where(filter_sql: str | None) -> str:
        if not filter_sql:
            return ""
        return " WHERE " + re.sub(r"\bs\.", "", filter_sql)

    def too_long(self, table, col, n, filter_sql=None):
        r = self._q(("len", table, col, n, filter_sql),
                    f'SELECT COUNT(*) FROM "{table}"{self._where(filter_sql)}'
                    f'{" AND" if filter_sql else " WHERE"} length(CAST("{col}" AS VARCHAR)) > {n}')
        return r[0][0] if r else None

    def cast_failures(self, table, col, kind):
        duck = {"int": "INTEGER", "decimal": "DECIMAL(18,4)", "float": "DOUBLE", "date": "DATE"}.get(kind, "VARCHAR")
        r = self._q(("cast", table, col, kind),
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NOT NULL AND TRY_CAST("{col}" AS {duck}) IS NULL')
        return r[0][0] if r else None

    def distinct(self, table, col, limit=50):
        r = self._q(("distinct", table, col), f'SELECT DISTINCT "{col}" FROM "{table}" LIMIT {limit}')
        return [x[0] for x in r] if r else []

    def duplicates(self, table, col, filter_sql=None):
        r = self._q(("dup", table, col, filter_sql),
                    f'SELECT COUNT(*) - COUNT(DISTINCT "{col}") FROM "{table}"{self._where(filter_sql)}')
        return r[0][0] if r else 0

    def orphans(self, m, ref, parent_table, parent_pk, parent_filters):
        """Child rows whose referenced legacy row will not exist in the parent's load."""
        mt = REF_RE.match(ref)
        if not mt or not parent_pk:
            return None
        al = aliases(m)
        joins = " ".join(f'{j.get("type", "LEFT")} JOIN "{j["table"]}" {j["alias"]} ON {j["on"]}' for j in m.get("joins", []) or [])
        pf = [f for f in parent_filters if f]
        rewritten = ["(" + re.sub(r"\bs\.", "pp.", f) + ")" for f in pf]     # parent filters use alias s -> pp
        parent_where = (" WHERE " + " OR ".join(rewritten)) if pf and len(pf) == len(parent_filters) else ""
        where = f" AND ({m['filter']})" if m.get("filter") else ""
        sql = (f'SELECT COUNT(*) FROM "{al[DRIVING_ALIAS]}" s {joins} WHERE {ref} IS NOT NULL{where} '
               f'AND {ref} NOT IN (SELECT pp."{parent_pk}" FROM "{parent_table}" pp{parent_where})')
        r = self._q(("orph", json.dumps(m.get("joins")), m.get("filter"), ref, parent_table, tuple(pf)), sql)
        return r[0][0] if r else None
