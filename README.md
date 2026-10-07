# Migration Platform

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
