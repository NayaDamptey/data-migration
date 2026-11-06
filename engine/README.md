# Recruitment System Data Migration

End-to-end data migration from a legacy recruitment CRM to a modern platform, built with DuckDB, Polars, Pydantic, and an LLM-powered schema mapping layer.

See [PROJECT.md](PROJECT.md) for full architecture, design decisions, and phase breakdown.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env          # add your Anthropic API key
python sample_data/generate.py
python sample_data/build_source_db.py --load   # builds RecruitCRM_Legacy in localhost\SQLEXPRESS from Source Schema.csv
python pipeline.py
streamlit run dashboard/app.py
```

## Tech Stack

- **DuckDB** — transformation engine
- **Polars** — data extraction and manipulation
- **Pydantic** — schema validation and data contracts
- **Claude API** — AI schema mapping, quality analysis, migration summaries
- **Streamlit** — migration dashboard
- **Faker** — sample data generation
- **pytest + GitHub Actions** — testing and CI
