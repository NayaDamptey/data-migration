# Migryr

A data migration tool for recruitment CRMs. You upload a legacy CRM's tables, check their data
quality, review suspected duplicates, map the data to a target schema and generate the T-SQL that
loads it.

All system and company names in this project are fictional (Cobaltdesk, Beaconfield, Larkspur,
Quillhire, Ninefold, Vantora, Harrow & Finch Recruitment), and so are their logos. The sample
data is generated.

## How it works

```
Source upload (CSV files, folders or zips)
   ▼
Data quality       7 standard checks, rules run in DuckDB over the uploaded files
   ▼
Duplicate review   suspected pairs side by side: merge (pick each value) or keep both
   ▼
Mapping            relational source → target mapping, with unmapped or broken links flagged
   ▼
T-SQL generation   key map, merges applied, load scripts, foreign keys, reconciliation counts
   ▼
SQL Server target
```

## Screens (in order)

1. **Source upload** (`/`): the start page. Upload CSVs, folders or zips. Files are checked in the
   browser, then stored by the API.
2. **Data quality** (`/quality`): locked until source data is uploaded. Two tabs:
   - **Checks:** the 7 standard checks: duplicate people; duplicate companies, jobs and transactions;
     deleted records still active; orphaned contacts (no company), candidates (no job), documents and
     notes (no record). Click a problem to see the offending records.
   - **Duplicates:** each suspected pair side by side. Merge (keep one record, pick each value) or keep
     both. Merges are applied by the migration; the source is never changed.
3. **Workflow:** Setup (`/workspace`, pipeline: upload source → data quality → canonical → target →
   get data), Schema mapping (`/canonical`), Destination data (`/target`), Version review (`/versions`).

## Run it locally

```bash
# API
pip install -r backend/requirements.txt
cd backend && APP_ENV=development uvicorn app.main:app --port 8000   # the UI calls http://127.0.0.1:8000

# Frontend
cd frontend && npm install && npm run dev                            # http://localhost:3000

# Optional: build the legacy source database in SQL Server Express (needs pyodbc)
python engine/sample_data/build_source_db.py --load
```

## Portfolio demo (no API or database)

`NEXT_PUBLIC_DEMO=1` runs the frontend on its own. Every API call is answered from a snapshot in
`frontend/public/demo/`, and duplicate decisions are saved in the visitor's browser.

Deploy on Vercel: import the repository, set **Root Directory** to `frontend`, and add the
environment variable `NEXT_PUBLIC_DEMO=1`.

To refresh the snapshot, start the API and run `python frontend/scripts/make_demo_data.py`.

## Migration engine (`engine/`)

Plain Python, used by the API through `backend/app/engine_bridge.py`.

| Folder | What it does |
|---|---|
| `engine/sample_data/` | Builds the legacy CRM source (58 tables, foreign keys, 57 planted problems with an answer key) |
| `engine/validation/` | Data quality rules (DuckDB), the 7 standard checks and duplicate pairs |
| `engine/mapping/` | Relational source → target mapping and the T-SQL generator |
| `engine/sql/` | Generated source, profiling, entity-trace and target load scripts |
| `engine/docs/` | Source data model, planted problems and mapping reference |
| `engine/tests/` | `python -m pytest engine/tests` |

## Folder layout

| Folder | What lives there |
|---|---|
| `frontend/` | Next.js app |
| `backend/` | FastAPI service: uploads, data quality report, duplicate decisions |
| `engine/` | Source build, data quality rules, mapping and SQL generation |
| `docs/` | Screen list and the original sketches |

## Tech stack

- **Languages:** TypeScript, Python, T-SQL, SQL (DuckDB)
- **Frontend:** Next.js, React, Tailwind CSS
- **API:** FastAPI, Uvicorn, Pydantic
- **Data:** DuckDB (data quality rules), SQL Server Express (source and target databases), pyodbc
- **Testing and CI:** pytest, GitHub Actions
- **Hosting (demo):** Vercel
