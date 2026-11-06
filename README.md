# Migryr

An AI-assisted platform that moves recruitment data from any source system
(Tracker, JobAdder, Bullhorn, Seven20, Vincere and others) into any target
schema. Agencies upload CSVs, database backups or JSON, or connect an API.
The platform maps everything to one **canonical layer**, transforms that into
the **target schema**, and returns validated CSVs, SQL inserts or an API push.

Agencies can run as many versions as they need, request changes in plain
English, and download the output of any run.

## How it works

```
Source (CSV / backup / JSON / API)
   │  ingest  → Parquet snapshot per run
   ▼
Inspect      → DuckDB profiling: tables, row counts, patterns, keys
   ▼
AI mapping   → mapping spec (YAML): source → canonical, with confidence
   ▼  human review of anything below the confidence threshold
Canonical layer (10 entities)            ← SQLMesh models, run on DuckDB
   ▼
Target schema (per target system)        ← SQLMesh models + SQLGlot dialects
   ▼  validation (audits: required fields, keys, formats)
Deliver      → CSVs + data dictionary / SQL inserts / API push
```

## Screens (in order)

1. **Source upload** (`/`): the start page. Upload CSVs, folders or zips. Files are checked in the
   browser, then stored by the API (local mode).
2. **Data quality** (`/quality`): locked until source data is uploaded. Two tabs:
   - **Checks:** the 7 standard checks: duplicate people; duplicate companies, jobs and transactions;
     deleted records still active; orphaned contacts (no company), candidates (no job), documents and
     notes (no record). Click a problem to see the offending records.
   - **Duplicates:** each suspected pair side by side. Merge (keep one record, pick each value) or keep
     both. Merges are applied by the migration; the source is never changed.
3. **Workflow:** Setup (`/workspace`, pipeline: upload source → data quality → canonical → target →
   get data), Schema mapping (`/canonical`), Destination data (`/target`), Version review (`/versions`).
   Sign-in lives at `/signin`.

## Run it locally

```bash
# API (needs fastapi, uvicorn, duckdb and python-multipart; pyodbc for the SQL Server source)
cd backend && APP_ENV=development uvicorn app.main:app --port 8000   # the UI calls http://127.0.0.1:8000
# Frontend
cd frontend && npm install && npm run dev        # http://localhost:3000
# Optional: build the legacy SQL Server source that the dashboard checks
python engine/sample_data/build_source_db.py --load
```

## Migration engine (`engine/`)

Merged from the *Data Migration* project. It is plain Python, used by the API through
`backend/app/engine_bridge.py`.

| Folder | What it does |
|---|---|
| `engine/sample_data/` | Builds the legacy recruitment CRM source in SQL Server (58 tables, 156 FKs, 244 planted defects) |
| `engine/validation/` | The data quality rules (DuckDB) behind the dashboard; run `pytest engine/tests` |
| `engine/mapping/` | Relational source → target mapping, validator flags and the T-SQL generator |
| `engine/sql/` | Generated source, profiling, trace and target scripts |
| `engine/docs/` | Source data model, planted defects and mapping reference |

## Folder layout

| Folder | What lives there |
|---|---|
| `docs/` | Architecture, the AI mapping design, the screens and the original sketches |
| `canonical/` | The canonical recruitment model: 10 entities and their fields |
| `mappings/` | Mapping specs: one per source system (and per project once approved) |
| `pipeline/profiling/` | The source profiler (working): run it on a folder of CSVs |
| `pipeline/mapping/` | AI mapping: candidate retrieval, LLM prompt, spec output |
| `pipeline/sqlmesh/` | SQLMesh project: canonical and target models |
| `backend/` | FastAPI service: projects, runs, versions, change requests, downloads |
| `frontend/` | Next.js app: sign in, setup, canonical review, target and delivery |
| `samples/` | Small fake source files for local testing |

## Tech stack

- **Frontend:** Next.js (React + TypeScript), Tailwind + shadcn/ui, TanStack Table, TanStack Query, Zod
- **Auth:** Clerk or Auth0 (one organisation per agency)
- **API:** FastAPI (Python)
- **App database:** Postgres (projects, runs, versions, mappings, change requests, audit log)
- **Jobs:** Celery + Redis to start; Dagster later for pipeline tracking
- **Data engine:** DuckDB for processing and profiling, SQLMesh for models, SQLGlot for SQL dialects
- **Ingestion:** temporary Docker containers to restore backups (SQL Server / MySQL / Postgres), dlt for APIs and nested JSON
- **AI:** Claude API for mapping suggestions and turning change requests into mapping changes
- **Storage:** object storage (S3 London / Azure UK South) for uploads and run outputs
- **Infra:** Docker, GitHub Actions, UK hosting for GDPR

## Quick start (local)

```bash
# 1. Profile a folder of CSVs (works today)
pip install duckdb
python pipeline/profiling/profile_source.py samples/tracker --out profile.json

# 2. Run everything else (once the services are filled in)
cp .env.example .env
docker compose up
```

## Status

| Part | Status |
|---|---|
| Canonical model (`canonical/model.yaml`) | First draft |
| Source profiler | Working |
| Mapping spec format + example | First draft |
| AI mapping | Prompt and flow outlined, not wired up |
| SQLMesh models | One example per layer (candidates) |
| API | Route skeleton |
| Frontend | Page skeleton; design in the prototype canvas |

See `docs/roadmap.md` for the build order.
