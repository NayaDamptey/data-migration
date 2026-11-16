# Migryr

A data migration tool for recruitment CRMs, built the way migrations are done traditionally but
automated: check the legacy data, review duplicates, load it into a middle tier with plain T-SQL
INSERT scripts, load the middle tier into the target, and keep every run as a version.

All system and company names in this project are fictional (Cobaltdesk, Beaconfield, Larkspur,
Quillhire, Ninefold, Vantora, Harrow & Finch Recruitment), and so are their logos. The sample
data is generated.

## How it works

```
Cobaltdesk_Legacy (SQL Server)            legacy CRM: 58 tables
   │  data quality       4 checks (DuckDB rules) + duplicate review (merge or keep both)
   ▼
Migration_Staging.mid.<Entity>            middle tier: one INSERT ... SELECT script per entity (25),
   │                                      then the reviewer's duplicate merges are applied
   ▼
RecruitPlatform_Target.dbo.<Table>        target: one INSERT ... SELECT script per table (37);
                                          jobs with no company, placements with no job and orphans are rejected
                                          (dbo.MigrationRejects)
   │
   ▼
Runs (engine/transform/runs.py)          every run, field change and merge is a version
```

## Platform data core (in progress: dbt on DuckDB)

The migration is moving to the platform stack. The processing no longer needs SQL Server:

```
source (restored .bak or uploaded CSVs)  ──►  Parquet, one file per table, per run       engine/ingest/to_parquet.py
mapping spec (DuckDB SQL, YAML)          ──►  dbt project, generated                      engine/transform/spec/*.yml, build_dbt.py
dbt build on DuckDB                      ──►  staging → middle tier (merges applied)
                                              → target → rejects, plus tests on every key
                                              and link                                    engine/transform/run.py
target                                   ──►  Parquet per table (export via SQLGlot next)
```

```bash
python engine/transform/run.py --run r1                                   # from the restored legacy database
python engine/transform/run.py --run r1 --csv engine/sample_data/source   # from CSV files
```

Each run keeps its own Parquet input and DuckDB warehouse in `storage/projects/<project>/runs/<run>/`.
Its output matches the SQL Server scripts table for table (25 middle-tier and 37 target tables, the same
rejects). The app runs on it: Run canonical layer starts a new run (`engine/transform/runs.py`), field
edits in the developer view change the spec and rebuild the affected dbt models (downstream included),
duplicate decisions start a new run with the merges applied, and every run is a version.
Next: run builds as Celery jobs, keep mappings, decisions, approvals and run history in Postgres, and
export INSERT scripts in any SQL dialect with SQLGlot.

## Screens (in order)

1. **Setup** (`/`): source and destination, the source upload (CSVs, folders or zips) and the pipeline:
   upload source → run data quality → run canonical layer → run target → get data.
2. **Data quality** (`/quality`): locked until source data is uploaded. Two tabs:
   - **Checks:** 4 checks: duplicate records; placements linked to no job; jobs linked to no company;
     dates that don't make sense (end before start, placements outside their job's dates, placeholder or
     future dates). Each problem is described technically (table, key, values).
   - **Duplicates:** each suspected pair side by side. Merge (keep one record, pick each value) or keep
     both. A decision is applied to the middle tier and target straight away, as a new version.
3. **Schema mapping** (`/canonical`): the middle tier.
   - **Extracted data:** the rows of each `mid` table.
   - **Developer view:** each entity's dbt model and its field expressions; any field can be changed (the
     mapping spec is updated and the model and everything downstream rebuilt; a failing change is undone).
   - **Request a change:** plain-English change requests.
4. **Review records** (`/review`): the customer's own data as records (Candidates, Clients, Contacts, Jobs,
   Placements), records to check first. Each record shows its details, related records and plain-language
   flags; clicking a value shows where it came from in the legacy source (table, column, row).
5. **Destination data** (`/target`): the target tables, their dbt models (editable), the rows that
   were rejected or flagged, and Get data (CSV files or SQL inserts).
6. **Version review** (`/versions`): every run is a version: the changes made in it, each merge as both
   records side by side and the record they became, and an audit trail of source tables read and target
   tables loaded.

## Run it locally

```bash
# API
pip install -r backend/requirements.txt
cd backend && APP_ENV=development uvicorn app.main:app --port 8000   # the UI calls http://127.0.0.1:8000

# Frontend
cd frontend && npm install && npm run dev                            # http://localhost:3000

# Legacy source database in SQL Server Express: restore the synthetic backup (SQL Server 2022+;
# copy engine/backups/Cobaltdesk_Legacy.bak into the server's Backup folder first) ...
sqlcmd -S "localhost\SQLEXPRESS" -E -i engine/backups/restore_Cobaltdesk_Legacy.sql
# ... or rebuild it from the CSVs (needs pyodbc)
python engine/sample_data/build_source_db.py --load

# Middle tier + target scripts (also run from the UI): write them, or write and run them
python engine/mapping/tiers.py --run
```

## Portfolio demo (no API or database)

`NEXT_PUBLIC_DEMO=1` runs the frontend on its own. Every API call is answered from a snapshot in
`frontend/public/demo/`, and duplicate decisions are saved in the visitor's browser.

Deploy on Vercel: import the repository, set **Root Directory** to `frontend`, and add the
environment variable `NEXT_PUBLIC_DEMO=1`.

To refresh the snapshot, start the API and run `python frontend/scripts/make_demo_data.py`.

## Migration engine (`engine/`)

Plain Python, used by the API through `backend/app/engine_bridge.py` and `backend/app/layers.py`.

| Folder | What it does |
|---|---|
| `engine/sample_data/` | Builds the legacy CRM source (58 tables, foreign keys, 64 planted problems with an answer key) |
| `engine/validation/` | Data quality rules (DuckDB), the 7 standard checks and duplicate pairs |
| `engine/mapping/tiers.py` | The middle tier and target: every field as one expression, scripts, checks, merges |
| `engine/sql/middle/`, `engine/sql/load/` | The generated middle tier and target scripts |
| `engine/sql/source/`, `engine/sql/profiling/` | Source build and profiling scripts |
| `engine/docs/` | Source data model, planted problems and mapping reference |
| `engine/tests/` | `python -m pytest engine/tests` (the SQL Server tests skip themselves without a server) |

## Folder layout

| Folder | What lives there |
|---|---|
| `frontend/` | Next.js app |
| `backend/` | FastAPI service: uploads, data quality, duplicate decisions, middle tier / target, versions |
| `engine/` | Source build, data quality rules, middle tier and target scripts |
| `docs/` | Screen list and the original sketches |

## Tech stack

- **Languages:** TypeScript, Python, T-SQL, SQL (DuckDB)
- **Frontend:** Next.js, React, Tailwind CSS
- **API:** FastAPI, Uvicorn, Pydantic
- **Data:** Parquet, DuckDB, Polars, dbt Core (dbt-duckdb), SQLGlot; SQL Server Express (restoring the legacy backup), pyodbc
- **Testing and CI:** pytest, GitHub Actions
- **Hosting (demo):** Vercel
