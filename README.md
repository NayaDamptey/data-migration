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
   │  data quality       7 standard checks (DuckDB rules) + duplicate review (merge or keep both)
   ▼
Migration_Staging.mid.<Entity>            middle tier: one INSERT ... SELECT script per entity (25),
   │                                      then the reviewer's duplicate merges are applied
   ▼
RecruitPlatform_Target.dbo.<Table>        target: one INSERT ... SELECT script per table (37);
                                          orphans are rejected, rows on deleted parents are flagged
                                          (dbo.MigrationRejects)
   │
   ▼
Dolt                                      every run, field change and merge is a version
```

## Screens (in order)

1. **Setup** (`/`): source and destination, the source upload (CSVs, folders or zips) and the pipeline:
   upload source → run data quality → run canonical layer → run target → get data.
2. **Data quality** (`/quality`): locked until source data is uploaded. Two tabs:
   - **Checks:** the 7 standard checks: duplicate people; duplicate companies, jobs and transactions;
     deleted records still active; placements on deleted jobs or companies; orphaned contacts,
     documents and notes. Each problem is described technically (table, key, values).
   - **Duplicates:** each suspected pair side by side. Merge (keep one record, pick each value) or keep
     both. A decision is applied to the middle tier and target straight away, as a new version.
3. **Schema mapping** (`/canonical`): the middle tier.
   - **Extracted data:** the rows of each `mid` table.
   - **Developer view:** each entity's INSERT script; any field's expression can be changed (it is saved,
     re-run on SQL Server and undone if it fails).
   - **Request a change:** plain-English change requests.
4. **Destination data** (`/target`): the target tables, their INSERT scripts (editable), the rows that
   were rejected or flagged, and Get data (CSV files or SQL inserts).
5. **Version review** (`/versions`): every version stored in Dolt. A merge shows both records side by
   side and the record they became; a load shows an audit trail of source tables read and target
   tables loaded.

## Run it locally

```bash
# API
pip install -r backend/requirements.txt
cd backend && APP_ENV=development uvicorn app.main:app --port 8000   # the UI calls http://127.0.0.1:8000

# Frontend
cd frontend && npm install && npm run dev                            # http://localhost:3000

# Legacy source database in SQL Server Express (needs pyodbc)
python engine/sample_data/build_source_db.py --load

# Middle tier + target scripts (also run from the UI): write them, or write and run them
python engine/mapping/tiers.py --run
```

Version review needs [Dolt](https://github.com/dolthub/dolt) on the PATH (or in `tools/dolt`); the
version database is kept in `storage/dolt/migration`.

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
| `engine/sample_data/` | Builds the legacy CRM source (58 tables, foreign keys, 60 planted problems with an answer key) |
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
- **Data:** SQL Server Express (source, middle tier and target), DuckDB (data quality rules), Dolt (versions), pyodbc
- **Testing and CI:** pytest, GitHub Actions
- **Hosting (demo):** Vercel
