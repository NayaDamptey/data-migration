# Roadmap: build order

## Phase 1: Core engine (no UI)
- [ ] Finalise `canonical/model.yaml`
- [x] Profiler for CSV folders
- [ ] Hand-write one mapping spec for a source you know well
- [ ] Generate SQLMesh canonical models from a spec
- [ ] One target (e.g. Bullhorn CSV) end to end, with audits
- [ ] CSV delivery + data dictionary

## Phase 2: AI mapping
- [ ] Key and relationship discovery
- [ ] Table → entity classification (Claude API, JSON output)
- [ ] Field candidate retrieval (names, patterns, past mappings)
- [ ] Field + value mapping with confidence and questions
- [ ] Store approved mappings for reuse

## Phase 3: Platform
- [ ] FastAPI + Postgres: projects, runs, versions, change requests
- [ ] Celery worker running the pipeline stages
- [ ] Object storage per organisation
- [ ] Auth (Clerk/Auth0)

### Make the developer SQL view real
The Schema mapping developer view shows each entity's joins as SQL. Today that SQL
is generated in the browser from mock data; once the API exists it must be real:
- [ ] Store joins and field mappings as structured spec (YAML), not SQL text; the API is the only place that turns spec into SQL
- [ ] Compile spec → SQLMesh model with SQLGlot (DuckDB dialect); return that exact SQL to the editor instead of building it in the browser
- [ ] Validate every edit server-side: parse with SQLGlot, check tables and columns exist in the profiled source, reject anything that isn't a SELECT
- [ ] Match counts per join from real queries (`COUNT(*)` of base rows with a match), refreshed after each edit
- [ ] "Preview rows": run the entity query with `LIMIT 50` on the run's DuckDB snapshot, read-only, with a timeout
- [ ] Transform macros (`@split_address`, `@value_map`, `@parse_date`, …) in `pipeline/sqlmesh/macros`, unit-tested
- [ ] Optional: a raw SQL mode for developers, parsed and checked the same way, run read-only on the snapshot (never on agency systems)

## Phase 4: Frontend
- [ ] Build the four screens from the prototype
- [ ] Review flow: accept / fix / comment per field
- [ ] Downloads and version history

## Phase 5: More sources and targets
- [ ] Backup restore containers (SQL Server, MySQL, Postgres)
- [ ] JSON / API ingestion with dlt
- [x] SQL inserts output in MySQL / Postgres / T-SQL, injection-proof (`pipeline/deliver/sql_inserts.py`)
- [ ] More target schemas
