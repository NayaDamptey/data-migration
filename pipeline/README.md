# Pipeline

| Stage | Code | Status |
|---|---|---|
| Ingest | `ingest/` (to add): unzip, restore backups, read JSON, pull APIs → Parquet | To build |
| Inspect | `profiling/profile_source.py` | Working for CSV folders |
| Map | `mapping/propose_mapping.py` | Shortlisting works; LLM steps outlined |
| Canonical | `sqlmesh/models/canonical/` | One example model |
| Target | `sqlmesh/models/target/<system>/` | One example model |
| Deliver | `deliver/sql_inserts.py`: injection-proof SQL inserts (Postgres, MySQL, SQL Server), each statement verified before writing. CSV via DuckDB `COPY … TO 'x.csv'` still to add | SQL inserts working |

```bash
pip install duckdb pyyaml sqlmesh
python profiling/profile_source.py ../samples/tracker --out profile.json
python mapping/propose_mapping.py profile.json

pip install sqlglot pytest
python -m pytest deliver     # SQL injection tests; set MIGRATION_TEST_PG_DSN etc. to also test real databases
```
