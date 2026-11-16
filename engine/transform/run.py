"""
transform/run.py

One migration run: ingest the source to Parquet, generate the dbt project from the mapping spec and the
duplicate decisions, then `dbt build` (seeds, the middle tier, the target, the rejects, and the tests) on
a DuckDB file for that run. Each run keeps its own Parquet input and warehouse, so runs are isolated and
can be compared.

    storage/projects/<project>/runs/<run>/source/*.parquet     input
    storage/projects/<project>/runs/<run>/warehouse.duckdb     staging, mid, target, audit schemas
    storage/projects/<project>/runs/<run>/target/<Table>.parquet  the target, exported

Run
    python transform/run.py --run r1                 # ingest from the legacy database, build, test
    python transform/run.py --run r1 --skip-ingest   # rebuild on the run's existing Parquet
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
sys.path.insert(0, str(ENGINE / "ingest"))
sys.path.insert(0, str(HERE))
from to_parquet import from_csv, from_sqlserver, run_dir  # noqa: E402

DBT = HERE / "dbt"


def run(project: str, run_id: str, ingest: bool = True, csv_dir: Path | None = None) -> dict:
    import build_dbt
    started = time.time()
    rd = run_dir(project, run_id)
    src = rd / "source"
    if csv_dir is not None:
        from_csv(csv_dir, src)
    elif ingest or not src.exists():
        from_sqlserver(src)
    built = build_dbt.build(src)

    env = {"MIGRYR_SOURCE_DIR": src.as_posix(), "MIGRYR_WAREHOUSE": (rd / "warehouse.duckdb").as_posix(),
           "MIGRYR_DBT_TARGET": (rd / "dbt_target").as_posix(), "MIGRYR_DBT_LOGS": (rd / "dbt_logs").as_posix()}
    os.environ.update(env)
    from dbt.cli.main import dbtRunner
    res = dbtRunner().invoke(["build", "--project-dir", str(DBT), "--profiles-dir", str(DBT), "--quiet"])
    results = []
    for r in (res.result or []):
        node = getattr(r, "node", None)
        results.append({"name": getattr(node, "name", "?"), "type": getattr(node, "resource_type", "?"),
                        "status": str(r.status), "message": r.message, "failures": getattr(r, "failures", None)})

    # export the target as Parquet (what the delivery step and the UI read)
    import duckdb
    out = rd / "target"
    out.mkdir(exist_ok=True)
    con = duckdb.connect(str(rd / "warehouse.duckdb"))
    counts = {}
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'target'").fetchall():
        con.execute(f"COPY target.\"{t}\" TO '{(out / f'{t}.parquet').as_posix()}' (FORMAT parquet)")
        counts[t] = con.execute(f"SELECT COUNT(*) FROM target.\"{t}\"").fetchone()[0]
    rejected = con.execute("SELECT action, COUNT(*) FROM audit.migration_rejects GROUP BY action").fetchall() \
        if con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='audit'").fetchone()[0] else []
    con.close()
    summary = {"project": project, "run": run_id, "ok": res.success, "seconds": round(time.time() - started, 1),
               "built": built, "target_rows": counts, "rejects": dict(rejected),
               "failed": [r for r in results if r["status"] not in ("success", "pass")]}
    (rd / "run.json").write_text(json.dumps({**summary, "results": results}, indent=2, default=str), encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="harrow-finch-cobaltdesk-beaconfield")
    ap.add_argument("--run", required=True)
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--csv", help="ingest from a folder of CSV files instead of the legacy database")
    a = ap.parse_args()
    s = run(a.project, a.run, ingest=not a.skip_ingest, csv_dir=Path(a.csv) if a.csv else None)
    print(json.dumps({k: v for k, v in s.items() if k != "target_rows"}, indent=2, default=str))
    print(f"{len(s['target_rows'])} target tables, {sum(s['target_rows'].values())} rows")


if __name__ == "__main__":
    main()
