# Migration engine

Legacy recruitment CRM (the fictional *Cobaltdesk*) → target platform migration, in Python and T-SQL.
The web UI (`../frontend`, `../backend`) uses it for data quality, duplicate review and SQL generation.

## Quick start

```bash
pip install -r requirements.txt
python sample_data/build_source_db.py          # rebuild the source CSVs and SQL scripts
python sample_data/build_source_db.py --load   # also load Cobaltdesk_Legacy into localhost\SQLEXPRESS (pyodbc)
python -m pytest tests -q                      # SQL Server tests skip themselves when no server is found
python mapping/generate_sql.py                 # T-SQL load scripts into sql/target/
```

## Tech stack

- **Python** with **DuckDB** for the data quality rules
- **T-SQL / SQL Server Express** for the source and target databases (via **pyodbc**)
- **pytest** and GitHub Actions
