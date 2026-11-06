# Recruitment System Data Migration

A data migration project that moves data from an outdated legacy recruitment system to a modern recruitment platform. Built with a modern data stack and an LLM-powered schema mapping layer.

---

## The Problem

The source system is an ageing recruitment CRM built on inconsistent design decisions accumulated over years — integer-based IDs tightly coupled to a single database, contact data scattered across multiple tables, no timezone awareness on timestamps, financial values stored as imprecise floats, and soft-delete logic applied differently across every table.

The target is a modern multi-tenant recruitment platform designed for scale: GUID-based identifiers, timezone-aware timestamps, precise decimal types for financial data, polymorphic communication and attachment patterns, and a clean separation between entities and their location or contact data.

Migrating between these two systems means resolving not just naming differences but fundamental data type and structural mismatches — without losing a single placement, candidate, or timesheet record in the process.

---

## Tech Stack

| Tool | Role |
|---|---|
| **DuckDB** | Core transformation engine — runs SQL in-process, reads CSVs and databases natively |
| **Polars** | Fast data extraction and manipulation |
| **Pydantic** | Schema validation and data contracts — every row is validated before load |
| **Claude API (Anthropic)** | LLM layer — schema mapping suggestions, data quality reports, migration summaries |
| **Streamlit** | Live migration dashboard — row counts, validation results, progress |
| **Faker** | Realistic fake data generation for development and testing |
| **Rich** | Terminal output formatting |
| **pytest + GitHub Actions** | Testing and CI |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        pipeline.py                          │
│                                                             │
│   ┌───────────┐    ┌─────────────┐    ┌─────────────────┐  │
│   │  Extract  │───▶│  Transform  │───▶│      Load       │  │
│   │ (Polars)  │    │  (DuckDB)   │    │ (Pydantic + SQL)│  │
│   └───────────┘    └─────────────┘    └─────────────────┘  │
│         │                │                     │            │
│         └────────────────┴─────────────────────┘           │
│                          │                                  │
│                          ▼                                  │
│              ┌───────────────────────┐                      │
│              │   Claude API Layer    │                      │
│              │                       │                      │
│              │  • Schema Mapper      │                      │
│              │  • Quality Analyst    │                      │
│              │  • Summary Generator  │                      │
│              └───────────────────────┘                      │
│                          │                                  │
│                          ▼                                  │
│              ┌───────────────────────┐                      │
│              │  Streamlit Dashboard  │                      │
│              └───────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

---

## LLM Features

### 1. AI Schema Mapper
Feeds both source and target schemas to Claude and returns a suggested field mapping with confidence scores, transform rules, and reasoning. Output is written to `mapping/field_mapping.csv` and can be reviewed and edited before the migration runs.

```
Source: Accounts.Account_name       →  Target: Company.CompanyName
Confidence: 0.97 | Transform: Direct copy
Reasoning: Name similarity and matching client/company context

Source: Associates.AssociateID      →  Target: Applicant.ApplicantID
Confidence: 0.71 | Transform: CAST + GUID generation (INT → NVARCHAR)
Reasoning: Both are person identifiers but type mismatch requires transform
```

### 2. Data Quality Analyst
After extraction, samples the raw source data and produces a human-readable quality report — flagging nulls, type mismatches, outliers, and format inconsistencies, with suggested cleaning rules for each issue found.

### 3. Migration Summary Generator
After the migration completes, reads the validation results and writes a plain-English executive summary covering rows migrated, issues encountered, data loss risk, and recommendations.

---

## Project Structure

```
recruitment-data-migration/
│
├── schemas/
│   ├── source_schema.csv          # Legacy system schema
│   └── target_schema.csv          # Target system schema
│
├── mapping/
│   └── field_mapping.csv          # Source → Target column mapping with transform rules
│
├── scripts/
│   ├── extract/
│   │   └── extractor.py           # Pulls data from source using Polars
│   ├── transform/
│   │   └── transformer.py         # DuckDB SQL transformations
│   └── load/
│       └── loader.py              # Pydantic-validated load into target
│
├── llm/
│   ├── schema_mapper.py           # AI-powered field mapping suggestions
│   ├── quality_analyst.py         # LLM data quality report generation
│   └── summary_generator.py       # Post-migration plain-English summary
│
├── validation/
│   └── validator.py               # Row counts, nulls, FK checks, business rules
│
├── sample_data/
│   └── generate.py                # Faker-based realistic data generator
│
├── dashboard/
│   └── app.py                     # Streamlit migration progress dashboard
│
├── tests/
│   ├── test_transform.py
│   ├── test_validation.py
│   └── test_load.py
│
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions — runs tests on every push
│
├── pipeline.py                    # Single entry point — runs the full migration
├── requirements.txt
├── .env.example
└── README.md
```

---

## Pipeline Phases

### Phase 1 — Schema Mapping
- Run the AI schema mapper against both schema CSVs
- Review and confirm the generated `field_mapping.csv`
- Document any transforms that require custom logic

### Phase 2 — Sample Data Generation
- Generate realistic fake data for all source tables using Faker
- Intentionally seed dirty data: nulls in required fields, type mismatches, duplicate records
- This validates that the pipeline handles real-world data conditions

### Phase 3 — Extract
- Load source data into Polars DataFrames
- Run initial profiling: row counts per table, null rates, data type distribution
- Feed a sample to the LLM Data Quality Analyst

### Phase 4 — Transform
- Execute DuckDB SQL transformations based on the field mapping
- Handle type conversions (e.g. INT → NVARCHAR for IDs)
- Apply cleaning rules from the quality report
- Resolve naming convention differences between source and target

### Phase 5 — Validate
- Row count reconciliation: source count must equal target count
- Null checks on all non-nullable target columns
- Foreign key integrity checks across all junction tables
- Business rule checks (e.g. every Placement links to a valid Applicant and Position)

### Phase 6 — Load
- Validate each row against Pydantic target schema models
- Load validated data into the target database
- Any row failing Pydantic validation is written to a rejection log with the reason

### Phase 7 — Report
- LLM Summary Generator reads validation results and rejection log
- Produces a plain-English migration report
- Streamlit dashboard displays final state: rows loaded, rows rejected, validation pass rate

---

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in your API key
cp .env.example .env

# Generate sample source data
python sample_data/generate.py

# Run the AI schema mapper (optional — mapping already provided)
python llm/schema_mapper.py

# Run the full migration pipeline
python pipeline.py

# View the dashboard
streamlit run dashboard/app.py
```

---

## Validation Checks

| Check | Description |
|---|---|
| Row count | Total rows in source = total rows in target per table |
| Null check | All non-nullable target columns have no nulls after load |
| FK integrity | Every FK value in child table exists in parent table |
| Type check | All columns match their declared Pydantic type |
| Duplicate check | No duplicate PKs in any target table |
| Business rules | Every Placement has a Applicant, Position, and Company |

---

## Key Migration Mappings (Source → Target)

| Source Table | Target Table | Notes |
|---|---|---|
| Accounts | Company | Direct equivalent — client organisations |
| Associates | Contact + Applicant | Split based on Associate type flag |
| Person | Applicant | Candidates — type change on ID column |
| Recruiter | User | System users |
| Req | Position + Position_Details | Job split across two target tables |
| Req_Hired | Placements | Hired records become placements |
| Req_Rates | Position (rate columns) | Rate data folded into Position |
| GDPR_Consent | Marketing | Consent flags mapped to marketing preferences |
| CV_Docs + Documents | Attachments + junction tables | Unified into target attachment pattern |
| EmpHist | Work_History | Employment history |
| EmpEdu | Mapped to Applicant notes | No direct target equivalent |
| TimeSheets + TimesheetItems | Timesheets + TimesheetActivity | Direct structural equivalent |
| PONo | PurchaseOrder + PurchaseOrderItems | PO header and line items split |

---

## What This Demonstrates

- **Data engineering fundamentals** — extract, transform, validate, load done properly
- **Modern tooling** — DuckDB and Polars over legacy pandas/SQLAlchemy
- **Data contracts** — Pydantic validation before every load, not after
- **AI-augmented engineering** — LLM used practically, not as a gimmick
- **Production thinking** — rejection logs, reconciliation checks, CI pipeline
- **Domain knowledge** — understanding of a real recruitment system's data model
