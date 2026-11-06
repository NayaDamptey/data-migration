"""
sample_data/generate_ai.py

Generates the entire source database using Claude AI.
Every record is realistic and internally consistent:
  - Names match emails and addresses
  - Associate tags are real recruitment tags
  - Notes are contextually appropriate
  - All FK references link to valid records
  - Addresses are real UK cities/postcodes

Output: sample_data/source/<TableName>.csv
Run:    python sample_data/generate_ai.py

Cost estimate: ~$0.50-1.50 from your API balance.
"""

import csv
import json
import os
import random
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()

SOURCE_DIR  = Path(__file__).parent / "source"
SCHEMA_FILE = Path(__file__).parent.parent / "Source Schema.csv"
SOURCE_DIR.mkdir(parents=True, exist_ok=True)

console = Console()
client  = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
random.seed(42)


# ── load source schema so generated columns match exactly ────────────────────

def load_schema() -> dict[str, list[str]]:
    """
    Reads Source Schema.csv and returns {TableName: [col1, col2, ...]}
    Used to validate generated rows and ensure column names match the schema.
    """
    schema: dict[str, list[str]] = {}
    if not SCHEMA_FILE.exists():
        console.print(f"[yellow]Warning: Source Schema.csv not found at {SCHEMA_FILE}[/yellow]")
        return schema
    with open(SCHEMA_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table = row["TableName"].strip()
            col   = row["Column"].strip()
            schema.setdefault(table, []).append(col)
    console.print(f"  [dim]Schema loaded: {len(schema)} tables[/dim]")
    return schema

SOURCE_SCHEMA: dict[str, list[str]] = {}   # populated in main()


def conform_to_schema(table: str, rows: list[dict]) -> list[dict]:
    """
    Ensures every row has exactly the columns defined in Source Schema.csv.
    - Missing columns are added as empty string
    - Extra columns (hallucinated by Claude) are removed
    - Logs any discrepancies so they're visible
    """
    expected = SOURCE_SCHEMA.get(table)
    if not expected or not rows:
        return rows

    row_keys   = set(rows[0].keys())
    schema_set = set(expected)
    missing    = schema_set - row_keys
    extra      = row_keys - schema_set

    if missing:
        console.print(f"  [yellow]  {table}: adding missing cols {sorted(missing)}[/yellow]")
    if extra:
        console.print(f"  [yellow]  {table}: dropping extra cols {sorted(extra)}[/yellow]")

    conformed = []
    for row in rows:
        new_row = {col: row.get(col, "") for col in expected}
        conformed.append(new_row)
    return conformed


def write_csv(name: str, rows: list[dict]):
    if not rows:
        console.print(f"  [yellow]SKIP[/yellow] {name} (no rows)")
        return
    rows = conform_to_schema(name, rows)   # align to schema before writing
    path = SOURCE_DIR / f"{name}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"  [green]OK[/green]   {name}.csv  ({len(rows)} rows)")


# ── global context — tracks all generated IDs for FK references ───────────────
ctx: dict = {
    "roles":           [],   # [{id, description}]
    "division_ids":    [],
    "dept_ids":        [],
    "skill_cat_ids":   [],
    "skill_ids":       [],
    "comp_type_ids":   [],
    "address_ids":     [],
    "recruiter_ids":   [],
    "recruiter_emails":{},   # id -> email
    "recruiter_names": {},   # id -> name
    "account_ids":     [],
    "person_ids":      [],
    "associate_ids":   [],
    "req_ids":         [],
    "hired_ids":       [],
    "emp_ids":         [],
    "cv_doc_ids":      [],
    "doc_ids":         [],
    "invoice_ids":     [],
    "po_numbers":      [],
    "ts_ids":          [],
    "hotlist_ids":     [],
    "referee_ids":     [],
    "tag_ids":         [],
    "hotlist_ids":     [],
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def write_csv(name: str, rows: list[dict]):
    if not rows:
        console.print(f"  [yellow]SKIP[/yellow] {name} (no rows)")
        return
    path = SOURCE_DIR / f"{name}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"  [green]OK[/green]   {name}.csv  ({len(rows)} rows)")


SYSTEM_CONTEXT = """
You are a senior data consultant who has been handed the source database schema for Bridge Talent Ltd,
a UK IT and professional services recruitment agency based in London with offices in Manchester and Birmingham.
Your job is to populate this database with realistic, production-quality data as if this were a live system
that has been running for 5+ years.

AGENCY BACKGROUND:
Bridge Talent Ltd specialises in placing IT contractors and permanent staff at UK financial services,
technology, healthcare, and engineering organisations. They have 30 staff, ~200 active client accounts,
~500 registered candidates, and process around 400 job requisitions per year.
The agency operates under UK employment law, IR35 regulations, and GDPR.

DATABASE ENTITIES — understand these relationships before generating any data:
- Recruiter     : Bridge Talent's own staff (the agency employees). Email domain: @bridgetalent.co.uk
- Accounts      : CLIENT companies that hire through Bridge Talent (e.g. Barclays, NHS Digital, BAE Systems)
- Associates    : CONTACTS at those client companies — the hiring managers and HR directors the agency calls
                  Associates are NOT candidates. They work at the client company, not the agency.
- Person        : CANDIDATES registered with Bridge Talent — IT contractors, finance professionals, engineers
                  seeking contract or permanent roles
- Req           : Job requisitions raised by client companies through their Associate contact
- Req_Hired     : Candidates placed or in the pipeline for a specific Req
- Req_Rates     : Pay rate, bill rate, and salary for each Req
- GDPR_Consent  : Consent flags per candidate — whether they allow contact by email/phone/text
- Emp_Profile   : Employment profile for placed candidates (NI number, bank details, emp type)
- EmpHist       : Previous employment history for candidates
- Notes         : CRM activity notes — call logs, email summaries, meeting notes per entity
- Leads         : New business development leads the agency is pursuing

COHERENCE RULES — every field must make sense in context:
1. Names → Emails: claire.hutchinson@lloydsbankinggroup.com must match "Claire Hutchinson" at "Lloyds Banking Group"
2. Job titles → Skills: A "Senior Python Developer" req must require Python, SQL, and cloud skills
3. Status → Dates: An "Active" job must have a future expiry date. A "Filled" job must have a past end date.
4. Placement logic: Hired_Status=1 means placed. Pipeline_Stage must match (Placed/Rejected/Interview etc.)
5. Addresses: London addresses must have London postcodes (EC, WC, E, N, W, SE, SW, NW, SE).
              Manchester must have M postcodes. Birmingham B postcodes. Never mix cities and postcodes.
6. Rates: Contract roles have a day rate (Payrate/BillRate). Permanent roles have a Salary. Not both.
7. Recruiter hierarchy: Directors report to nobody. Managers report to Directors. Consultants to Managers.
8. FK integrity: Every foreign key must point to a record that exists.
9. GDPR: If Email consent = 0, the agency cannot email that candidate. Notes should reflect this.
10. Realistic UK business norms: 30-day payment terms standard, PSL (preferred supplier list) agreements,
    IR35 determinations for contractors, NI numbers in AB123456C format, UK mobile numbers +44 7XXX XXXXXX.

Generate data as if you are filling in a real database that recruiters use every day.
Every record should feel like it was entered by a real person about a real situation.
"""

def ask(prompt: str, max_tokens: int = 4000) -> list | dict:
    """
    Call Claude and parse JSON response.
    - On JSON truncation: doubles max_tokens and retries (up to 3 attempts)
    - On API error: waits and retries
    - Never raises — returns [] on total failure so the script keeps running
    """
    full_prompt = (
        SYSTEM_CONTEXT
        + "\n\n"
        + prompt
        + "\n\nIMPORTANT: Respond with valid JSON only. "
        "No markdown, no code fences, no explanation."
    )
    token_limit = max_tokens
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=min(token_limit, 8096),
                messages=[{"role": "user", "content": full_prompt}],
            )
            text = msg.content[0].text.strip()
            text = re.sub(r"^```[a-z]*\n?|```$", "", text, flags=re.MULTILINE).strip()
            return json.loads(text)
        except json.JSONDecodeError:
            # Response was truncated — double the token budget and retry
            token_limit = min(token_limit * 2, 8096)
            console.print(f"  [yellow]JSON truncated — retry {attempt+1}/3 with {token_limit} tokens[/yellow]")
            time.sleep(1)
        except Exception as e:
            console.print(f"  [yellow]API error (attempt {attempt+1}/3): {type(e).__name__}[/yellow]")
            time.sleep(3)
    console.print("  [red]Batch failed after 3 attempts — skipping (other batches will continue)[/red]")
    return []


def ask_chunked(prompt_fn, start_batch: int, max_tokens: int = 4000) -> list:
    """
    Calls ask() with automatic batch size halving if the batch fails.
    prompt_fn(n) must return the prompt string for n items.
    Tries: start_batch → start_batch//2 → start_batch//4 → gives up.
    """
    batch = start_batch
    while batch >= 3:
        result = ask(prompt_fn(batch), max_tokens)
        if result:
            return result
        batch = batch // 2
        console.print(f"  [yellow]Halving batch to {batch} and retrying...[/yellow]")
        time.sleep(1)
    console.print("  [red]Could not generate batch even at minimum size — skipping[/red]")
    return []


def name_to_email(fullname: str, domain: str) -> str:
    parts = re.sub(r"[^a-zA-Z\s]", "", fullname).strip().lower().split()
    local = f"{parts[0]}.{parts[-1]}" if len(parts) >= 2 else (parts[0] if parts else "user")
    local = re.sub(r"[^a-z0-9.]", "", local)[:30]
    return f"{local}@{domain}"


def pick(pool: list):
    return random.choice(pool) if pool else None


def maybe(value, pct_null: float = 0.15):
    return "" if random.random() < pct_null else value


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — LOOKUP / REFERENCE TABLES
# ══════════════════════════════════════════════════════════════════════════════

def gen_lookups():
    console.print("\n[bold cyan]Phase 1 — Lookup tables[/bold cyan]")

    # Roles
    roles = [
        {"Role_ID": 1, "Description": "Admin",      "RoleCode": "ADM"},
        {"Role_ID": 2, "Description": "Recruiter",  "RoleCode": "REC"},
        {"Role_ID": 3, "Description": "Manager",    "RoleCode": "MGR"},
        {"Role_ID": 4, "Description": "Director",   "RoleCode": "DIR"},
        {"Role_ID": 5, "Description": "Consultant", "RoleCode": "CON"},
    ]
    write_csv("Roles", roles)
    ctx["roles"] = roles
    ctx["role_ids"] = [r["Role_ID"] for r in roles]

    # Division
    divisions = [
        {"DivisionID": 1, "Division_Name": "UK",       "CreatedBy": 1, "CreatedAt": "2020-01-01 09:00:00", "Deleted": 0},
        {"DivisionID": 2, "Division_Name": "Europe",   "CreatedBy": 1, "CreatedAt": "2020-01-01 09:00:00", "Deleted": 0},
        {"DivisionID": 3, "Division_Name": "Americas", "CreatedBy": 1, "CreatedAt": "2020-01-01 09:00:00", "Deleted": 0},
        {"DivisionID": 4, "Division_Name": "APAC",     "CreatedBy": 1, "CreatedAt": "2020-01-01 09:00:00", "Deleted": 0},
    ]
    write_csv("Division", divisions)
    ctx["division_ids"] = [d["DivisionID"] for d in divisions]

    # Departments
    departments = [
        {"DepartmentID": 1, "Name": "Technology",     "CreatedAt": "2020-01-01 09:00:00", "UpdatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "Deleted": 0},
        {"DepartmentID": 2, "Name": "Finance",        "CreatedAt": "2020-01-01 09:00:00", "UpdatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "Deleted": 0},
        {"DepartmentID": 3, "Name": "Human Resources","CreatedAt": "2020-01-01 09:00:00", "UpdatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "Deleted": 0},
        {"DepartmentID": 4, "Name": "Sales",          "CreatedAt": "2020-01-01 09:00:00", "UpdatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "Deleted": 0},
        {"DepartmentID": 5, "Name": "Operations",     "CreatedAt": "2020-01-01 09:00:00", "UpdatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "Deleted": 0},
    ]
    write_csv("Departments", departments)
    ctx["dept_ids"] = [d["DepartmentID"] for d in departments]

    # DocumentType
    doc_types = [
        {"Doc_TypeID": 1, "Desc": "CV"},
        {"Doc_TypeID": 2, "Desc": "Contract"},
        {"Doc_TypeID": 3, "Desc": "Identity Document"},
        {"Doc_TypeID": 4, "Desc": "Certificate"},
        {"Doc_TypeID": 5, "Desc": "Other"},
    ]
    write_csv("DocumentType", doc_types)

    # Languages
    langs = [
        {"ID": i, "Language": l}
        for i, l in enumerate(["English","French","Spanish","Arabic","Mandarin",
                                "German","Portuguese","Urdu","Polish","Italian"], 1)
    ]
    write_csv("Languages", langs)

    # AccountType
    acct_types = [
        {"AccountTypeID": 1, "Description": "Client",    "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "UpdatedBy": 1, "Active": 1, "Deleted": 0},
        {"AccountTypeID": 2, "Description": "Prospect",  "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "UpdatedBy": 1, "Active": 1, "Deleted": 0},
        {"AccountTypeID": 3, "Description": "Partner",   "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "UpdatedBy": 1, "Active": 1, "Deleted": 0},
        {"AccountTypeID": 4, "Description": "Agency",    "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1, "UpdatedBy": 1, "Active": 1, "Deleted": 0},
    ]
    write_csv("AccountType", acct_types)

    # AccountStatus
    acct_statuses = [
        {"Account_StatusID": 1, "Description": "Active",    "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1},
        {"Account_StatusID": 2, "Description": "On Hold",   "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1},
        {"Account_StatusID": 3, "Description": "Closed",    "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1},
        {"Account_StatusID": 4, "Description": "Prospect",  "CreatedAt": "2020-01-01 09:00:00", "CreatedBy": 1},
    ]
    write_csv("AccountStatus", acct_statuses)

    # SkillCategory + Skills
    skill_cats = [
        {"CategoryID": 1, "Name": "Software Development", "Deleted": 0},
        {"CategoryID": 2, "Name": "Data & Analytics",     "Deleted": 0},
        {"CategoryID": 3, "Name": "Project Management",   "Deleted": 0},
        {"CategoryID": 4, "Name": "Sales & Business Dev", "Deleted": 0},
        {"CategoryID": 5, "Name": "Finance & Accounting", "Deleted": 0},
    ]
    write_csv("SkillCategory", skill_cats)
    ctx["skill_cat_ids"] = [s["CategoryID"] for s in skill_cats]

    skills_data = [
        {"SkillID": 1,  "SkillName": "Python",              "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 2,  "SkillName": "SQL",                 "Skill_CategoryID": 2, "Deleted": 0},
        {"SkillID": 3,  "SkillName": "Java",                "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 4,  "SkillName": "C#",                  "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 5,  "SkillName": "Azure",               "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 6,  "SkillName": "AWS",                 "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 7,  "SkillName": "Power BI",            "Skill_CategoryID": 2, "Deleted": 0},
        {"SkillID": 8,  "SkillName": "Agile / Scrum",       "Skill_CategoryID": 3, "Deleted": 0},
        {"SkillID": 9,  "SkillName": "Salesforce",          "Skill_CategoryID": 4, "Deleted": 0},
        {"SkillID": 10, "SkillName": "Recruitment",         "Skill_CategoryID": 4, "Deleted": 0},
        {"SkillID": 11, "SkillName": "Financial Modelling", "Skill_CategoryID": 5, "Deleted": 0},
        {"SkillID": 12, "SkillName": "React",               "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 13, "SkillName": "Node.js",             "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 14, "SkillName": "Data Analysis",       "Skill_CategoryID": 2, "Deleted": 0},
        {"SkillID": 15, "SkillName": "Project Management",  "Skill_CategoryID": 3, "Deleted": 0},
        {"SkillID": 16, "SkillName": "Business Development","Skill_CategoryID": 4, "Deleted": 0},
        {"SkillID": 17, "SkillName": "Excel / VBA",         "Skill_CategoryID": 5, "Deleted": 0},
        {"SkillID": 18, "SkillName": "Tableau",             "Skill_CategoryID": 2, "Deleted": 0},
        {"SkillID": 19, "SkillName": "DevOps / CI-CD",      "Skill_CategoryID": 1, "Deleted": 0},
        {"SkillID": 20, "SkillName": "Communication",       "Skill_CategoryID": 4, "Deleted": 0},
    ]
    write_csv("Skills", skills_data)
    ctx["skill_ids"] = [s["SkillID"] for s in skills_data]

    # Categories — describe what TYPE of tag it is (not industry)
    tag_categories = [
        {"Category_ID": 1, "Cat_Name": "Candidate Status",   "CreatedBy": 1, "CreatedAt": "2021-01-01 09:00:00", "Deleted": 0},
        {"Category_ID": 2, "Cat_Name": "Client & Account",   "CreatedBy": 1, "CreatedAt": "2021-01-01 09:00:00", "Deleted": 0},
        {"Category_ID": 3, "Cat_Name": "Compliance & Legal", "CreatedBy": 1, "CreatedAt": "2021-01-01 09:00:00", "Deleted": 0},
        {"Category_ID": 4, "Cat_Name": "Job Preference",     "CreatedBy": 1, "CreatedAt": "2021-01-01 09:00:00", "Deleted": 0},
        {"Category_ID": 5, "Cat_Name": "Relationship",       "CreatedBy": 1, "CreatedAt": "2021-01-01 09:00:00", "Deleted": 0},
    ]
    write_csv("Categories", tag_categories)

    # Tags — each mapped to the correct category
    tags = [
        # Candidate Status (CategoryID 1)
        {"ID": 1,  "Tag_Name": "Hot Candidate",       "CategoryID": 1, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        {"ID": 2,  "Tag_Name": "Graduate",             "CategoryID": 1, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        {"ID": 3,  "Tag_Name": "Senior Level",         "CategoryID": 1, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        # Client & Account (CategoryID 2)
        {"ID": 4,  "Tag_Name": "VIP Client",           "CategoryID": 2, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        {"ID": 5,  "Tag_Name": "Key Account",          "CategoryID": 2, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        # Compliance & Legal (CategoryID 3)
        {"ID": 6,  "Tag_Name": "Do Not Contact",       "CategoryID": 3, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        {"ID": 7,  "Tag_Name": "Visa Sponsorship Req", "CategoryID": 3, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        # Job Preference (CategoryID 4)
        {"ID": 8,  "Tag_Name": "Contract Only",        "CategoryID": 4, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        {"ID": 9,  "Tag_Name": "Permanent Only",       "CategoryID": 4, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        {"ID": 10, "Tag_Name": "Willing to Relocate",  "CategoryID": 4, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        # Relationship (CategoryID 5)
        {"ID": 11, "Tag_Name": "Referred by Client",   "CategoryID": 5, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
        {"ID": 12, "Tag_Name": "Ex-Placed Candidate",  "CategoryID": 5, "CreatedBy": 1, "CreatedAt": "2021-03-01 09:00:00", "Deleted": 0},
    ]
    write_csv("Tags", tags)
    ctx["tag_ids"] = [t["ID"] for t in tags]

    # TimesheetType
    write_csv("TimesheetType", [
        {"Timesheet_TypeID": 1, "Desc": "Regular",      "Billable": 1, "Requires_Approval": 0},
        {"Timesheet_TypeID": 2, "Desc": "Overtime",     "Billable": 1, "Requires_Approval": 1},
        {"Timesheet_TypeID": 3, "Desc": "Training",     "Billable": 0, "Requires_Approval": 1},
        {"Timesheet_TypeID": 4, "Desc": "Sick Leave",   "Billable": 0, "Requires_Approval": 0},
        {"Timesheet_TypeID": 5, "Desc": "Bank Holiday", "Billable": 0, "Requires_Approval": 0},
    ])

    # InvoiceTypes
    write_csv("InvoiceTypes", [
        {"InvoiceType_ID": 1, "Type_Name": "Placement Fee", "Desc": "One-off permanent placement invoice", "CreatedBy": 1, "UpdatedBy": 1, "Deleted": 0},
        {"InvoiceType_ID": 2, "Type_Name": "Timesheet",     "Desc": "Weekly contractor timesheet invoice",  "CreatedBy": 1, "UpdatedBy": 1, "Deleted": 0},
        {"InvoiceType_ID": 3, "Type_Name": "Credit Note",   "Desc": "Invoice correction or reversal",       "CreatedBy": 1, "UpdatedBy": 1, "Deleted": 0},
    ])

    # WebForms
    write_csv("WebForms", [
        {"FormID": i, "Form_Name": n, "Desc": d, "Deleted": 0, "CreatedAt": "2021-01-01 09:00:00", "UpdatedAt": "2021-01-01 09:00:00"}
        for i, (n, d) in enumerate([
            ("Candidate Registration", "New candidate self-registration form"),
            ("Job Application",        "Standard job application form"),
            ("Client Enquiry",         "Inbound client interest form"),
            ("Timesheet Submission",   "Contractor weekly timesheet form"),
            ("Reference Request",      "Automated reference collection form"),
        ], 1)
    ])

    # ComplianceTypes / ComplianceDocuments
    write_csv("ComplianceTypes", [
        {"Compliance_typeID": 1, "Name": "Right to Work"},
        {"Compliance_typeID": 2, "Name": "DBS Check"},
        {"Compliance_typeID": 3, "Name": "Reference Check"},
    ])
    ctx["comp_type_ids"] = [1, 2, 3]

    write_csv("ComplianceDocuments", [
        {"Comp_DocId": 1, "Desc": "Passport Copy"},
        {"Comp_DocId": 2, "Desc": "DBS Certificate"},
        {"Comp_DocId": 3, "Desc": "Reference Letter"},
        {"Comp_DocId": 4, "Desc": "National Insurance Card"},
        {"Comp_DocId": 5, "Desc": "Visa Document"},
    ])

    # Sectors
    industries = ["Technology","Finance","Healthcare","Retail","Engineering",
                  "Legal","Education","Construction","Media","Logistics"]
    write_csv("Sectors", [
        {"ID": i, "Desc": s, "ObjectID": i, "ObjectType": "Account",
         "CreatedAt": "2021-01-01 09:00:00", "UpdatedAt": "2021-01-01 09:00:00",
         "CreatedBy": 1, "UpdatedBy": 1, "Deleted": 0}
        for i, s in enumerate(industries, 1)
    ])


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — RECRUITERS
# ══════════════════════════════════════════════════════════════════════════════

def gen_recruiters():
    console.print("\n[bold cyan]Phase 2 — Recruiters[/bold cyan]")

    data = ask("""
Generate 30 staff members at Bridge Talent Ltd, a UK IT and professional services recruitment agency
based in London with regional offices in Manchester and Birmingham.

Org structure (strict reporting lines):
- 2 Managing Directors (Role_ID 4) — ReportsTo: ""
- 4 Division Managers (Role_ID 3) — report to MDs (IDs 1-2)
- 18 Recruiters / Consultants (Role_ID 2) — report to Managers (IDs 3-6)
- 4 Resourcers / Admins (Role_ID 1) — report to Managers (IDs 3-6)
- 2 Senior Consultants (Role_ID 5) — report to Managers

Use diverse but realistic British names (mix of English, Scottish, South Asian, and European names).
Email format: firstname.lastname@bridgetalent.co.uk — derived strictly from Fullname.
Username: first initial + last name lowercase (e.g. jsmith).
CreatedAt: between 2018 and 2022 (when they joined the agency).
UpdatedAt: more recent than CreatedAt.

Return a JSON array of 30 objects:
{
  "RecruiterID": 1,
  "Username": "spatel",
  "Role_ID": 4,
  "Fullname": "Sunita Patel",
  "email": "sunita.patel@bridgetalent.co.uk",
  "ReportsTo": "",
  "CreatedAt": "2018-04-10 09:00:00",
  "UpdatedAt": "2023-06-01 10:00:00",
  "Password": "hashed_placeholder"
}
""", max_tokens=5000)

    rows = []
    for r in data:
        r["RecruiterID"] = int(r["RecruiterID"])
        r["Role_ID"]     = int(r.get("Role_ID", 2))
        if r.get("ReportsTo") in ("", None, "null"):
            r["ReportsTo"] = ""
        rows.append(r)

    write_csv("Recruiter", rows)
    ctx["recruiter_ids"]    = [r["RecruiterID"] for r in rows]
    ctx["recruiter_emails"] = {r["RecruiterID"]: r["email"] for r in rows}
    ctx["recruiter_names"]  = {r["RecruiterID"]: r["Fullname"] for r in rows}


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — ADDRESSES
# ══════════════════════════════════════════════════════════════════════════════

def gen_addresses():
    console.print("\n[bold cyan]Phase 3 — Addresses[/bold cyan]")

    all_rows = []
    addr_id = 1

    # Need enough addresses for: 200 accounts + overflow for associates/reqs
    for batch_start in range(0, 250, 10):
        batch_count = min(10, 250 - batch_start)
        data = ask(f"""
Generate {batch_count} realistic UK business addresses for a recruitment database.
These are office addresses for client companies and candidate home/work addresses.
Mix of: London (City, Canary Wharf, West End, Shoreditch), Manchester (Spinningfields, MediaCityUK),
Birmingham (Brindleyplace, Colmore Row), Leeds (City Centre), Bristol (Temple Quarter),
Edinburgh (New Town, Quartermile), Glasgow (City Centre), Reading, Cambridge, Oxford, Sheffield.

Postcode rules:
- London EC/WC: EC1A 1BB, WC2N 5DU style
- London E/N/W/SE/SW/NW: E14 5AB, N1 9GU style
- Manchester: M1 1AE, M2 3BQ style
- Birmingham: B1 1BB, B2 4QA style
- Use correct postcode district for the city — do NOT use London postcodes for Manchester

Phone format: +44 20 XXXX XXXX for London landlines, +44 161 XXX XXXX for Manchester,
+44 121 XXX XXXX for Birmingham. Mobile: +44 7XXX XXXXXX.
Longitude/Latitude: accurate for the city (London ~51.51, -0.12 / Manchester ~53.48, -2.24).
IDs start at {addr_id}.

Return a JSON array of {batch_count} objects:
{{
  "AddressID": {addr_id},
  "Address_line1": "12 Bishopsgate",
  "Address_line2": "Floor 22",
  "City": "London",
  "ZipCode": "EC2N 4AJ",
  "Province": "Greater London",
  "Country": "United Kingdom",
  "Email": "info@example.co.uk",
  "Phone": "+44 20 7283 4500",
  "OtherPhone": "",
  "WorkPhone": "+44 20 7283 4501",
  "Longitude": -0.0822,
  "Latitude": 51.5155,
  "CreatedAt": "2020-01-15 09:00:00",
  "CreatedBy": 1
}}
""", max_tokens=3000)

        for row in data:
            row["AddressID"] = addr_id
            all_rows.append(row)
            addr_id += 1
        time.sleep(0.3)

    write_csv("Addresses", all_rows)
    ctx["address_ids"]   = [r["AddressID"] for r in all_rows]
    ctx["address_rows"]  = {r["AddressID"]: r for r in all_rows}  # id → full row for city lookups


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — ACCOUNTS (COMPANIES)
# ══════════════════════════════════════════════════════════════════════════════

def gen_accounts():
    console.print("\n[bold cyan]Phase 4 — Accounts (Companies)[/bold cyan]")

    industries = ["Technology","Finance","Healthcare","Retail","Engineering",
                  "Legal","Education","Construction","Media","Logistics"]
    all_rows = []
    acct_id = 1

    for batch_start in range(0, 200, 10):
        batch_count = min(10, 200 - batch_start)
        data = ask(f"""
Generate {batch_count} realistic UK client companies for a recruitment CRM at Bridge Talent Ltd.
These are organisations that hire IT contractors and permanent staff through the agency.

Company name rules:
- Technology: use names like "Apex Systems Ltd", "Meridian Tech", "Quantum Analytics", "Vertex Cloud Solutions"
- Finance: "Hargreaves Capital", "Pinnacle Asset Management", "Sterling Financial Group"
- Healthcare: "MedCore Solutions", "Nexus Health Systems", "Vital Care Group"
- Legal: "Ashfield Law LLP", "Meridian Legal Partners", "Crown Solicitors"
- Names must end with Ltd, PLC, LLP, Group, or Solutions where appropriate

About field: 2-3 sentences — company size (e.g. 500-person fintech, FTSE 250 retailer),
what they do, and why they use Bridge Talent for hiring. Sound like LinkedIn company description.

AccountTypeID distribution: 60% Client (1), 20% Prospect (2), 10% Partner (3), 10% Agency (4).
AccountStatusTypeID: 70% Active (1), 15% Prospect (4), 10% On Hold (2), 5% Closed (3).
Terms: 30 days for most clients, 60 days for large enterprises, 14 days for agencies.
NoticePeriod: weeks of notice required — 4, 8, or 12 for most.
Note: internal account notes like "Preferred supplier agreement signed Q2 2022" or "".

Industries: {industries}.
IDs start at {acct_id}.
Recruiter IDs (account owners): {ctx['recruiter_ids'][:10]}.
Address IDs: {ctx['address_ids'][batch_start:batch_start+batch_count+5]}.
DivisionID: 1=UK, 2=Europe, 3=Americas, 4=APAC. DeptID: 1-5.

Return JSON array of {batch_count} objects:
{{
  "Account_ID": {acct_id},
  "Account_name": "Apex Systems Ltd",
  "AccountTypeID": 1,
  "AccountStatusTypeID": 1,
  "DeptID": 1,
  "AccountReferenceNo": 10234,
  "Terms": "30 days",
  "Website": "https://www.apexsystems.co.uk",
  "AddressID": 3,
  "Division_ID": 1,
  "About": "Apex Systems is a 350-person cloud and data engineering consultancy headquartered in London's City district. They specialise in AWS migrations and real-time data platforms for FTSE 100 clients. Bridge Talent has been their preferred IT contractor supplier since 2021.",
  "ParentAccountID": "",
  "InvoiceAddressID": 3,
  "CreatedAt": "2020-05-12 09:00:00",
  "UpdatedAt": "2023-02-20 14:30:00",
  "Note": "Preferred supplier agreement in place. Key contact is the Head of TA.",
  "Industry": "Technology",
  "CreatedBy": 2,
  "UpdatedBy": 3,
  "NoticePeriod": 4,
  "RateID": "",
  "Deleted": 0
}}
""", max_tokens=6000)

        for row in data:
            row["Account_ID"] = acct_id
            # Assign addresses sequentially — each company gets its own address slot
            # This guarantees every account has a unique, valid address
            addr_idx = (acct_id - 1) % len(ctx["address_ids"])
            assigned_addr = ctx["address_ids"][addr_idx]
            row["AddressID"]        = assigned_addr
            row["InvoiceAddressID"] = assigned_addr   # invoice goes to same office by default
            row["ParentAccountID"]  = ""
            all_rows.append(row)
            acct_id += 1
        time.sleep(0.3)

    write_csv("Accounts", all_rows)
    ctx["account_ids"] = [r["Account_ID"] for r in all_rows]
    # Map account → its office address so Associates and Reqs inherit the right location
    ctx["account_address_map"] = {r["Account_ID"]: r["AddressID"] for r in all_rows}


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — PERSONS (CANDIDATES & CONTACTS)
# ══════════════════════════════════════════════════════════════════════════════

def gen_persons():
    console.print("\n[bold cyan]Phase 5 — Persons[/bold cyan]")

    all_rows = []
    person_id = 1

    for batch_start in range(0, 500, 15):
        batch_count = min(15, 500 - batch_start)
        data = ask(f"""
Generate {batch_count} realistic UK candidates and professionals for a recruitment database.
These are people registered with Bridge Talent Ltd — IT contractors, finance professionals,
engineers, and other professionals seeking work through the agency.

Name diversity: mix of English, Scottish, Welsh, Irish, South Asian (Indian, Pakistani),
Eastern European (Polish, Romanian), and West African names. All should sound natural for UK.

DOB rules:
- Graduates (22-26): DOB 1998-2002
- Mid-level (27-38): DOB 1985-1997
- Senior (39-55): DOB 1969-1985
- Most candidates should be mid-level (60%), senior (25%), graduate (15%)

Flag rules:
- Associate=1 means they are registered as a candidate/contractor with the agency
- Emp=1 means they have been placed and are currently on an active assignment
- Most should have Associate=1 (they registered with the agency)
- 30% should also have Emp=1 (currently placed)
- Deleted=1 for <5% (left the country, withdrew, or duplicate entry)
- IsArchived=1 for <8% (old inactive candidates not seen in 2+ years)

Recruiter IDs for CreatedBy/UpdatedBy: {ctx['recruiter_ids'][:8]}.
Department IDs: {ctx['dept_ids']}. Role IDs: {ctx['role_ids']}.
IDs start at {person_id}.

Return JSON array of {batch_count} objects:
{{
  "Person_ID": {person_id},
  "First_Name": "Priya",
  "Middle_name": "",
  "Last_Name": "Sharma",
  "DOB": "1991-09-14",
  "Account_Number": "",
  "GDPRConsent_ID": {person_id},
  "DeptID": 1,
  "Role_ID": 2,
  "CreatedAt": "2021-06-10 10:00:00",
  "UpdatedAt": "2023-01-15 11:30:00",
  "CreatedBy": 3,
  "UpdatedBy": 3,
  "Associate": 1,
  "Emp": 1,
  "Deleted": 0,
  "IsArchived": 0
}}
""", max_tokens=6000)

        for row in data:
            row["Person_ID"]      = person_id
            row["GDPRConsent_ID"] = person_id
            all_rows.append(row)
            person_id += 1
        time.sleep(0.3)

    write_csv("Person", all_rows)
    ctx["person_ids"] = [r["Person_ID"] for r in all_rows]
    ctx["persons"]    = all_rows


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — ASSOCIATES (CONTACTS)
# ══════════════════════════════════════════════════════════════════════════════

def gen_associates():
    console.print("\n[bold cyan]Phase 6 — Associates[/bold cyan]")

    # Associates are CONTACTS at client companies — e.g. HR managers, hiring managers,
    # finance directors — the people the agency deals with on the client side.
    contact_tags = [
        "Key decision maker", "Preferred contact", "CC on all comms",
        "Senior stakeholder", "Do not contact directly — go via PA",
        "Fast responder", "Budget holder", "New contact — nurture",
        "Met at industry event", "Referred by existing client",
        "Slow to respond — chase weekly", "VIP — handle with care",
        "Gatekeeping — needs relationship building", "Champion at account",
        "Secondary contact only",
    ]

    all_rows = []
    assoc_id = 1

    for batch_start in range(0, 300, 30):
        batch_count = min(30, 300 - batch_start)
        person_sample = ctx["person_ids"][batch_start:batch_start + batch_count]
        addr_sample   = ctx["address_ids"][batch_start:batch_start + batch_count]
        rec_sample    = ctx["recruiter_ids"][:8]

        data = ask(f"""
Generate {batch_count} client contact records for Bridge Talent Ltd's recruitment CRM.
These are the hiring managers, HR leads, and procurement contacts at client companies
that the agency's recruiters call, email, and meet with to win and manage business.

Job titles (AssociateTypeDescription should be "Contact"):
- Technology clients: Head of Engineering, VP Technology, IT Director, CTO, Lead Developer
- Finance: CFO, Finance Director, Head of Finance, FP&A Manager
- HR/Talent: Head of Talent Acquisition, HR Director, People & Culture Manager, Resourcing Lead
- Procurement: Procurement Manager, Vendor Manager, Supplier Relations Lead
- Operations: COO, Head of Operations, Programme Director

AssociateTitle: Mr/Ms/Mrs/Dr — match to name appropriately.
Associate_StatusID:
  1 = Active — currently engaged, receives calls/emails from Bridge Talent
  2 = Inactive — left their role or no longer engaging
  3 = On Hold — temporarily not recruiting
  4 = Blacklisted — had a bad experience, do not contact
Distribution: 65% Active, 20% Inactive, 10% On Hold, 5% Blacklisted.

Associate_Tag: pick from {contact_tags} — must match the status
  (Active contacts = "Key decision maker", "Budget holder" etc.
   Inactive = "Slow to respond", "Secondary contact only"
   Blacklisted = "Do not contact directly — go via PA").

Associate_RoleID: 3=Manager, 4=Director.
DeptID: match to their function (1=Tech, 2=Finance, 3=HR, 4=Sales, 5=Ops).

Person IDs (one per record): {person_sample}.
Address IDs (company office addresses): {addr_sample}.
Recruiter IDs (the Bridge Talent recruiter managing this contact): {rec_sample}.
Division IDs: {ctx['division_ids']}.
IDs start at {assoc_id}.

Return JSON array of {batch_count} objects:
{{
  "AssociateID": "{assoc_id}",
  "AssociateTitle": "Ms",
  "Person_ID": {person_sample[0] if person_sample else 1},
  "Associate_StatusID": 1,
  "DeptID": 3,
  "AssociateTypeDescription": "Contact",
  "Associate_AddressID": {addr_sample[0] if addr_sample else 1},
  "Associate_RoleID": 4,
  "Photo": "",
  "DivisionID": 1,
  "Active": 1,
  "Associate_Tag": "Key decision maker",
  "CreatedAt": "2021-07-01 09:00:00",
  "UpdatedAt": "2023-03-10 14:00:00",
  "CreatedBy": 2,
  "UpdatedBy": 2
}}
""", max_tokens=6000)

        for i, row in enumerate(data):
            row["AssociateID"] = str(assoc_id)
            row["Person_ID"]   = person_sample[i] if i < len(person_sample) else pick(ctx["person_ids"])

            # Use the address of the account this associate works at
            # This ensures the contact's address matches their company's office location
            linked_account = pick(ctx["account_ids"])
            row["Associate_AddressID"] = ctx["account_address_map"].get(
                linked_account, pick(ctx["address_ids"])
            )

            status = int(str(row.get("Associate_StatusID", 1)))
            row["Active"]  = 1 if status == 1 else 0
            row["Deleted"] = 1 if random.random() < 0.03 else 0
            all_rows.append(row)
            assoc_id += 1
        time.sleep(0.3)

    write_csv("Associates", all_rows)
    ctx["associate_ids"]    = [r["AssociateID"] for r in all_rows]
    ctx["active_assoc_ids"] = [r["AssociateID"] for r in all_rows
                                if r.get("Active") == 1 and r.get("Deleted") == 0]

    # AccountAssociates — link each associate to one company (their client site)
    aa_rows = []
    for i, aid in enumerate(ctx["associate_ids"][:250], 1):
        aa_rows.append({
            "AccountAssociateID": i,
            "AssociateID":        aid,
            "AccountID":          pick(ctx["account_ids"]),
        })
    write_csv("AccountAssociates", aa_rows)

    # AssociateTypes
    write_csv("AssociateTypes", [
        {"Associate_TypeID": i, "TypeName": t, "DivisionID": pick(ctx["division_ids"]), "DepartmentID": pick(ctx["dept_ids"])}
        for i, t in enumerate(["Candidate","Contact","Employee","Contractor","Consultant"], 1)
    ])

    # AssociateTypeRelation
    atr_rows = []
    for i in range(1, 401):
        atr_rows.append({
            "AssociateRelationID": i,
            "AssociateID": pick(ctx["associate_ids"]),
            "TypeID": random.randint(1, 5),
        })
    write_csv("AssociateTypeRelation", atr_rows)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 7 — GDPR CONSENT
# ══════════════════════════════════════════════════════════════════════════════

def gen_gdpr():
    console.print("\n[bold cyan]Phase 7 — GDPR Consent[/bold cyan]")
    rows = []
    for pid in ctx["person_ids"]:
        email_ok = random.choice([0, 1])
        phone_ok = random.choice([0, 1])
        text_ok  = random.choice([0, 1])
        rows.append({
            "GDPR_ConsentID": pid,
            "Person_ID":      pid,
            "Email":          email_ok,
            "Text":           text_ok,
            "Phone":          phone_ok,
            "CreatedBy":      pick(ctx["recruiter_ids"]),
            "CreatedAt":      "2021-05-25 09:00:00",
            "UpdatedBy":      pick(ctx["recruiter_ids"]),
            "UpdatedAt":      "2023-01-01 09:00:00",
        })
    write_csv("GDPR_Consent", rows)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 8 — JOBS (REQ + REQ_RATES)
# ══════════════════════════════════════════════════════════════════════════════

def gen_jobs():
    console.print("\n[bold cyan]Phase 8 — Jobs (Req + Req_Rates)[/bold cyan]")

    # Status distribution:
    # 220 Active (open, being worked), 80 Filled (placed), 60 Closed (cancelled/expired),
    # 20 On Hold, 20 Archived (Deleted=1) = 400 total
    status_plan = (
        [("Active",   1, 0)] * 220 +
        [("Filled",   2, 0)] * 80  +
        [("Closed",   3, 0)] * 60  +
        [("On Hold",  4, 0)] * 20  +
        [("Archived", 3, 1)] * 20
    )
    random.shuffle(status_plan)

    all_reqs  = []
    all_rates = []
    req_id    = 1

    for batch_start in range(0, 400, 5):
        batch_count = min(5, 400 - batch_start)
        batch_statuses = status_plan[batch_start:batch_start + batch_count]

        # Date rules per status:
        # Active:  StartDate past, ExpiryDate future (2024-2025), no EndDate
        # Filled:  StartDate past, ExpiryDate past, EndDate past (role was filled)
        # Closed:  StartDate past, ExpiryDate past, EndDate past or empty
        # On Hold: StartDate past, ExpiryDate future but paused
        # Archived: Old dates, deleted=1
        data = ask(f"""
Generate {batch_count} realistic UK job requisitions.
Each has a predefined status — dates MUST match the status:

Status rules:
- Active:   StartDate in 2023, ExpiryDate in future (2025), no EndDate — role is open now
- Filled:   StartDate in 2022, ExpiryDate in 2022-2023 (past), EndDate = date role was filled — success
- Closed:   StartDate in 2021-2022, ExpiryDate in past, EndDate in past — cancelled or expired
- On Hold:  StartDate in 2023, ExpiryDate in 2025, no EndDate — paused by client
- Archived: StartDate in 2020-2021, ExpiryDate in past, Deleted=1 — old record

Statuses for this batch (in order): {[s[0] for s in batch_statuses]}

Req_Title: specific real UK job titles matching industries like Technology, Finance, Healthcare.
Req_Description: 3-4 sentences. Match the title — a Python dev role must mention Python.
Worktype: Contract for tech/IT roles mostly, Permanent for management, mix for others.
Payrate: realistic UK day rate (e.g. £450-800/day for senior tech contractors).
BillRate: Payrate * 1.2 to 1.4 (agency margin).
Salary: realistic UK annual salary for the role (e.g. £45,000-120,000).
CurrencyCode: GBP for all UK roles.
Vacancy: 1-3 for senior roles, up to 5 for junior/volume roles.

Account IDs (client companies raising these jobs): {ctx['account_ids'][:30]}.
Associate IDs (client contacts who raised the req): {ctx['associate_ids'][:15]}.
Address IDs: {ctx['address_ids'][:20]}.
Recruiter IDs: {ctx['recruiter_ids'][:8]}.
IDs start at {req_id}.

Return JSON array of {batch_count} objects:
{{
  "req": {{
    "ReqID": {req_id},
    "Req_Title": "Senior Python Developer",
    "AssociateID": "1",
    "AccountID": 5,
    "ReqStat": "Active",
    "Req_RateID": {req_id},
    "Compensation_package": "£600/day outside IR35, 6-month initial contract, remote-friendly",
    "StatusID": 1,
    "StatusText": "Active",
    "StatusDate": "2023-09-01",
    "CurrencyCode": "GBP",
    "WorktypeID": 2,
    "Worktype": "Contract",
    "Vacancy": 1,
    "WorkingHours": 40,
    "Address_ID": 3,
    "ReqSource": 2,
    "StartDate": "2023-09-01 00:00:00",
    "ExpiryDate": "2025-03-01 00:00:00",
    "EndDate": "",
    "Req_Description": "We require a Senior Python Developer with strong experience in FastAPI and AWS...",
    "PONumber": "",
    "Deleted": 0,
    "CreatedBy": 2,
    "UpdatedBy": 2,
    "CreatedAt": "2023-08-20 09:00:00",
    "UpdatedAt": "2023-08-20 09:00:00"
  }},
  "rate": {{
    "Req_RateID": {req_id},
    "Req_ID": {req_id},
    "Payrate": 600.0,
    "BillRate": 750.0,
    "Salary": 0,
    "Notes": "",
    "UpdatedAt": "2023-08-20 09:00:00",
    "CreatedBy": 2,
    "UpdatedBy": 2
  }}
}}
""", max_tokens=6000)

        for idx, item in enumerate(data):
            req  = item.get("req", item)
            rate = item.get("rate", {})
            stat_txt, stat_id, deleted = batch_statuses[idx] if idx < len(batch_statuses) else ("Active", 1, 0)

            req["ReqID"]      = req_id
            req["Req_RateID"] = req_id
            req["ReqStat"]    = stat_txt
            req["StatusID"]   = stat_id
            req["StatusText"] = stat_txt
            req["Deleted"]    = deleted

            if req.get("AccountID") not in ctx["account_ids"]:
                req["AccountID"] = pick(ctx["account_ids"])
            if str(req.get("AssociateID","")) not in ctx["associate_ids"]:
                req["AssociateID"] = pick(ctx["associate_ids"])

            # Job location = the client company's office address (where the role is based)
            req["Address_ID"] = ctx["account_address_map"].get(
                req["AccountID"], pick(ctx["address_ids"])
            )

            all_reqs.append(req)

            rate["Req_RateID"] = req_id
            rate["Req_ID"]     = req_id
            if not rate.get("Payrate"):
                rate = {"Req_RateID": req_id, "Req_ID": req_id, "Payrate": 500.0,
                        "BillRate": 625.0, "Salary": 0, "Notes": "",
                        "UpdatedAt": "2023-01-01 09:00:00", "CreatedBy": 1, "UpdatedBy": 1}
            all_rates.append(rate)
            req_id += 1
        time.sleep(0.3)

    write_csv("Req", all_reqs)
    write_csv("Req_Rates", all_rates)
    ctx["req_ids"]        = [r["ReqID"] for r in all_reqs]
    ctx["active_req_ids"] = [r["ReqID"] for r in all_reqs if r.get("ReqStat") == "Active"]
    ctx["req_titles"]     = [r.get("Req_Title", "") for r in all_reqs]
    ctx["req_title_list"] = {r["ReqID"]: r.get("Req_Title","") for r in all_reqs}


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 9 — PLACEMENTS (REQ_HIRED)
# ══════════════════════════════════════════════════════════════════════════════

def gen_placements():
    console.print("\n[bold cyan]Phase 9 — Placements (Req_Hired)[/bold cyan]")
    sources = ["LinkedIn","Referral","Job Board","Direct","Agency"]

    # Placement scenario definitions — every record must make logical sense
    # (pipeline_stage, hired_status, worktype, start, end, fee_range, notes)
    scenarios = [
        # Active contract placements — started, still running
        ("Placed",    1, "Contract",  "2024-01-06", "2024-12-31", (5000,15000), 80),
        ("Placed",    1, "Contract",  "2023-09-04", "2024-09-03", (5000,12000), 60),
        # Completed contract placements — both dates in past, end > start
        ("Placed",    1, "Contract",  "2022-06-01", "2023-05-31", (5000,10000), 40),
        ("Placed",    1, "Contract",  "2021-03-01", "2022-02-28", (4000, 8000), 20),
        # Permanent placements — no end date
        ("Placed",    1, "Permanent", "2023-04-03", "",            (8000,18000), 30),
        ("Placed",    1, "Permanent", "2022-09-05", "",            (6000,15000), 20),
        # Active pipeline — various stages, not placed yet
        ("Applied",   0, "Contract",  "", "", (0,0), 15),
        ("Screening", 0, "Contract",  "", "", (0,0), 15),
        ("Interview", 0, "Permanent", "", "", (0,0), 10),
        ("Offer",     0, "Permanent", "", "", (0,0),  5),
        ("Rejected",  0, "Contract",  "", "", (0,0), 10),
        ("Rejected",  0, "Permanent", "", "", (0,0),  5),
    ]

    rows = []
    i = 1
    assoc_pool = ctx.get("active_assoc_ids", ctx["associate_ids"])

    for (stage, hired, worktype, start, end, fee_range, count) in scenarios:
        for _ in range(count):
            fee = random.randint(*fee_range) if hired and fee_range[1] > 0 else 0

            # Permanent placements typically have no day rate — use salary
            is_contract = worktype in ("Contract", "Temporary", "Freelance")

            rows.append({
                "Req_HiredID":       i,
                "Account_ID":        pick(ctx["account_ids"]),
                "Associate_ID":      pick(assoc_pool),
                "Req_ID":            pick(ctx.get("active_req_ids", ctx["req_ids"])),
                "Worktype":          worktype,
                "StartDate":         start,
                "EndDate":           end,
                "Burden":            round(random.uniform(1.1, 1.5), 2) if is_contract else "",
                "Invoiced_PersonID": pick(ctx["person_ids"]) if hired and is_contract else "",
                "Pipeline_Stage":    stage,
                "RateID":            pick(ctx["req_ids"]),
                "CurrencyCode":      "GBP",
                "CurrencyID":        1,
                "Source":            random.choice(sources),
                "FeeValue":          fee,
                "Owner_ID":          pick(ctx["recruiter_ids"]),
                "Second_OwnerID":    maybe(pick(ctx["recruiter_ids"]), pct_null=0.6),
                "Reason_ID":         random.randint(1,5) if stage == "Rejected" else "",
                "Hired_Status":      hired,
                "Deleted":           0,
                "CreatedBy":         pick(ctx["recruiter_ids"]),
                "UpdatedBy":         pick(ctx["recruiter_ids"]),
                "CreatedAt":         start if start else "2024-01-01 09:00:00",
            })
            i += 1

    write_csv("Req_Hired", rows)
    ctx["hired_ids"] = [r["Req_HiredID"] for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 10 — EMPLOYEE PROFILES
# ══════════════════════════════════════════════════════════════════════════════

def gen_employee_data():
    console.print("\n[bold cyan]Phase 10 — Employee profiles[/bold cyan]")

    emp_person_ids = ctx["person_ids"][:150]
    emp_rows = []

    for i, pid in enumerate(emp_person_ids, 1):
        emp_rows.append({
            "Emp_ProfileID":       i,
            "Emp_No":              1000 + i,
            "Person_ID":           pid,
            "Profile_Notes":       "",
            "Emp_TypeID":          random.randint(1, 4),
            "Emp_TypeDescription": random.choice(["Permanent","Contract","Temporary","Freelance"]),
            "NI_number":           f"{random.choice('ABCDEFGHJKLMNPRSTW')}{random.choice('ABCEGHJKLMNPRSTWYZ')}{random.randint(100000,999999)}{random.choice('ABCD')}",
            "BankDetails":         "REDACTED",
            "SortCode":            f"{random.randint(10,99)}-{random.randint(10,99)}-{random.randint(10,99)}",
            "CreatedBy":           pick(ctx["recruiter_ids"]),
            "CreatedAt":           "2021-09-01 09:00:00",
            "UpdatedAt":           "2023-04-01 09:00:00",
        })
    write_csv("Emp_Profile", emp_rows)
    ctx["emp_ids"]  = [r["Emp_ProfileID"] for r in emp_rows]
    ctx["emp_nos"]  = {r["Emp_ProfileID"]: r["Emp_No"] for r in emp_rows}   # id → emp number

    # Enrich Profile_Notes with AI
    sample_persons = ctx.get("persons", [])[:10]
    person_context = [{"pid": p["Person_ID"], "first": p["First_Name"], "last": p["Last_Name"]} for p in sample_persons]
    notes_pool = ask(f"""
Generate 20 realistic recruiter notes about candidates in a UK recruitment database.
Include: skills summary, availability, salary expectations, attitude in interview, strengths.
Each 2-3 sentences. Sound like a recruiter typed it quickly.
Return JSON array of 20 strings.
""", max_tokens=2000)
    for row in emp_rows:
        row["Profile_Notes"] = pick(notes_pool) if isinstance(notes_pool, list) else ""
    write_csv("Emp_Profile", emp_rows)

    # EmpHist
    hist_rows = []
    uk_companies = ["BT Group","Lloyds Banking Group","Tesco","HSBC","Vodafone",
                    "Barclays","Unilever","GlaxoSmithKline","BP","Rolls-Royce",
                    "National Grid","Diageo","Rio Tinto","Compass Group","Astrazeneca"]
    for i in range(1, 351):
        hist_rows.append({
            "Hist_ID":     i,
            "Emp_ID":      pick(ctx["emp_ids"]),
            "PlaceofWork": random.choice(uk_companies),
            "Started_At":  "2015-03-01 00:00:00",
            "Ended_At":    maybe("2020-08-31 00:00:00"),
            "Title":       "Senior Analyst",
            "CreatedBy":   pick(ctx["recruiter_ids"]),
            "UpdatedBy":   pick(ctx["recruiter_ids"]),
            "Deleted":     0,
        })
    write_csv("EmpHist", hist_rows)

    # EmpEdu
    institutions = ["University of Manchester","King's College London","University of Birmingham",
                    "Leeds Beckett University","Coventry University","Oxford Brookes University",
                    "University of Edinburgh","Cardiff University","University of Bristol",
                    "Newcastle University"]
    edu_rows = []
    for i in range(1, 251):
        edu_rows.append({
            "Edu_ID":         i,
            "Emp_ID":         pick(ctx["emp_ids"]),
            "Institution":    random.choice(institutions),
            "StartDate":      "2008-09-01",
            "EndDate":        "2012-06-30",
            "Grade":          random.choice(["First","2:1","2:2","Pass","Merit","Distinction"]),
            "AwardTitle":     random.choice(["BSc Computer Science","BA Business","MSc Data Science",
                                             "LLB Law","BEng Engineering","MBA","BA Marketing"]),
            "EducationLevel": random.choice(["Undergraduate","Postgraduate","HND","A-Level"]),
            "IsHighestLevel": random.choice([1, 0]),
            "CreatedAt":      "2021-09-01 09:00:00",
            "UpdatedAt":      "2021-09-01 09:00:00",
        })
    write_csv("EmpEdu", edu_rows)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 11 — DOCUMENTS
# ══════════════════════════════════════════════════════════════════════════════

def gen_documents():
    console.print("\n[bold cyan]Phase 11 — Documents[/bold cyan]")

    cv_rows = []
    for i in range(1, 301):
        assoc_id = pick(ctx["associate_ids"])
        cv_rows.append({
            "Doc_ID":      i,
            "CV_ID":       i,
            "Desc":        f"CV — uploaded by candidate",
            "Path":        f"/cvs/cv_{i}.pdf",
            "CV_AssocID":  assoc_id,
            "CreatedAt":   "2022-01-10 09:00:00",
            "Uploaded_Id": pick(ctx["recruiter_ids"]),
            "Updated_Id":  pick(ctx["recruiter_ids"]),
            "UpdatedAt":   "2022-01-10 09:00:00",
            "AgencyCV":    random.choice([0, 0, 0, 1]),
            "Deleted":     random.choice([0, 0, 0, 0, 1]),
        })
    write_csv("CV_Docs", cv_rows)
    ctx["cv_doc_ids"] = [r["Doc_ID"] for r in cv_rows]

    doc_descriptions = [
        "Right to work documentation",
        "Employment contract — signed",
        "DBS check certificate",
        "Professional qualification certificate",
        "Identity document (passport copy)",
        "Reference letter from previous employer",
        "Non-disclosure agreement",
        "Offer letter — accepted",
    ]
    doc_rows = []
    for i in range(1, 151):
        doc_id = 300 + i
        doc_rows.append({
            "Doc_ID":       doc_id,
            "Desc":         random.choice(doc_descriptions),
            "Path":         f"/docs/doc_{doc_id}.pdf",
            "Doc_AssocID":  pick(ctx["associate_ids"]),
            "Typeid":       random.randint(1, 5),
            "CreatedAt":    "2022-03-15 09:00:00",
            "Uploaded_Id":  pick(ctx["recruiter_ids"]),
            "Updated_Id":   pick(ctx["recruiter_ids"]),
            "UpdatedAt":    "2022-03-15 09:00:00",
            "Personal_Doc": random.choice([0, 1]),
            "Deleted":      random.choice([0, 0, 0, 1]),
            "Private":      random.choice([0, 0, 1]),
            "ObjectType":   random.choice(["Associate","Person","Req"]),
            "Filesize":     f"{random.randint(50, 5000)}KB",
        })
    write_csv("Documents", doc_rows)
    ctx["doc_ids"] = [r["Doc_ID"] for r in doc_rows]

    # Junction tables
    write_csv("RecruiterDocuments", [
        {"RecDocument_ID": i, "Recruiter_ID": pick(ctx["recruiter_ids"]),
         "Document_ID": pick(ctx["doc_ids"]), "Desc": "Internal recruiter document",
         "Deleted": 0, "Private": random.choice([0, 1])}
        for i in range(1, 51)
    ])
    write_csv("Req_Documents", [
        {"ReqDocument_ID": i, "Req_ID": pick(ctx["req_ids"]),
         "Document_ID": pick(ctx["doc_ids"]), "Desc": "Job-related document",
         "Deleted": 0, "Private": 0}
        for i in range(1, 101)
    ])
    write_csv("Emp_Documents", [
        {"EmpDocument_ID": i, "Emp_ID": pick(ctx["emp_ids"]),
         "Document_ID": pick(ctx["doc_ids"]),
         "Person_ID": pick(ctx["person_ids"]),
         "Desc": "Employee document", "Deleted": 0, "Private": random.choice([0, 1])}
        for i in range(1, 101)
    ])


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 12 — NOTES (AI-generated, contextual)
# ══════════════════════════════════════════════════════════════════════════════

def gen_notes():
    console.print("\n[bold cyan]Phase 12 — Notes[/bold cyan]")

    pools = {}
    note_context = {
        "Person": "a candidate or contractor registered with Bridge Talent Ltd",
        "Associate": "a client contact (e.g. hiring manager, HR director) at a company Bridge Talent works with",
        "Account": "a client company that Bridge Talent recruits for",
        "Req": "an open job requisition that Bridge Talent is trying to fill",
    }
    for obj_type in ["Person", "Associate", "Account", "Req"]:
        result = ask(f"""
Generate 25 realistic recruiter CRM notes about {note_context[obj_type]}.
These are quick notes typed by a recruiter at Bridge Talent Ltd after calls, emails, or meetings.

For Person (candidate): availability updates, salary expectations, interview feedback received,
skill gaps noted, left voicemail, sent CV to client, counter-offer situation, notice period update.
For Associate (client contact): call notes, meeting outcomes, budget confirmed, headcount approved,
chased for feedback, out of office, referred us to another manager, relationship building.
For Account: new business won, contract renewal, payment issue, new project starting,
preferred supplier status confirmed, rate card agreed, PSL review coming up.
For Req: shortlist sent, client feedback received, role put on hold, revised brief,
salary increased, competitor also briefed, 3 CVs with client, interview slots agreed.

Each note 1-3 sentences. Include specifics — dates, names, numbers where natural.
Sound like a recruiter typed it quickly after a call. Use UK English.
Examples for Person: "Called re availability — starting to look from 1st April. Wants £600/day min outside IR35."
Examples for Account: "Spoke with Fiona re Q3 headcount. 3 Python roles confirmed, briefs to follow by EOW."

Return JSON array of 25 strings.
""", max_tokens=3000)
        pools[obj_type] = result if isinstance(result, list) else []
        time.sleep(0.2)

    rows = []
    entity_map = {
        "Person":    ctx["person_ids"],
        "Associate": ctx["associate_ids"],
        "Account":   ctx["account_ids"],
        "Req":       ctx["req_ids"],
    }
    for i in range(1, 401):
        obj_type = random.choice(list(entity_map.keys()))
        rows.append({
            "Note_ID":    i,
            "ObjectId":   pick(entity_map[obj_type]),  # always a valid ID for that type
            "ObjectType": obj_type,
            "Notetext":   pick(pools.get(obj_type, ["Follow-up required."])),
            "CreatedAt":  "2022-08-15 10:30:00",
            "CreatedBy":  pick(ctx["recruiter_ids"]),
            "UpdatedAt":  "2022-08-15 10:30:00",
            "UpdatedBy":  pick(ctx["recruiter_ids"]),
        })
    write_csv("Notes", rows)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 13 — ACTIVITIES (Interview Feedback, Schedule, Leads)
# ══════════════════════════════════════════════════════════════════════════════

def gen_activities():
    console.print("\n[bold cyan]Phase 13 — Activities[/bold cyan]")

    # Interview Feedback — AI generated
    feedback_pool = ask("""
Generate 30 realistic UK interview feedback notes.
Mix of: strong positive, positive with reservations, neutral, negative.
Each 2-4 sentences. Sound like a hiring manager wrote it.
Include specific observations about communication, technical ability, culture fit.
Return JSON array of 30 strings.
""", max_tokens=3000)
    time.sleep(0.3)

    feedback_rows = []
    for i in range(1, 201):
        note = pick(feedback_pool) if isinstance(feedback_pool, list) else "No feedback recorded."
        positive = any(w in note.lower() for w in ["strong","excellent","impressive","highly recommend","great fit"])
        feedback_rows.append({
            "Interview_FeedbackID": i,
            "Interviewer_ID":       pick(ctx["associate_ids"]),
            "Interviewee_ID":       pick(ctx["person_ids"]),
            "Interview_Date":       "2022-09-14 14:00:00",
            "Second_InterviewerID": maybe(pick(ctx["associate_ids"])),
            "Other_InterviewerID":  maybe(pick(ctx["associate_ids"])),
            "Notes":                note,
            "Callback":             1 if positive else 0,
            "CreatedAt":            "2022-09-14 16:00:00",
            "UpdatedAt":            "2022-09-14 16:00:00",
        })
    write_csv("Interview_Feedback", feedback_rows)

    # Schedule
    schedule_rows = []
    schedule_types = ["Interview","Phone Screen","Client Meeting","Assessment Centre","Induction"]
    for i in range(1, 201):
        schedule_rows.append({
            "Schedule_ID":       i,
            "AssignSchedule_ID": maybe(i - 1 if i > 1 else ""),
            "ScheduleType":      random.choice(schedule_types),
            "Account_ID":        pick(ctx["account_ids"]),
            "Req_ID":            pick(ctx["req_ids"]),
            "Person_ID":         pick(ctx["person_ids"]),
            "Person_Type":       random.choice(["Candidate","Contact"]),
            "StartDate":         "2022-10-05 10:00:00",
            "EndDate":           "2022-10-05 11:00:00",
            "Notes":             maybe("Teams link sent. Candidate confirmed attendance."),
            "CreatedAt":         "2022-10-01 09:00:00",
            "CreatedBy":         pick(ctx["recruiter_ids"]),
            "UpdatedAt":         "2022-10-01 09:00:00",
            "UpdatedBy":         pick(ctx["recruiter_ids"]),
        })
    write_csv("Schedule", schedule_rows)

    # Leads — AI generated
    lead_data = ask("""
Generate 50 realistic business development leads for Bridge Talent Ltd, a UK recruitment agency.
These are prospective client companies that a recruiter is trying to win as new clients.

Lead_Status pipeline (must be logically consistent with Lead_Score and Note):
- New (score 1-2): just identified, no contact yet — Note should mention how they were found
- Contacted (score 2-3): initial outreach made — Note should mention call/LinkedIn message sent
- Qualified (score 3-4): confirmed they hire contractors/staff — Note should mention conversation detail
- Proposal (score 4-5): sent a commercial proposal or rate card — Note should mention what was sent
- Converted (score 5): became a client — Note should say when and who signed
- Lost (score 1-2): went with a competitor or froze headcount — Note should say why lost

Lead_Source:
- LinkedIn: "Found on LinkedIn — Director of Engineering at [Company]. Connection request accepted."
- Referral: "Referred by [existing client name]. Introduction made by [recruiter name]."
- Cold Call: "Cold called switchboard — got through to HR. Interest shown."
- Event: "Met at [specific UK tech/finance event name]. Exchanged cards."
- Website: "Inbound enquiry via website contact form."

Name: realistic UK company name matching the industry.
Lead_Name: the specific person spoken to — their name must match their email.
Email: firstname.lastname@companydomain.co.uk — MUST derive from Lead_Name.
Phone: UK mobile +44 7XXX XXXXXX or direct line +44 20/161/121 XXXX XXXX.
Address: real UK business district street addresses.
Lead_Score: 1-5 — MUST align with Lead_Status (Converted=5, New=1-2, Lost=1-2).

Return JSON array of 50 objects:
{
  "Lead_ID": 1,
  "Name": "Vertex Capital Partners",
  "Lead_Status": "Qualified",
  "Lead_Source": "LinkedIn",
  "Lead_Name": "Thomas Abernethy",
  "Associate_ID": "",
  "Account_ID": "",
  "Req_ID": "",
  "Email": "thomas.abernethy@vertexcapital.co.uk",
  "Phone": "+44 7891 234567",
  "Note": "Spoke to Thomas on 8 Feb — they are expanding their quant dev team and need 3 Python/C++ contractors. Sending rate card this week.",
  "Consent_GDPR": 1,
  "URL": "https://www.vertexcapital.co.uk",
  "Address_Line1": "30 St Mary Axe",
  "Address_Line2": "Floor 14",
  "City": "London",
  "Country": "United Kingdom",
  "Document_ID": "",
  "Sourced_Date": "2023-02-08 09:00:00",
  "Assigned_To": 1,
  "CreatedBy": 1,
  "UpdatedBy": 1,
  "Lead_Score": 4
}
""", max_tokens=6000)
    time.sleep(0.3)

    lead_rows = []
    for i, row in enumerate(lead_data, 1):
        row["Lead_ID"]     = i
        row["Associate_ID"] = maybe(pick(ctx["associate_ids"]))
        row["Account_ID"]   = maybe(pick(ctx["account_ids"]))
        row["Req_ID"]       = maybe(pick(ctx["req_ids"]))
        row["Document_ID"]  = maybe(pick(ctx["doc_ids"]))
        row["Assigned_To"]  = pick(ctx["recruiter_ids"])
        row["CreatedBy"]    = pick(ctx["recruiter_ids"])
        row["UpdatedBy"]    = pick(ctx["recruiter_ids"])
        lead_rows.append(row)

    write_csv("Leads", lead_rows)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 14 — FINANCE
# ══════════════════════════════════════════════════════════════════════════════

def gen_finance():
    console.print("\n[bold cyan]Phase 14 — Finance[/bold cyan]")

    # Account Rates
    write_csv("AccountRate", [
        {"Rate_ID": i, "Account_ID": pick(ctx["account_ids"]),
         "Chargerate": round(random.uniform(20.0, 150.0), 2),
         "Payrate": round(random.uniform(12.0, 100.0), 2),
         "CreatedAt": "2021-01-01 09:00:00", "UpdatedAt": "2021-01-01 09:00:00",
         "CreatedBy": pick(ctx["recruiter_ids"]), "UpdatedBy": pick(ctx["recruiter_ids"])}
        for i in range(1, 151)
    ])

    # PO Numbers
    po_numbers = [f"PO{str(i).zfill(5)}" for i in range(1, 61)]
    po_rows = []
    for i, po in enumerate(po_numbers, 1):
        po_rows.append({
            "PONo":          po,
            "VendorID":      pick(ctx["account_ids"]),
            "ReqID":         pick(ctx["req_ids"]),
            "DepartmentID":  pick(ctx["dept_ids"]),
            "CreatedBy":     pick(ctx["recruiter_ids"]),
            "UpdatedBy":     pick(ctx["recruiter_ids"]),
            "ApprovedBy":    pick(ctx["recruiter_ids"]),
            "POStatus":      random.choice(["Open","Closed","Pending","Cancelled"]),
            "Issue_Date":    "2022-01-15",
            "DateDue":       "2022-04-15",
            "Currency":      "GBP",
            "Amount":        round(random.uniform(5000, 100000), 2),
            "TaxAmount":     round(random.uniform(500, 10000), 2),
            "Payment_Terms": random.choice(["30 days","60 days","14 days"]),
            "Desc":          f"Purchase order for recruitment services",
            "Notes":         maybe("Approved by finance director."),
            "CreatedAt":     "2022-01-10 09:00:00",
            "UpdatedAt":     "2022-01-10 09:00:00",
        })
    write_csv("PONo", po_rows)
    ctx["po_numbers"] = po_numbers

    # Invoices
    invoice_rows = []
    for i in range(1, 201):
        invoice_rows.append({
            "InvoiceID":       i,
            "Invoice_No":      f"INV{str(i).zfill(5)}",
            "PONo":            maybe(pick(po_numbers)),
            "Vendor_ID":       pick(ctx["account_ids"]),
            "DateDue":         "2023-03-31",
            "InvoiceDate":     "2023-03-01",
            "Currency":        "GBP",
            "Status":          random.choice(["Draft","Sent","Paid","Overdue","Cancelled"]),
            "Amount":          round(random.uniform(1000, 50000), 2),
            "VAT":             "20%",
            "NETAmount":       round(random.uniform(800, 40000), 2),
            "Amount_Paid":     round(random.uniform(0, 50000), 2),
            "Balance_Due":     round(random.uniform(0, 10000), 2),
            "SubTotal_Amount": round(random.uniform(800, 40000), 2),
            "Payment_Terms":   random.choice(["30 days","60 days"]),
            "Desc":            random.choice(["Permanent placement fee","Contractor timesheet — March 2023","Credit note"]),
            "Document_ID":     maybe(pick(ctx["doc_ids"])),
            "Approved_By":     maybe(pick(ctx["recruiter_ids"])),
            "CreatedBy":       pick(ctx["recruiter_ids"]),
            "UpdatedBy":       pick(ctx["recruiter_ids"]),
            "InvoiceType_ID":  random.randint(1, 3),
        })
    write_csv("Invoice", invoice_rows)
    ctx["invoice_ids"] = [r["InvoiceID"] for r in invoice_rows]

    write_csv("InvoiceEntries", [
        {"Invoice_EntryID": i,
         "Invoice_ID": pick(ctx["invoice_ids"]),
         "Quantity": random.randint(1, 40),
         "Unit_Price": round(random.uniform(15.0, 150.0), 2),
         "Amount": round(random.uniform(200, 10000), 2),
         "Desc": random.choice(["Contractor Hours","Placement Fee","Admin Fee","Expenses"]),
         "Plac_ID": maybe(pick(ctx["hired_ids"])),
         "CreatedAt": "2023-03-01 09:00:00",
         "UpdatedAt": "2023-03-01 09:00:00",
         "CreatedBy": pick(ctx["recruiter_ids"])}
        for i in range(1, 501)
    ])


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 15 — TIMESHEETS
# ══════════════════════════════════════════════════════════════════════════════

def gen_timesheets():
    console.print("\n[bold cyan]Phase 15 — Timesheets[/bold cyan]")

    ts_rows = []
    for i in range(1, 201):
        ts_rows.append({
            "ID":               i,
            "Timesheet_TypeID": random.randint(1, 5),
            "PONo":             maybe(pick(ctx["po_numbers"])),
            "Payrate":          round(random.uniform(12.0, 80.0), 2),
            "Billrate":         round(random.uniform(15.0, 100.0), 2),
            "StartDate":        "2023-01-02",
            "Enddate":          "2023-01-08",
            "Status":           random.choice(["Pending","Approved","Rejected","Submitted"]),
            "Approved_Date":    maybe("2023-01-09 09:00:00"),
            "Approved_By":      maybe(pick(ctx["recruiter_ids"])),
        })
    write_csv("TimeSheets", ts_rows)
    ctx["ts_ids"] = [r["ID"] for r in ts_rows]

    write_csv("TimesheetItems", [
        {"ItemID":           i,
         "Timesheet_ID":     pick(ctx["ts_ids"]),
         "Timesheet_TypeID": random.randint(1, 5),
         "StartTime":        f"{random.randint(8,10):02d}:00:00",
         "EndTime":          f"{random.randint(16,18):02d}:00:00",
         "Person_ID":        pick(ctx["person_ids"]),
         "TotalHours":       round(random.uniform(6.0, 10.0), 1),
         "Req_ID":           pick(ctx["req_ids"]),
         "CreatedBy":        pick(ctx["recruiter_ids"]),
         "UpdatedBy":        pick(ctx["recruiter_ids"]),
         "CreatedAt":        "2023-01-08 17:00:00",
         "UpdatedAt":        "2023-01-08 17:00:00"}
        for i in range(1, 801)
    ])


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 16 — COMPLIANCE & REFERENCES
# ══════════════════════════════════════════════════════════════════════════════

def gen_compliance_references():
    console.print("\n[bold cyan]Phase 16 — Compliance & References[/bold cyan]")

    write_csv("BackgroundChecks", [
        {"Check_ID": i, "Person_ID": pick(ctx["person_ids"]),
         "Check_Type": random.choice(["DBS Basic","DBS Enhanced","Right to Work","Credit Check","Employment Reference"]),
         "Doc_ID": maybe(pick(ctx["doc_ids"])),
         "Notes": maybe("Check passed. Document verified by compliance team."),
         "CreatedAt": "2022-11-01 09:00:00", "UpdatedAt": "2022-11-05 09:00:00",
         "CreatedBy": pick(ctx["recruiter_ids"]), "UpdatedBy": pick(ctx["recruiter_ids"])}
        for i in range(1, 201)
    ])

    write_csv("Compliance", [
        {"Compliance_ID": i, "Notes": maybe("Compliance review completed. All documents in order."),
         "Deleted": 0, "CreatedBy": pick(ctx["recruiter_ids"])}
        for i in range(1, 101)
    ])

    write_csv("ComplianceItems", [
        {"Compliance_ItemID": i, "Comp_ID": random.randint(1, 100),
         "Comp_DocID": random.randint(1, 5), "CompType_ID": pick(ctx["comp_type_ids"]),
         "Comp_AssocID": pick(ctx["associate_ids"]),
         "CreatedAt": "2022-11-01 09:00:00", "UpdatedAt": "2022-11-01 09:00:00",
         "CreatedBy": pick(ctx["recruiter_ids"]), "Deleted": 0}
        for i in range(1, 201)
    ])

    # Referees — AI generated
    referee_data = ask("""
Generate 75 professional referees for a UK IT/professional services recruitment database.
These are former managers and colleagues of candidates registered with Bridge Talent Ltd.

Rules:
- Fullname: realistic British name (diverse — English, South Asian, European)
- Email: strictly firstname.lastname@companydomain.co.uk derived from their name and company
  Example: "Claire Hutchinson" at "Barclays" → claire.hutchinson@barclays.co.uk
- Telephone: UK mobile (+44 7XXX XXXXXX) or direct line (+44 20 XXXX XXXX)
- Company: real-sounding UK companies (banks, tech firms, NHS Trusts, consultancies)
  Examples: "Lloyds Banking Group", "NHS Digital", "Accenture UK", "BAE Systems",
  "PwC", "Deloitte", "BT Group", "Vodafone UK", "Rolls-Royce", "National Grid"
- Job_Title: seniority appropriate — Line Manager, Head of Department, HR Business Partner,
  Engineering Director, Senior Project Manager
- Notes: either blank, or a brief CRM note like "Contacted 14/03/2023 — happy to provide ref by email"

Return JSON array of 75 objects:
{
  "Referee_ID": 1,
  "Fullname": "Claire Hutchinson",
  "email": "claire.hutchinson@lloydsbankinggroup.com",
  "Telephone": "+44 7712 834561",
  "Company": "Lloyds Banking Group",
  "Job_Title": "Head of Technology Resourcing",
  "Notes": "Contacted March 2023 — prefers written reference requests by email only.",
  "CreatedAt": "2022-01-10 09:00:00"
}
""", max_tokens=6000)
    time.sleep(0.3)

    for i, row in enumerate(referee_data, 1):
        row["Referee_ID"] = i
    write_csv("Referees", referee_data)
    ctx["referee_ids"] = [r["Referee_ID"] for r in referee_data]

    # Reference letters — AI generated
    ref_letters = ask("""
Generate 25 realistic UK employment reference texts.
Mix of: glowing references, solid positive ones, neutral professional ones.
Each 3-5 sentences. Sound authentic — like an HR director or line manager wrote it.
Include specific mentions of skills, work ethic, achievements.
Return JSON array of 25 strings.
""", max_tokens=3000)
    time.sleep(0.3)

    emp_ref_rows = []
    emp_id_list  = list(ctx["emp_nos"].keys())   # valid Emp_ProfileIDs
    for i in range(1, 201):
        status = random.choice(["Requested","Received","Satisfactory","Unsatisfactory"])
        emp_id = pick(emp_id_list)
        emp_ref_rows.append({
            "EmpRef_ID":    i,
            "Ref_ID":       pick(ctx["referee_ids"]),
            "EmpNo":        str(ctx["emp_nos"][emp_id]),   # real Emp_No matching Emp_Profile
            "Status":       status,
            "Relationship": random.choice(["Line Manager","Colleague","HR Contact","Director"]),
            "Reference":    pick(ref_letters) if status in ("Received","Satisfactory") and isinstance(ref_letters, list) else "",
            "Notes":        maybe("Reference received by email."),
            "CreatedAt":    "2023-01-15 09:00:00",
            "UpdatedAt":    "2023-01-20 09:00:00",
        })
    write_csv("EmpRef", emp_ref_rows)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 17 — SKILLS, HOTLISTS, TAGS
# ══════════════════════════════════════════════════════════════════════════════

def gen_skills_tags_hotlists():
    console.print("\n[bold cyan]Phase 17 — Skills, Hotlists, Tags[/bold cyan]")

    # Skills per category so we can assign contextually
    tech_skills    = [1, 3, 4, 5, 6, 12, 13, 19]   # Python, Java, C#, Azure, AWS, React, Node, DevOps
    data_skills    = [2, 7, 14, 18]                   # SQL, Power BI, Data Analysis, Tableau
    pm_skills      = [8, 15, 20]                      # Agile, PM, Communication
    sales_skills   = [9, 10, 16, 20]                  # Salesforce, Recruitment, BizDev, Communication
    finance_skills = [11, 17, 2]                      # Financial Modelling, Excel, SQL

    skill_pool_by_dept = {
        1: tech_skills + data_skills,    # Technology dept
        2: finance_skills + data_skills, # Finance dept
        3: sales_skills + pm_skills,     # HR dept
        4: sales_skills,                 # Sales dept
        5: pm_skills + tech_skills,      # Operations dept
    }

    obj_skills = []
    skill_id = 1

    # Ask Claude to map job titles to the correct skill IDs so skills match real roles
    req_titles_sample = list(set(ctx.get("req_titles", [])))[:40]
    title_skill_map: dict[str, list[int]] = {}

    if req_titles_sample:
        mapping = ask(f"""
You are building a realistic UK IT/professional services recruitment database.
This database tracks contractors placed at client companies.

Map each job title below to the most appropriate skill IDs from this list:
1=Python, 2=SQL, 3=Java, 4=C#, 5=Azure, 6=AWS, 7=Power BI, 8=Agile/Scrum,
9=Salesforce, 10=Recruitment, 11=Financial Modelling, 12=React, 13=Node.js,
14=Data Analysis, 15=Project Management, 16=Business Development,
17=Excel/VBA, 18=Tableau, 19=DevOps/CI-CD, 20=Communication

Strict rules — a skill must genuinely match the job title:
- Python/Data Engineer → must include 1, 2, plus cloud (5 or 6)
- Java/.NET Developer → 3 or 4, plus 8, 19
- DevOps Engineer → 19, 5 or 6, 8
- Data Analyst / BI → 2, 14, and 7 or 18
- Finance Manager → 11, 17, 2
- Project Manager → 8, 15, 20
- Sales / BizDev → 16, 20, and optionally 9
- Recruitment Consultant → 10, 20, 16
- Full Stack Developer → 12, 13, 2, 19
- Cloud Architect → 5, 6, 19, 8
Assign 3-5 skills per title.

Job titles: {req_titles_sample}

Return ONLY a JSON object — keys are job titles, values are arrays of integer skill IDs:
{{"Senior Python Developer": [1, 2, 6, 8, 19], "Finance Manager": [11, 17, 2], ...}}
""", max_tokens=3000)
        if isinstance(mapping, dict):
            title_skill_map = mapping
        time.sleep(0.3)

    # Skills for associates — matched to their associated job title where possible
    req_title_list = ctx.get("req_title_list", {})  # req_id → title
    assoc_sample = ctx["associate_ids"][:400]
    for aid in assoc_sample:
        dept  = random.randint(1, 5)
        pool  = skill_pool_by_dept.get(dept, ctx["skill_ids"])
        n_skills = random.randint(2, 4)
        chosen = random.sample(pool, min(n_skills, len(pool)))
        for sid in chosen:
            obj_skills.append({
                "ID": skill_id, "ObType": "Associate", "SkillID": sid, "SkillName": "",
                "CreatedBy": pick(ctx["recruiter_ids"]), "UpdatedBy": pick(ctx["recruiter_ids"]),
                "CreatedAt": "2022-06-01 09:00:00", "UpdatedAt": "2022-06-01 09:00:00", "Deleted": 0,
            })
            skill_id += 1

    # Skills for reqs — use Claude's title→skill map so required skills match the job
    req_sample = ctx["req_ids"][:300]
    for rid in req_sample:
        title = req_title_list.get(rid, "")
        pool  = title_skill_map.get(title) if title and title in title_skill_map else None
        if not pool:
            pool = random.choice(list(skill_pool_by_dept.values()))
        n_skills = random.randint(2, 5)
        chosen = random.sample(pool, min(n_skills, len(pool)))
        for sid in chosen:
            obj_skills.append({
                "ID": skill_id, "ObType": "Req", "SkillID": sid, "SkillName": "",
                "CreatedBy": pick(ctx["recruiter_ids"]), "UpdatedBy": pick(ctx["recruiter_ids"]),
                "CreatedAt": "2022-06-01 09:00:00", "UpdatedAt": "2022-06-01 09:00:00", "Deleted": 0,
            })
            skill_id += 1

    write_csv("ObjectSKills", obj_skills)

    hotlists = [
        {"Hotlist_ID": 1, "Name": "Tech Contractors — Available Now", "Desc": "Active contractors available within 2 weeks", "Hotlist_Type": "Candidate", "CreatedBy": 1, "UpdatedBy": 1},
        {"Hotlist_ID": 2, "Name": "Finance Permanent — Senior",       "Desc": "Senior finance candidates for permanent roles",  "Hotlist_Type": "Candidate", "CreatedBy": 2, "UpdatedBy": 2},
        {"Hotlist_ID": 3, "Name": "VIP Clients — Q1 2023",           "Desc": "Priority client accounts this quarter",          "Hotlist_Type": "Client",    "CreatedBy": 1, "UpdatedBy": 1},
        {"Hotlist_ID": 4, "Name": "Graduates 2023",                   "Desc": "Graduate intake candidates",                    "Hotlist_Type": "Candidate", "CreatedBy": 3, "UpdatedBy": 3},
        {"Hotlist_ID": 5, "Name": "Healthcare Contractors",           "Desc": "Registered healthcare workers available",       "Hotlist_Type": "Candidate", "CreatedBy": 2, "UpdatedBy": 2},
        {"Hotlist_ID": 6, "Name": "Engineering — Relocators",        "Desc": "Candidates willing to relocate for eng roles",   "Hotlist_Type": "Candidate", "CreatedBy": 1, "UpdatedBy": 1},
        {"Hotlist_ID": 7, "Name": "Legal Professionals",              "Desc": "Qualified solicitors and paralegals",           "Hotlist_Type": "Candidate", "CreatedBy": 4, "UpdatedBy": 4},
        {"Hotlist_ID": 8, "Name": "Prospect Clients — Midlands",     "Desc": "Warm leads from Midlands region",               "Hotlist_Type": "Client",    "CreatedBy": 2, "UpdatedBy": 2},
        {"Hotlist_ID": 9, "Name": "Data Science Specialists",        "Desc": "ML/AI and data science candidates",             "Hotlist_Type": "Candidate", "CreatedBy": 1, "UpdatedBy": 3},
        {"Hotlist_ID":10, "Name": "Executive Search Pipeline",        "Desc": "C-suite and director level candidates",         "Hotlist_Type": "Candidate", "CreatedBy": 4, "UpdatedBy": 4},
    ]
    write_csv("Hotlists", hotlists)
    ctx["hotlist_ids"] = [h["Hotlist_ID"] for h in hotlists]

    write_csv("ObjectHotlist", [
        {"ObjHotlistID": i, "Hotlist_ID": pick(ctx["hotlist_ids"]),
         "Person_ID": pick(ctx["person_ids"]),
         "CreatedBy": pick(ctx["recruiter_ids"]), "UpdatedBy": pick(ctx["recruiter_ids"]), "Deleted": 0}
        for i in range(1, 201)
    ])

    # Tags split correctly by entity type using updated category-aligned IDs:
    # Associates = contacts at client companies → relationship + compliance tags
    # Accounts   = client companies → client & account tags
    # Persons    = candidates → candidate status + job preference tags
    assoc_tag_ids   = [6, 11, 12]          # Do Not Contact, Referred by Client, Ex-Placed Candidate
    account_tag_ids = [4, 5]              # VIP Client, Key Account
    person_tag_ids  = [1, 2, 3, 7, 8, 9, 10]  # Hot Candidate, Graduate, Senior, Visa, Contract/Perm Only, Relocate

    tag_entity_rows = []
    te_id = 1

    # Tag associates (client contacts) with relationship tags
    for aid in random.sample(ctx["associate_ids"], min(150, len(ctx["associate_ids"]))):
        tag_entity_rows.append({
            "TagEntity_ID": te_id, "TagID": pick(assoc_tag_ids),
            "EntityID": aid, "EntityType": "Associate",
            "CreatedAt": "2022-07-01 09:00:00", "CreatedBy": pick(ctx["recruiter_ids"]),
        })
        te_id += 1

    # Tag accounts with account-level tags
    for acct_id in random.sample(ctx["account_ids"], min(80, len(ctx["account_ids"]))):
        tag_entity_rows.append({
            "TagEntity_ID": te_id, "TagID": pick(account_tag_ids),
            "EntityID": acct_id, "EntityType": "Account",
            "CreatedAt": "2022-07-01 09:00:00", "CreatedBy": pick(ctx["recruiter_ids"]),
        })
        te_id += 1

    # Tag persons (candidates) with candidate tags
    for pid in random.sample(ctx["person_ids"], min(200, len(ctx["person_ids"]))):
        tag_entity_rows.append({
            "TagEntity_ID": te_id, "TagID": pick(person_tag_ids),
            "EntityID": pid, "EntityType": "Person",
            "CreatedAt": "2022-07-01 09:00:00", "CreatedBy": pick(ctx["recruiter_ids"]),
        })
        te_id += 1

    write_csv("TagEntity", tag_entity_rows)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 18 — SYSTEM TABLES
# ══════════════════════════════════════════════════════════════════════════════

def gen_system():
    console.print("\n[bold cyan]Phase 18 — System tables[/bold cyan]")

    write_csv("APIsession", [
        {"SessionID":        i,
         "User_ID":          pick(ctx["recruiter_ids"]),
         "UserType":         "Recruiter",
         "API_Key":          f"sk-{''.join(random.choices('abcdef0123456789', k=40))}",
         "ip_Address":       f"{random.randint(10,200)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
         "User_agent":       random.choice(["Mozilla/5.0 Chrome/120","Mozilla/5.0 Firefox/121","python-requests/2.31"]),
         "CreatedAt":        "2023-01-10 08:45:00",
         "Expires_At":       "2023-01-10 20:45:00",
         "Last_activity_At": "2023-01-10 15:20:00",
         "Status":           random.choice(["Active","Expired","Terminated"]),
         "refresh_Token":    maybe(f"rt-{''.join(random.choices('abcdef0123456789', k=40))}"),
         "scopes":           random.choice(["read","read,write","admin"]),
         "request_count":    random.randint(1, 5000),
         "terminated_by":    maybe(pick(ctx["recruiter_ids"]))}
        for i in range(1, 201)
    ])

    actions = ["CREATE","UPDATE","DELETE","LOGIN","EXPORT","VIEW"]
    entities = ["Account","Person","Req","Invoice","Timesheet","Associate"]
    write_csv("Log", [
        {"LogID":       i,
         "Timestamp":   "2023-03-15 11:22:00",
         "Level":       random.choice([1, 2, 3, 4]),
         "User_ID":     pick(ctx["recruiter_ids"]),
         "Action":      random.choice(actions),
         "Entity_Type": random.choice(entities),
         "Entity_ID":   random.randint(1, 500),
         "message":     "Record updated successfully.",
         "ip_Address":  f"10.0.{random.randint(0,5)}.{random.randint(1,254)}",
         "User_Agent":  "Mozilla/5.0 Chrome/120",
         "request_Id":  random.randint(100000, 999999),
         "Status_Code": random.choice(["200","201","400","500"]),
         "CreatedAt":   "2023-03-15 11:22:00"}
        for i in range(1, 1001)
    ])


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 19 — INTENTIONAL DIRTY DATA
# Real-world databases always have data quality issues.
# These simulate genuine problems the migration must handle.
# ══════════════════════════════════════════════════════════════════════════════

def inject_dirty_data():
    console.print("\n[bold cyan]Phase 19 — Injecting dirty data[/bold cyan]")

    # ── Person: missing phones, emails, DOBs ─────────────────────────────────
    persons = read_csv("Person")
    dirty_count = 0
    for i, row in enumerate(persons):
        r = random.random()
        if r < 0.08:     # 8% have no DOB (not captured)
            row["DOB"] = ""
            dirty_count += 1
        if r < 0.05:     # 5% missing department (newly added, not categorised)
            row["DeptID"] = ""
            dirty_count += 1
    # 3 records where Deleted=1 but IsArchived=0 (inconsistent soft-delete flags)
    for row in random.sample(persons, 3):
        row["Deleted"]    = 1
        row["IsArchived"] = 0
        dirty_count += 1
    # 2 records that look like duplicates (same name, slightly different DOB)
    if len(persons) >= 2:
        clone = dict(persons[0])
        clone["Person_ID"]  = 9998
        clone["DOB"]        = "1985-03-15"   # slightly different
        clone["GDPRConsent_ID"] = 9998
        persons.append(clone)
        dirty_count += 1
    write_csv("Person", persons)

    # ── Addresses: missing phones, blank emails ───────────────────────────────
    addresses = read_csv("Addresses")
    for row in random.sample(addresses, int(len(addresses) * 0.12)):   # 12% no phone
        row["Phone"] = ""
        dirty_count += 1
    for row in random.sample(addresses, int(len(addresses) * 0.18)):   # 18% no email
        row["Email"] = ""
        dirty_count += 1
    for row in random.sample(addresses, int(len(addresses) * 0.08)):   # 8% no address line 2
        row["Address_line2"] = ""
    # 5 addresses with clearly wrong postcode format (data entry errors)
    for row in random.sample(addresses, 5):
        row["ZipCode"] = random.choice(["00000","N/A","TBC","n/a",""])
        dirty_count += 1
    write_csv("Addresses", addresses)

    # ── Accounts: missing websites, blank About, inconsistent status ──────────
    accounts = read_csv("Accounts")
    for row in random.sample(accounts, int(len(accounts) * 0.10)):   # 10% no website
        row["Website"] = ""
        dirty_count += 1
    for row in random.sample(accounts, int(len(accounts) * 0.06)):   # 6% no About
        row["About"] = ""
        dirty_count += 1
    # 4 accounts: Deleted=0 but AccountStatusTypeID=3 (Closed) — inconsistent
    for row in random.sample(accounts, 4):
        row["AccountStatusTypeID"] = 3
        row["Deleted"] = 0
        dirty_count += 1
    write_csv("Accounts", accounts)

    # ── Req: some jobs missing description, some with very short notes ────────
    reqs = read_csv("Req")
    for row in random.sample(reqs, int(len(reqs) * 0.04)):   # 4% no description
        row["Req_Description"] = ""
        dirty_count += 1
    for row in random.sample(reqs, int(len(reqs) * 0.03)):   # 3% placeholder description
        row["Req_Description"] = "TBC"
        dirty_count += 1
    # 5 jobs where ExpiryDate < StartDate (data entry error)
    for row in random.sample(reqs, 5):
        row["ExpiryDate"] = "2020-01-01 00:00:00"   # before StartDate
        dirty_count += 1
    write_csv("Req", reqs)

    # ── Associates: some missing role, some with blank tags ───────────────────
    associates = read_csv("Associates")
    for row in random.sample(associates, int(len(associates) * 0.07)):
        row["Associate_Tag"] = ""
        dirty_count += 1
    for row in random.sample(associates, int(len(associates) * 0.05)):
        row["Associate_RoleID"] = ""
        dirty_count += 1
    write_csv("Associates", associates)

    # ── Notes: some very unhelpful notes ─────────────────────────────────────
    notes = read_csv("Notes")
    junk_notes = [".", "N/A", "TBC", "see email", "-", "?", "done", "called"]
    for row in random.sample(notes, int(len(notes) * 0.05)):
        row["Notetext"] = random.choice(junk_notes)
        dirty_count += 1
    write_csv("Notes", notes)

    # ── Req_Hired: few records missing start date (pipeline never converted) ──
    placements = read_csv("Req_Hired")
    for row in random.sample(placements, int(len(placements) * 0.04)):
        if row.get("Hired_Status") == "0":
            row["StartDate"] = ""
    write_csv("Req_Hired", placements)

    console.print(f"  [yellow]Injected {dirty_count} dirty data points across 7 tables[/yellow]")
    console.print("  [dim]Issues include: missing phones/emails/DOBs, bad postcodes, "
                  "inconsistent deleted flags, placeholder descriptions, duplicate person[/dim]")


def read_csv(name: str) -> list[dict]:
    path = SOURCE_DIR / f"{name}.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY not set. Add it to your .env file.[/red]")
        return

    global SOURCE_SCHEMA
    SOURCE_SCHEMA = load_schema()

    console.print(Panel(
        "[bold]AI-Powered Source Data Generator[/bold]\n\n"
        "Building a realistic, internally consistent recruitment database.\n"
        "Estimated cost: $0.50 – $1.50 from your API balance.",
        style="blue"
    ))

    gen_lookups()
    gen_recruiters()
    gen_addresses()
    gen_accounts()
    gen_persons()
    gen_associates()
    gen_gdpr()
    gen_jobs()
    gen_placements()
    gen_employee_data()
    gen_documents()
    gen_notes()
    gen_activities()
    gen_finance()
    gen_timesheets()
    gen_compliance_references()
    gen_skills_tags_hotlists()
    gen_system()
    inject_dirty_data()

    console.print(Panel(
        "[green]Done — all source CSVs written to sample_data/source/[/green]\n\n"
        "Next step: [bold]python pipeline.py[/bold]",
        style="green"
    ))


if __name__ == "__main__":
    main()
