"""
validation/validator.py

Runs the data-quality rules in validation/baseline_rules.py against either
  * the clean baseline CSVs      (sample_data/source/*.csv)            -- must be 0 violations
  * the legacy SQL Server DB     (Cobaltdesk_Legacy, with planted defects)

Both sources are loaded into an in-memory DuckDB with the column types from
`Source Schema.csv`, so exactly the same rules run against both.

CLI
  python -m validation.validator                      # validate the clean CSVs
  python -m validation.validator --source sqlserver   # run rules against the legacy DB
  python -m validation.validator --source sqlserver --score   # + score against the defect answer key
"""

from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sample_data"))

from build_source_db import DEFAULT_DB, DEFAULT_SERVER, SOURCE_DIR, load_schema  # noqa: E402
import dedupe_generated as dg                                                     # noqa: E402

from validation.baseline_rules import RULES, Rule                                  # noqa: E402

MANIFEST = ROOT / "sql" / "source" / "defect_manifest.csv"
EDGE_CASES = ROOT / "sql" / "source" / "edge_cases.csv"


def duck_type(sql_type: str) -> str:
    t = sql_type.upper()
    if t in ("INT", "BIT"):
        return "INTEGER"
    if t == "FLOAT":
        return "DOUBLE"
    if t.startswith("DECIMAL"):
        return t
    if t in ("DATETIME", "DATE", "TIME"):
        return {"DATETIME": "TIMESTAMP", "DATE": "DATE", "TIME": "TIME"}[t]
    return "VARCHAR"


def _load_csv_dir(con: duckdb.DuckDBPyConnection, folder: Path, schema: dict, lenient: bool = False):
    cast = "TRY_CAST" if lenient else "CAST"     # lenient (uploads): bad values become NULL instead of failing the load
    for table, cols in schema.items():
        path = folder / f"{table}.csv"
        # no CSV for this table: an empty, correctly typed table
        select = ", ".join(f'CAST(NULL AS {duck_type(c["type"])}) AS "{c["col"]}"' for c in cols)
        if path.exists() and path.stat().st_size:
            header = next(csv.reader(open(path, encoding="utf-8-sig")))
            select = ", ".join(
                (f'{cast}(NULLIF("{c["col"]}", \'\') AS {duck_type(c["type"])}) AS "{c["col"]}"' if c["col"] in header
                 else f'CAST(NULL AS {duck_type(c["type"])}) AS "{c["col"]}"') for c in cols)
            con.execute(f'CREATE TABLE "{table}" AS SELECT {select} FROM read_csv(\'{path.as_posix()}\', '
                        f"header=true, all_varchar=true, quote='\"', escape='\"')")
        else:
            con.execute(f'CREATE TABLE "{table}" AS SELECT {select} FROM (SELECT 1) WHERE false')


def _support_tables(con: duckdb.DuckDBPyConnection):
    genders = {}
    for grp in dg.GROUPS.values():
        genders.update({n: "F" for n in grp["F"]})
        genders.update({n: "M" for n in grp["M"]})
    genders.update({n: g for n, (_, g) in dg.FIRST_NAME_GROUP.items()})
    genders.update({n: "F" for n in dg.BRITISH_F})
    con.execute("CREATE TABLE first_name_gender (first_name VARCHAR, gender VARCHAR)")
    con.executemany("INSERT INTO first_name_gender VALUES (?, ?)", list(genders.items()))
    con.execute("CREATE TABLE edge_cases (person_id INTEGER, associate_id INTEGER, emp_profile_id INTEGER, \"case\" VARCHAR)")
    if EDGE_CASES.exists():
        rows = [(int(r["person_id"]), int(r["associate_id"] or 0) or None, int(r["emp_profile_id"] or 0) or None, r["case"])
                for r in csv.DictReader(open(EDGE_CASES, encoding="utf-8"))]
        con.executemany("INSERT INTO edge_cases VALUES (?, ?, ?, ?)", rows)


def load_csv_baseline(folder: Path = SOURCE_DIR, lenient: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    _load_csv_dir(con, folder, load_schema(), lenient)
    _support_tables(con)
    return con


def load_sqlserver(server: str = DEFAULT_SERVER, database: str = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    import pyodbc
    schema = load_schema()
    cn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};"
                        "Trusted_Connection=yes;", timeout=10)
    with tempfile.TemporaryDirectory() as tmp:
        for table, cols in schema.items():
            cur = cn.cursor()
            cur.execute(f"SELECT {', '.join('[' + c['col'] + ']' for c in cols)} FROM dbo.[{table}]")
            with open(Path(tmp) / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([c["col"] for c in cols])
                for row in cur.fetchall():
                    w.writerow(["" if v is None else (int(v) if isinstance(v, bool) else v) for v in row])
        cn.close()
        con = duckdb.connect()
        _load_csv_dir(con, Path(tmp), schema)
    _support_tables(con)
    return con


@dataclass
class Violation:
    rule: str
    category: str
    table: str
    pk: str
    detail: str


def run_rules(con: duckdb.DuckDBPyConnection, rules: list[Rule] = RULES) -> list[Violation]:
    out = []
    for r in rules:
        for row in con.execute(r.sql).fetchall():
            out.append(Violation(r.id, r.category, r.table, str(row[0]), str(row[1]) if len(row) > 1 else ""))
    return out


def score(violations: list[Violation]) -> dict:
    """Which planted defects (answer key) were found by at least one rule on the same table + key."""
    hits = {(v.table, v.pk) for v in violations}
    manifest = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
    found = [m for m in manifest if (m["table"], m["pk_value"]) in hits]
    missed = [m for m in manifest if (m["table"], m["pk_value"]) not in hits]
    planted = {(m["table"], m["pk_value"]) for m in manifest}
    unexplained = [v for v in violations if (v.table, v.pk) not in planted]
    return {"manifest": manifest, "found": found, "missed": missed, "unexplained": unexplained}


def _print_summary(violations: list[Violation]):
    by_rule = Counter(v.rule for v in violations)
    width = max(len(r.id) for r in RULES)
    for r in RULES:
        n = by_rule.get(r.id, 0)
        print(f"  {'FAIL' if n else 'ok  '}  {r.id:<{width}}  {n:>4}  {r.description}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["csv", "sqlserver"], default="csv")
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--database", default=DEFAULT_DB)
    ap.add_argument("--score", action="store_true", help="score findings against the defect answer key")
    args = ap.parse_args()

    con = load_csv_baseline() if args.source == "csv" else load_sqlserver(args.server, args.database)
    violations = run_rules(con)
    print(f"{len(RULES)} rules, {len(violations)} violations ({args.source})")
    _print_summary(violations)

    if args.score:
        s = score(violations)
        print(f"\nAnswer key: {len(s['found'])}/{len(s['manifest'])} planted defects found")
        cats = defaultdict(lambda: [0, 0])
        for m in s["manifest"]:
            cats[m["category"]][1] += 1
        for m in s["found"]:
            cats[m["category"]][0] += 1
        for c, (f, n) in sorted(cats.items()):
            print(f"  {'ok  ' if f == n else 'MISS'}  {c:<22} {f}/{n}")
        for m in s["missed"]:
            print(f"  missed {m['defect_id']} {m['category']} {m['table']}.{m['column']} pk={m['pk_value']}")
        print(f"Violations not in the answer key (collateral of planted defects): {len(s['unexplained'])}")
        sys.exit(1 if s["missed"] else 0)
    sys.exit(1 if violations and args.source == "csv" else 0)


if __name__ == "__main__":
    main()
