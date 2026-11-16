"""
transform/build_dbt.py

Generates the dbt project from the mapping spec (spec/middle.yml, spec/target.yml) and the reviewer's
duplicate decisions. The spec is the source of truth; everything under dbt/models and dbt/seeds is
generated (do not edit by hand).

    dbt/models/sources.yml               the run's Parquet files (one per legacy table)
    dbt/models/staging/stg_<entity>.sql  source -> canonical shape (one SELECT per entity)
    dbt/models/mid/mid_<entity>.sql      the middle tier: staging with duplicate merges applied
    dbt/models/target/target_<t>.sql     middle tier -> target table; rows failing a check are left out
    dbt/models/audit/migration_rejects   every row rejected or flagged, with the reason
    dbt/models/target/schema.yml         tests: keys unique and not null, every link resolves
    dbt/seeds/merges.csv, merge_fields   the merges decided in Data quality -> Duplicates
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
DBT = HERE / "dbt"
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ENGINE / "sample_data"))
sys.path.insert(0, str(ENGINE / "mapping"))

# middle-tier entity -> (merge kind, its id column)
SELF_KIND = {"candidates": ("candidate", "candidate_id"), "contacts": ("contact", "contact_id"),
             "clients": ("client", "client_id"), "jobs": ("job", "job_id"), "timesheet_lines": ("timesheet_line", "line_id")}
FOREIGN = {"candidate_id": "candidate", "contact_id": "contact", "client_id": "client", "job_id": "job", "person_id": "candidate"}
LEGACY_KIND = {"Associates": "contact", "Accounts": "client", "Req": "job", "TimesheetItems": "timesheet_line"}

# target links that must resolve: (child table, column, parent table, parent key, where)
LINKS = [
    ("Placements", "ApplicantID", "Applicant", "ApplicantID", None), ("Placements", "PositionID", "Position", "ID", None),
    ("Position", "CompanyID", "Company", "ID", None), ("Position_Details", "PositionID", "Position", "ID", None),
    ("Offer", "PlacementID", "Placements", "ID", None), ("Deal", "PlacementID", "Placements", "ID", None),
    ("Contact", "CompanyID", "Company", "ID", None), ("Comms", "ObjectID", "Applicant", "ApplicantID", None),
    ("Notes", "ApplicantID", "Applicant", "ApplicantID", None), ("Notes", "ContactID", "Contact", "ID", None),
    ("Notes", "CompanyID", "Company", "ID", None), ("Notes", "PositionID", "Position", "ID", None),
    ("Position_Applicant", "ApplicantID", "Applicant", "ApplicantID", None), ("Position_Applicant", "PositionID", "Position", "ID", None),
    ("Work_History", "ApplicationID", "Applicant", "ApplicantID", None), ("References", "ApplicantID", "Applicant", "ApplicantID", None),
    ("Employment_Details", "ApplicantID", "Applicant", "ApplicantID", None),
    ("ApplicantAttachment", "ApplicantID", "Applicant", "ApplicantID", None), ("ContactAttachment", "ContactID", "Contact", "ID", None),
    ("PositionAttachment", "PositionID", "Position", "ID", None),
    ("TaskItem", "ObjectID", "Applicant", "ApplicantID", "ObjectType = 'Applicant'"),
    ("TaskItem", "ObjectID", "Contact", "ID", "ObjectType = 'Contact'"),
]


OVERRIDES = HERE / "spec" / "overrides.json"


def load_overrides() -> dict:
    return json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}


def save_overrides(o: dict):
    o = {layer: v for layer, v in o.items() if v}
    OVERRIDES.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_spec(layer: str, with_overrides: bool = True) -> dict:
    """The mapping spec for a layer; developer field edits (spec/overrides.json, key:select:column) applied."""
    spec = yaml.safe_load((HERE / "spec" / f"{layer}.yml").read_text(encoding="utf-8"))
    if with_overrides:
        for k, expr in load_overrides().get(layer, {}).items():
            key, n, col = k.split(":", 2)
            ent = next((e for e in spec["entities"] if e["key"] == key), None)
            if ent and int(n) < len(ent["selects"]) and col in ent["selects"][int(n)]["columns"]:
                ent["selects"][int(n)]["columns"][col] = expr
    return spec


def _duck_type(t: str) -> str:
    t = t.upper().strip()
    if t.startswith(("NVARCHAR", "VARCHAR", "NCHAR", "CHAR", "TEXT")):
        return "VARCHAR"
    if t.startswith("BIT"):
        return "BOOLEAN"
    if t.startswith("DATETIME"):
        return "TIMESTAMP"
    if t.startswith("FLOAT"):
        return "DOUBLE"
    if t in ("INT", "INTEGER"):
        return "INTEGER"
    return t


def resolved_merges(source_dir: Path | None) -> list[dict]:
    """The reviewer's merges as (kind, duplicate, survivor, columns taken from the duplicate). A merged person
    who is a client contact is merged as a contact (by contact id), any other person as a candidate."""
    from validation.duplicates import merges
    decided = merges("legacy")
    contact_of: dict[str, str] = {}
    if source_dir and (source_dir / "Associates.parquet").exists():
        import duckdb
        rows = duckdb.sql(f"SELECT CAST(Person_ID AS VARCHAR), CAST(MIN(AssociateID) AS VARCHAR) FROM "
                          f"read_parquet('{(source_dir / 'Associates.parquet').as_posix()}') GROUP BY Person_ID").fetchall()
        contact_of = {p: a for p, a in rows}
    out = []
    for m in decided:
        keep, dup = m["survivor"], m["duplicate"]
        if m["table"] == "Person":
            if keep in contact_of and dup in contact_of:
                kind, keep, dup = "contact", contact_of[keep], contact_of[dup]
            else:
                kind = "candidate"
        elif m["table"] in LEGACY_KIND:
            kind = LEGACY_KIND[m["table"]]
        else:
            continue
        out.append({"kind": kind, "duplicate": dup, "survivor": keep, "take": m["take_from_duplicate"]})
    return out


def _src(sql: str, layer: str, tables: dict[str, str]) -> str:
    """src__X -> {{ source('legacy', 'X') }};  mid__X -> {{ ref('mid_<key>') }}"""
    sql = re.sub(r"\bsrc__(\w+)", lambda m: "{{ source('legacy', '" + m.group(1) + "') }}", sql)
    return re.sub(r"\bmid__(\w+)", lambda m: "{{ ref('mid_" + tables[m.group(1)] + "') }}", sql)


def _select(sel: dict, layer: str, tables: dict, types: dict | None = None, keep_checks: bool = False) -> str:
    cols = []
    for c, ex in sel["columns"].items():
        e = _src(str(ex), layer, tables)
        cols.append(f"    TRY_CAST({e} AS {types[c]}) AS {c}" if types and c in types else f"    {e} AS {c}")
    sql = "SELECT\n" + ",\n".join(cols) + f"\nFROM {_src(sel['from'], layer, tables)}"
    for j in sel.get("joins") or []:
        sql += "\n" + _src(j, layer, tables)
    conds = [f"({_src(sel['where'], layer, tables)})"] if sel.get("where") else []
    if keep_checks:
        conds += [f"({_src(c['condition'], layer, tables)})" for c in sel.get("checks", []) if c["action"] == "reject"]
    if conds:
        sql += "\nWHERE " + "\n  AND ".join(conds)
    return sql


def build(source_dir: Path | None = None) -> dict:
    from engine import load_target_schema
    middle, target = load_spec("middle"), load_spec("target")
    tables = {e["table"]: e["key"] for e in middle["entities"]}
    tgt_schema = load_target_schema()

    for sub in ("models", "seeds"):
        shutil.rmtree(DBT / sub, ignore_errors=True)
        (DBT / sub).mkdir(parents=True)
    for sub in ("staging", "mid", "target", "audit"):
        (DBT / "models" / sub).mkdir()

    # sources: the run's Parquet files
    from build_source_db import load_schema
    legacy = sorted(load_schema())
    (DBT / "models" / "sources.yml").write_text(yaml.safe_dump({"version": 2, "sources": [{
        "name": "legacy", "meta": {"external_location": "{{ env_var('MIGRYR_SOURCE_DIR') }}/{name}.parquet"},
        "tables": [{"name": t} for t in legacy]}]}, sort_keys=False), encoding="utf-8")

    # seeds: the duplicate merges
    merges = resolved_merges(source_dir)
    with open(DBT / "seeds" / "merges.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind", "duplicate", "survivor"])
        for m in merges:
            w.writerow([m["kind"], m["duplicate"], m["survivor"]])
    fields: list[tuple] = []
    for m in merges:
        ent = next((k for k, (kind, _) in SELF_KIND.items() if kind == m["kind"]), None)
        if not ent:
            continue
        spec = next(e for e in middle["entities"] if e["key"] == ent)
        for col, ex in spec["selects"][0]["columns"].items():
            mm = re.fullmatch(r"\w+\.(\w+)", str(ex))
            if mm and mm.group(1) in m["take"]:
                fields.append((m["kind"], m["survivor"], m["duplicate"], col))
    with open(DBT / "seeds" / "merge_fields.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind", "survivor", "duplicate", "column_name"])
        w.writerows(fields)
    picked = {(k, c) for k, _, _, c in fields}

    # staging + middle tier
    for e in middle["entities"]:
        key, types = e["key"], e.get("types") or {}
        types = {c: _duck_type(t) for c, t in types.items()}
        body = "\nUNION ALL\n".join(_select(s, "middle", tables, types) for s in e["selects"])
        (DBT / "models" / "staging" / f"stg_{key}.sql").write_text(
            body + "\n", encoding="utf-8")
        kind, idc = SELF_KIND.get(key, (None, None))
        cols = list(e["selects"][0]["columns"])
        out = []
        for c in cols:
            if c == idc:
                out.append(f"    s.{c}")
            elif kind and (kind, c) in picked:
                out.append(f"    COALESCE((SELECT d.{c} FROM {{{{ ref('merge_fields') }}}} f JOIN {{{{ ref('stg_{key}') }}}} d ON d.{idc} = f.duplicate "
                           f"WHERE f.kind = '{kind}' AND f.survivor = s.{idc} AND f.column_name = '{c}' LIMIT 1), s.{c}) AS {c}")
            elif c in FOREIGN and c != idc:
                out.append(f"    COALESCE((SELECT m.survivor FROM {{{{ ref('merges') }}}} m WHERE m.kind = '{FOREIGN[c]}' AND m.duplicate = s.{c}), s.{c}) AS {c}")
            elif c == "entity_id" and "entity_type" in cols:
                out.append(f"    COALESCE((SELECT m.survivor FROM {{{{ ref('merges') }}}} m WHERE m.kind = s.entity_type AND m.duplicate = s.entity_id), s.entity_id) AS entity_id")
            else:
                out.append(f"    s.{c}")
        sql = (f"{{{{ config(alias='{e['table']}') }}}}\n"
               f"SELECT\n" + ",\n".join(out) + f"\nFROM {{{{ ref('stg_{key}') }}}} s")
        if kind:
            sql += f"\nWHERE s.{idc} NOT IN (SELECT duplicate FROM {{{{ ref('merges') }}}} WHERE kind = '{kind}')"
        if key == "consents":   # one consent per person after merges: the survivor's own row wins
            sql += ("\nQUALIFY ROW_NUMBER() OVER (PARTITION BY COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m "
                    "WHERE m.kind = 'candidate' AND m.duplicate = s.person_id), s.person_id) "
                    "ORDER BY CASE WHEN s.person_id IN (SELECT survivor FROM {{ ref('merges') }}) THEN 0 ELSE 1 END, s.consent_id) = 1")
        (DBT / "models" / "mid" / f"mid_{key}.sql").write_text(sql + "\n", encoding="utf-8")

    # target + rejects
    rejects = []
    tests = []
    for e in target["entities"]:
        t = e["table"]
        ttypes = {c.name: _duck_type(c.type) for c in tgt_schema.tables[t].values()}
        body = "\nUNION ALL\n".join(_select(s, "target", tables, ttypes, keep_checks=True) for s in e["selects"])
        (DBT / "models" / "target" / f"target_{t.lower()}.sql").write_text(
            f"{{{{ config(alias='{t}') }}}}\n" + body + "\n", encoding="utf-8")
        for s in e["selects"]:
            key_expr = _src(str(next(iter(s["columns"].values()))), "target", tables)
            base = [f"({_src(s['where'], 'target', tables)})"] if s.get("where") else []
            keeps = [f"({_src(c['condition'], 'target', tables)})" for c in s.get("checks", []) if c["action"] == "reject"]
            for c in s.get("checks", []):
                conds = base + (keeps if c["action"] == "flag" else []) + [f"NOT ({_src(c['condition'], 'target', tables)})"]
                reason = c["reason"].replace("'", "''")
                rejects.append(f"SELECT '{t}' AS target_table, CAST({key_expr} AS VARCHAR) AS source_key, "
                               f"'{'rejected' if c['action'] == 'reject' else 'flagged'}' AS action, '{reason}' AS reason\n"
                               f"FROM {_src(s['from'], 'target', tables)}\n" + "\n".join(_src(j, 'target', tables) for j in s.get("joins") or [])
                               + "\nWHERE " + "\n  AND ".join(conds))
        pk = next((c.name for c in tgt_schema.tables[t].values() if c.pk), None)
        cols_tests = {}
        if pk:
            cols_tests[pk] = ["not_null", "unique"]
        for child, col, parent, pkey, where in LINKS:
            if child == t:
                rel = {"relationships": {"arguments": {"to": f"ref('target_{parent.lower()}')", "field": pkey}}}
                if where:
                    rel["relationships"]["config"] = {"where": where}
                cols_tests.setdefault(col, []).append(rel)
        tests.append({"name": f"target_{t.lower()}", "columns": [{"name": c, "data_tests": v} for c, v in cols_tests.items()]})
    (DBT / "models" / "audit" / "migration_rejects.sql").write_text(
        ("\nUNION ALL\n".join(rejects) if rejects else "SELECT NULL AS target_table, NULL AS source_key, NULL AS action, NULL AS reason WHERE FALSE") + "\n",
        encoding="utf-8")
    (DBT / "models" / "target" / "schema.yml").write_text(yaml.safe_dump({"version": 2, "models": tests}, sort_keys=False), encoding="utf-8")
    return {"middle": len(middle["entities"]), "target": len(target["entities"]), "merges": len(merges), "checks": len(rejects)}


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]) if len(sys.argv) > 1 else None)))
