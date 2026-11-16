"""
ingest/to_parquet.py

Ingestion: the source becomes one Parquet file per table, per run. Everything downstream (dbt on
DuckDB) reads these files, so the processing never touches the customer's system again.

    storage/projects/<project>/runs/<run>/source/<Table>.parquet

Sources
    legacy   a restored SQL Server database (the customer's .bak, restored in a container)
    csv      uploaded CSV files, typed with the source schema

Run
    python ingest/to_parquet.py --run <run-id>                     # from the legacy database
    python ingest/to_parquet.py --run <run-id> --csv <folder>      # from uploaded CSVs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

ENGINE = Path(__file__).resolve().parent.parent
REPO = ENGINE.parent
sys.path.insert(0, str(ENGINE / "sample_data"))
from build_source_db import load_schema  # noqa: E402

SERVER = r"localhost\SQLEXPRESS"
SOURCE_DB = "Cobaltdesk_Legacy"


def run_dir(project: str, run: str) -> Path:
    return REPO / "storage" / "projects" / project / "runs" / run


def _polars_type(sql_type: str) -> pl.DataType:
    t = sql_type.upper()
    if t.startswith(("INT", "BIGINT", "SMALLINT", "TINYINT")):
        return pl.Int64
    if t.startswith("BIT"):
        return pl.Boolean
    if t.startswith(("DECIMAL", "NUMERIC", "MONEY", "FLOAT", "REAL")):
        return pl.Float64
    if t.startswith("DATETIME"):
        return pl.Datetime("us")
    if t.startswith("DATE"):
        return pl.Date
    if t.startswith("TIME"):
        return pl.Utf8
    return pl.Utf8


def from_sqlserver(out: Path, server: str = SERVER, database: str = SOURCE_DB) -> dict[str, int]:
    """Read every source table from a restored SQL Server database into Parquet."""
    import pyodbc
    schema = load_schema()
    out.mkdir(parents=True, exist_ok=True)
    cn = pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;")
    counts = {}
    for table, cols in schema.items():
        names = [c["col"] for c in cols]
        cur = cn.cursor()
        cur.execute(f"SELECT {', '.join(f'[{c}]' for c in names)} FROM dbo.[{table}]")
        rows = cur.fetchall()
        data = {c: [r[i] for r in rows] for i, c in enumerate(names)}
        df = pl.DataFrame(data, schema={c["col"]: _polars_type(c["type"]) for c in cols}, strict=False)
        df.write_parquet(out / f"{table}.parquet")
        counts[table] = df.height
    cn.close()
    return counts


def _from_text(col: str, t: pl.DataType) -> pl.Expr:
    """A CSV text column as its schema type; values that don't fit become empty."""
    c = pl.col(col).str.strip_chars()
    c = pl.when(c == "").then(None).otherwise(c)
    if t == pl.Boolean:
        return pl.when(c.is_null()).then(None).otherwise(c.str.to_lowercase().is_in(["1", "true", "yes", "y"])).alias(col)
    if t == pl.Date:
        return c.str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias(col)
    if isinstance(t, pl.Datetime):
        return c.str.to_datetime(strict=False, time_unit="us").alias(col)
    return c.cast(t, strict=False).alias(col)


def from_csv(folder: Path, out: Path) -> dict[str, int]:
    """Uploaded CSVs (named after the source tables) into typed Parquet; unknown files are skipped."""
    schema = {t.lower(): (t, cols) for t, cols in load_schema().items()}
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for f in sorted(folder.glob("*.csv")):
        if f.stem.lower() not in schema:
            continue
        table, cols = schema[f.stem.lower()]
        df = pl.read_csv(f, infer_schema=False, encoding="utf8-lossy")
        df = df.select([_from_text(c["col"], _polars_type(c["type"])) if c["col"] in df.columns
                        else pl.lit(None, dtype=_polars_type(c["type"])).alias(c["col"]) for c in cols])
        df.write_parquet(out / f"{table}.parquet")
        counts[table] = df.height
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="harrow-finch-cobaltdesk-beaconfield")
    ap.add_argument("--run", required=True)
    ap.add_argument("--csv", help="folder of uploaded CSV files (default: the legacy SQL Server database)")
    args = ap.parse_args()
    out = run_dir(args.project, args.run) / "source"
    counts = from_csv(Path(args.csv), out) if args.csv else from_sqlserver(out)
    print(f"{len(counts)} tables, {sum(counts.values())} rows -> {out}")


if __name__ == "__main__":
    main()
