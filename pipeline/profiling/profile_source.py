"""Profile a folder of source CSV files with DuckDB.

Produces the evidence the AI mapper needs: per-table row counts, per-column
null rates, distinct counts, lengths, top values, masked samples, detected
patterns, likely primary keys and likely foreign keys.

Usage:
    python profile_source.py <folder_of_csvs> [--out profile.json] [--samples 10]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb

PATTERNS = {
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "uk_phone": re.compile(r"^(\+44\s?|0)(\d[\s-]?){9,10}$"),
    "uk_postcode": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$", re.I),
    "url": re.compile(r"^(https?://)?([\w-]+\.)+[a-z]{2,}(/\S*)?$", re.I),
    "date_dmy": re.compile(r"^\d{1,2}/\d{1,2}/\d{4}"),
    "date_iso": re.compile(r"^\d{4}-\d{2}-\d{2}"),
    "money": re.compile(r"^£?\d{1,3}(,?\d{3})*(\.\d{2})?$"),
    "integer": re.compile(r"^-?\d+$"),
    "boolean": re.compile(r"^(true|false|yes|no|y|n|0|1)$", re.I),
    "rich_text": re.compile(r"(\{\\rtf|<[a-z][^>]*>)", re.I),
}
PATTERN_THRESHOLD = 0.8   # share of non-null values that must match
FK_THRESHOLD = 0.95       # share of values that must exist in the other key


def mask(value: str, kind: str | None) -> str:
    """Mask personal data before it can be sent to an LLM."""
    if value is None:
        return value
    if kind == "email":
        local, _, domain = value.partition("@")
        return f"{local[:1]}****@{domain}"
    if kind == "uk_phone":
        return value[:4] + "*" * max(len(value) - 7, 0) + value[-3:]
    return value


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def profile_column(con, table: str, col: str, rows: int, n_samples: int) -> dict:
    t, c = q(table), q(col)
    nulls, distinct, min_len, max_len = con.execute(
        f"""SELECT count(*) FILTER (WHERE {c} IS NULL OR trim({c}::VARCHAR) = ''),
                   count(DISTINCT {c}),
                   min(length({c}::VARCHAR)), max(length({c}::VARCHAR))
            FROM {t}"""
    ).fetchone()
    values = [
        r[0] for r in con.execute(
            f"""SELECT {c}::VARCHAR FROM {t}
                WHERE {c} IS NOT NULL AND trim({c}::VARCHAR) <> ''
                USING SAMPLE 500 ROWS"""
        ).fetchall()
    ]
    detected = []
    for name, rx in PATTERNS.items():
        if values and sum(bool(rx.search(v.strip())) for v in values) / len(values) >= PATTERN_THRESHOLD:
            detected.append(name)
    # Mixed date formats in one column (common in older CRMs)
    if values and "date_dmy" not in detected and "date_iso" not in detected:
        dated = sum(bool(PATTERNS["date_dmy"].search(v) or PATTERNS["date_iso"].search(v)) for v in values)
        if dated / len(values) >= PATTERN_THRESHOLD:
            detected.append("date_mixed_formats")
    kind = next((k for k in ("email", "uk_phone") if k in detected), None)
    top = con.execute(
        f"""SELECT {c}::VARCHAR AS v, count(*) AS n FROM {t}
            WHERE {c} IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT 10"""
    ).fetchall()
    non_null = rows - nulls
    return {
        "column": col,
        "null_rate": round(nulls / rows, 4) if rows else None,
        "distinct": distinct,
        "unique": non_null > 0 and distinct == non_null and nulls == 0,
        "min_length": min_len,
        "max_length": max_len,
        "patterns": detected,
        # top values only make sense for low-cardinality (enum-like) columns
        "top_values": [{"value": mask(v, kind), "count": n} for v, n in top] if distinct <= 50 else [],
        "samples": [mask(v, kind) for v in values[:n_samples]],
    }


def find_foreign_keys(con, tables: dict) -> list[dict]:
    # Only a table's likely primary key can be the target of a foreign key.
    keys = [(t, info["likely_primary_key"]) for t, info in tables.items() if info["likely_primary_key"]]
    fks = []
    for table, info in tables.items():
        for col in info["columns"]:
            if col["column"] == info["likely_primary_key"] or col["distinct"] == 0:
                continue
            for k_table, k_col in keys:
                if k_table == table:
                    continue
                share = con.execute(
                    f"""SELECT avg(CASE WHEN k.{q(k_col)} IS NOT NULL THEN 1 ELSE 0 END)
                        FROM (SELECT DISTINCT {q(col['column'])}::VARCHAR AS v FROM {q(table)}
                              WHERE {q(col['column'])} IS NOT NULL) s
                        LEFT JOIN (SELECT DISTINCT {q(k_col)}::VARCHAR AS {q(k_col)} FROM {q(k_table)}) k
                          ON s.v = k.{q(k_col)}"""
                ).fetchone()[0]
                if share is not None and share >= FK_THRESHOLD:
                    fks.append({"from": f"{table}.{col['column']}", "to": f"{k_table}.{k_col}",
                                "match_rate": round(share, 4)})
    return fks


def profile_folder(folder: Path, n_samples: int = 10) -> dict:
    con = duckdb.connect()
    tables: dict = {}
    for path in sorted(folder.glob("*.csv")):
        name = path.stem.upper()
        con.execute(
            f"CREATE TABLE {q(name)} AS SELECT * FROM read_csv_auto(?, all_varchar=true, header=true)",
            [str(path)],
        )
        rows = con.execute(f"SELECT count(*) FROM {q(name)}").fetchone()[0]
        cols = [r[0] for r in con.execute(f"DESCRIBE {q(name)}").fetchall()]
        tables[name] = {
            "file": path.name,
            "rows": rows,
            "columns": [profile_column(con, name, c, rows, n_samples) for c in cols],
        }
    for info in tables.values():
        # Prefer a unique column whose name looks like an ID; fall back to the first unique column.
        unique = [c["column"] for c in info["columns"] if c["unique"]]
        id_like = [c for c in unique if re.search(r"(^id$|id$|_id$|code$)", c, re.I)]
        info["likely_primary_key"] = (id_like or unique or [None])[0]
    return {
        "source_folder": str(folder),
        "table_count": len(tables),
        "total_rows": sum(t["rows"] for t in tables.values()),
        "tables": tables,
        "foreign_keys": find_foreign_keys(con, tables),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, default=Path("profile.json"))
    ap.add_argument("--samples", type=int, default=10)
    args = ap.parse_args()
    result = profile_folder(args.folder, args.samples)
    args.out.write_text(json.dumps(result, indent=2, default=str))
    print(f"Profiled {result['table_count']} tables, {result['total_rows']:,} rows -> {args.out}")
    for fk in result["foreign_keys"]:
        print(f"  FK  {fk['from']} -> {fk['to']}  ({fk['match_rate']:.0%})")


if __name__ == "__main__":
    main()
