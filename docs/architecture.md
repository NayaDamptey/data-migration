# Architecture

## Main ideas

1. **Every run is a version.** A run takes one source snapshot plus one
   mapping spec version and produces one set of outputs. Nothing is
   overwritten, so any version can be compared, re-downloaded or rolled back.
2. **The AI writes rules, not data.** The model proposes a mapping spec
   (YAML). Code turns the spec into SQLMesh models, and DuckDB runs them. Runs
   are deterministic, auditable and cheap.
3. **Canonical in the middle.** N sources × M targets becomes N + M mappings.
   Each source only maps to canonical, and each target only maps from it.
4. **People approve what the AI isn't sure about.** Anything below the
   confidence threshold, or failing validation, appears as "Needs review".

## Components

```
Next.js frontend ──► FastAPI ──► Postgres (app data)
                        │
                        ├──► Redis queue ──► Worker (Celery)
                        │                      ├── ingest   (restore / read / pull)
                        │                      ├── profile  (DuckDB)
                        │                      ├── map      (Claude API → mapping spec)
                        │                      ├── canonical (SQLMesh on DuckDB)
                        │                      ├── target    (SQLMesh on DuckDB)
                        │                      └── deliver   (CSV / SQL / API)
                        │
                        └──► Object storage: uploads/, runs/<run_id>/{raw,canonical,target,out}/
```

## Run lifecycle

| Status | Meaning |
|---|---|
| `uploaded` | Source files received |
| `inspecting` → `inspected` | Profile written to `runs/<id>/profile.json` |
| `mapping` → `needs_review` | AI spec proposed; fields waiting for a person |
| `canonical_ready` | Canonical approved |
| `target_ready` | Target built and validated |
| `delivered` | Output downloaded or pushed |
| `superseded` | A newer version replaced it |

## App database (Postgres): core tables

- `organisations`, `users`
- `projects` (source system, target system, target dialect, output type)
- `runs` (project_id, version, status, source_snapshot_uri, mapping_spec_version, started_by, timestamps)
- `mapping_specs` (project_id, version, yaml, created_by, parent_version)
- `field_reviews` (run_id, entity, field, decision, comment, reviewed_by)
- `change_requests` (project_id, run_id, text, status, resulting_spec_version)
- `outputs` (run_id, file_name, row_count, uri, checksum)
- `audit_log` (who did what, when; includes every download)

## Ingesting each source type

| Source | How |
|---|---|
| CSV / zip | Unzip, detect encoding and delimiter, read with DuckDB, save as Parquet |
| SQL Server `.bak` | Restore into a temporary `mssql` container, export each table to Parquet, delete the container |
| MySQL / Postgres dump | Same, using a `mysql` or `postgres` container |
| JSON / NDJSON | DuckDB `read_json_auto`; dlt for deeply nested data |
| API | dlt source per system, with the agency's credentials; never store them longer than the run needs |

## Security and GDPR

- Host in the UK. Encrypt data at rest and in transit.
- Keep each agency's data separate (per-organisation storage prefixes and row-level security).
- Delete source uploads after a set time (e.g. 30 days after delivery), configurable per project.
- Send the LLM profiles and masked samples, not full personal data.
- Log every download and every mapping change.
