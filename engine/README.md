# Migration engine

Legacy recruitment CRM (the fictional *Cobaltdesk*) to target platform. The API (`../backend`) uses it for
ingestion, data quality, duplicate review, the dbt transformation, personal data and runs.

## Quick start

```bash
pip install -r requirements.txt

# a run: ingest to Parquet, generate the dbt project from the mapping spec, dbt build, export the target
python transform/run.py --run r1 --csv sample_data/source     # from the clean CSVs (no SQL Server needed)
python transform/run.py --run r1                              # from the restored legacy database

# the synthetic legacy source
python sample_data/build_source_db.py          # rebuild the source CSVs and SQL scripts
python sample_data/build_source_db.py --load   # also load Cobaltdesk_Legacy into localhost\SQLEXPRESS

python -m pytest tests -q                      # tests needing SQL Server skip themselves without one
```

## Layout

| Folder | What it does |
|---|---|
| `ingest/to_parquet.py` | Source tables to one Parquet file each, per run |
| `transform/spec/` | The mapping spec (`middle.yml`, `target.yml`), field overrides and personal data tags |
| `transform/build_dbt.py` | Generates the dbt project from the spec and the duplicate decisions |
| `transform/dbt/` | The dbt project (models and seeds are generated; `dbt_project.yml`, `profiles.yml` and macros are not) |
| `transform/runs.py` | Runs: ingest, build, row counts, history (the versions) |
| `validation/` | Data quality rules, the 4 checks, duplicate pairs and decisions |
| `privacy/pii.py` | Personal data detection (Presidio), tags and masking |
| `sample_data/` | The synthetic legacy source and its planted problems |
| `mapping/merge_decisions.json` | The duplicate decisions made in the UI |
| `mapping/` (other files), `sql/middle/`, `sql/load/`, `sql/target/` | The earlier SQL Server version of the mapping, kept as a reference |

## Tech stack

Python, DuckDB, Polars, Parquet, dbt Core (dbt-duckdb), SQLGlot, Microsoft Presidio; SQL Server Express for
the legacy source (pyodbc); pytest.
