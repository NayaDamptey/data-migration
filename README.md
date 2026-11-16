# Migryr

A data migration platform for recruitment CRMs. It follows the way migrations are done by hand, a
middle tier between the legacy system and the target, and automates it. You check the legacy data,
review duplicates, map the data into the middle tier and on to the target, and review the result as
records. Every run is kept as a version.

All system and company names in this project are fictional (Cobaltdesk, Beaconfield, Larkspur,
Quillhire, Ninefold, Vantora, Harrow & Finch Recruitment), and so are their logos. The sample data is
generated.

## How it works

```
Legacy CRM (Cobaltdesk, 58 tables)
   │   restored backup or uploaded CSV files
   ▼
Ingest                     one Parquet file per table, per run                   engine/ingest/
   │
   │   Data quality        4 checks + duplicate review (merge or keep both)       engine/validation/
   ▼
Middle tier (25 entities)  dbt models generated from the mapping spec;            engine/transform/
   │                       the reviewer's duplicate merges are applied
   ▼
Target (37 tables)         dbt models; jobs with no company, placements with
                           no job and records linked to nothing are rejected
                           and listed with the reason
   │
   ▼
Review and versions        records reviewed in the UI; every run is a version
```

The **mapping spec** is the source of truth. It holds every middle-tier and target field as one DuckDB
SQL expression, in `engine/transform/spec/middle.yml` and `target.yml`. The dbt project is generated from
the spec and the duplicate decisions. `dbt build` runs it on a DuckDB file for the run, with tests that
every key is unique and every link between target tables resolves.

Each run lives in `storage/projects/<project>/runs/<run>/`. It holds its Parquet input, its DuckDB
warehouse (staging, middle tier, target, rejects), the spec and merges it was built from, row counts,
and the changes made in it. That's what Version review shows.

## Screens (in order)

1. **Setup** (`/`): source and destination, the source upload (CSVs, folders or zips) and the pipeline:
   upload source → run data quality → run canonical layer → run target → get data.
2. **Data quality** (`/quality`): locked until source data is uploaded. Two tabs:
   - **Checks:** duplicate records; placements linked to no job; jobs linked to no company; invalid dates
     (end before start, placements outside their job's dates, placeholder or future dates). Each problem
     is described technically: table, key, values.
   - **Duplicates:** each suspected pair side by side. Merge (keep one record, pick each value) or keep
     both. A decision starts a new run with the merge applied.
3. **Schema mapping** (`/canonical`): the middle tier.
   - **Extracted data:** the rows of each middle-tier table.
   - **Developer view:** each entity's dbt model, its field expressions and their personal data tags. Any
     expression can be changed: the spec is updated and the model and everything downstream rebuilt; a
     change that fails is undone and dbt's error shown.
   - **Request a change:** plain-English change requests.
4. **Review records** (`/review`): the customer's own data as records (Candidates, Clients, Contacts, Jobs,
   Placements), with the records to check listed first. Each record shows its details, related records
   and plain-language flags. Clicking a value shows where it came from in the source: table, column, row.
5. **Destination data** (`/target`): the target tables, their dbt models (editable), the rows that were
   rejected or flagged, and Get data (CSV files or SQL inserts).
6. **Version review** (`/versions`): every run. A load shows an audit trail of source rows read and target
   rows loaded, a merge shows both records side by side and the record they became, and field changes
   are listed.

## Personal data

Every middle-tier field can carry a personal data category: name, email, phone, address, free text, date
of birth, NI number, bank account or sort code.

- **Suggested automatically,** from the column name and from Microsoft Presidio's pattern detectors run on
  sample values (email, phone, UK NI number, UK postcode, IBAN, plus a sort code rule).
- **Confirmed or changed** by a person in the developer view, and kept with the spec in
  `engine/transform/spec/pii.yml`. Source and target fields inherit the tag of the middle-tier field they
  feed or are fed by.
- **Masked:** date of birth, NI number, bank account and sort code are masked everywhere the app shows
  data, keeping only the last two characters. Search runs over masked values, so it can't find one.
  Names and contact details stay visible, since reviewers need them.

## Run it locally

Needs Python 3.12+, Node 22 and, for the legacy source, SQL Server 2022 Express.

```bash
# Legacy source: restore the synthetic backup (copy engine/backups/Cobaltdesk_Legacy.bak into the
# server's Backup folder first) ...
sqlcmd -S "localhost\SQLEXPRESS" -E -i engine/backups/restore_Cobaltdesk_Legacy.sql
# ... or rebuild it from the CSVs
python engine/sample_data/build_source_db.py --load

# API
pip install -r backend/requirements.txt
cd backend && APP_ENV=development uvicorn app.main:app --port 8000      # the UI calls http://127.0.0.1:8000

# Frontend
cd frontend && npm install && npm run dev                               # http://localhost:3000
```

The first page that needs data starts a run on its own. A run can also be built from the command line:

```bash
python engine/transform/run.py --run r1                                 # from the restored legacy database
python engine/transform/run.py --run r1 --csv engine/sample_data/source # from CSV files (no SQL Server)
```

Tests: `python -m pytest engine/tests` and `cd backend && python -m pytest tests`. Tests that need SQL
Server or a built run skip themselves without one, so CI runs the rest.

## Portfolio demo (no API or database)

`NEXT_PUBLIC_DEMO=1` runs the frontend on its own. Every API call is answered from a snapshot in
`frontend/public/demo/`, and duplicate decisions are saved in the visitor's browser. Editing, value
sources and versions need the API.

Deploy on Vercel: import the repository, set **Root Directory** to `frontend`, and add the environment
variable `NEXT_PUBLIC_DEMO=1` for Production and Preview. To refresh the snapshot, start the API and run
`python frontend/scripts/make_demo_data.py`.

## Engine (`engine/`)

| Folder | What it does |
|---|---|
| `ingest/` | Source to Parquet: a restored SQL Server database or uploaded CSVs, typed with the source schema |
| `transform/` | The mapping spec, the dbt project generator, the dbt project, and runs (versions) |
| `validation/` | Data quality rules (DuckDB), the 4 checks, duplicate pairs and decisions |
| `privacy/` | Personal data detection, tags and masking |
| `sample_data/` | Builds the synthetic legacy source: 58 tables, foreign keys, 64 planted problems with an answer key |
| `backups/` | The legacy source as a SQL Server backup, and its restore script |
| `docs/` | Source data model, planted problems and mapping reference |
| `mapping/` | `merge_decisions.json`, the duplicate decisions; also the earlier SQL Server version of the mapping, kept as a reference until removed |
| `sql/` | Source build and profiling scripts; `sql/middle/`, `sql/load/` and `sql/target/` are the earlier T-SQL scripts (reference) |
| `tests/` | pytest |

## Folder layout

| Folder | What lives there |
|---|---|
| `frontend/` | Next.js app |
| `backend/` | FastAPI service: uploads, data quality, duplicates, middle tier and target, review, personal data, versions |
| `engine/` | Ingestion, the dbt transformation, data quality, personal data, the synthetic source |
| `docs/` | Screen list and the original sketches |

## Tech stack

- **Languages:** TypeScript, Python, SQL (DuckDB), T-SQL
- **Frontend:** Next.js, React, Tailwind CSS
- **API:** FastAPI, Uvicorn, Pydantic
- **Data:** Parquet, DuckDB, Polars, dbt Core (dbt-duckdb), SQLGlot; SQL Server Express (the legacy source), pyodbc
- **Personal data:** Microsoft Presidio
- **Testing and CI:** pytest, GitHub Actions
- **Hosting (demo):** Vercel

## Roadmap

1. **Platform services:** run builds as Celery jobs (Redis) with live progress; keep mappings, decisions,
   approvals and run history in Postgres (SQLAlchemy, Alembic) with tenant isolation; data quality reads the
   run's Parquet instead of SQL Server; export INSERT scripts in any SQL dialect with SQLGlot.
2. **Review:** correct values on a record, either just this one or all records like it (a mapping rule
   change), approval per entity and a final approval that locks a version.
3. **AI mapping:** AI proposes each field's expression with a confidence score through a LiteLLM gateway,
   sample values masked with Presidio first, measured against a known answer key.
4. **Frontend on the full stack:** shadcn/ui, TanStack Query, AG Grid, an OpenAPI-generated client.
5. **Infrastructure:** login with MFA, S3 in London, Terraform and ECS, Sentry and OpenTelemetry.
