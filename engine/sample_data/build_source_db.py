"""
sample_data/build_source_db.py

Builds the legacy SOURCE database in SQL Server from `Source Schema.csv`
and the CSVs in sample_data/source/.

Steps
  0. dedupe    : dedupe_generated.py gives unintended repeats in the AI-generated
                 CSVs (same company / person / street) distinct identities.
  1. fill-gaps : deterministically generates the tables the first data generator never
                 produced (Req, Req_Rates, Referees, Leads) and backfills the
                 FK columns that were left blank because of it
                 (Req_Hired.Req_ID, PONo.ReqID, Schedule.Req_ID,
                 TimesheetItems.Req_ID, Req_Documents.Req_ID, EmpRef.Ref_ID).
                 Only empty columns / missing files are touched.
  2. ddl       : sql/source/01_create_source_db.sql
                 One table per schema table, declared types, PRIMARY KEYs.
                 sql/source/03_add_constraints.sql (after the load)
                 Foreign keys from relationships.py, created WITH CHECK so the
                 clean baseline is proven relationally consistent.
  3. data      : sql/source/02_load_source_data.sql  (batched INSERTs)
                 Every value is checked against its declared type; values
                 that cannot be stored are loaded as NULL and logged to
                 sql/source/load_rejects.csv.
  4. defects   : sql/source/04_inject_legacy_defects.sql via inject_defects.py
                 (known data-quality problems + answer key; skip with --no-defects).
                 FKs it breaks are disabled first, so they show as not trusted.
  5. load      : runs the scripts with sqlcmd (Windows auth).

Run
  python sample_data/build_source_db.py                       # steps 1-3
  python sample_data/build_source_db.py --load                # + load into localhost\\SQLEXPRESS
  python sample_data/build_source_db.py --load --server .\\SQL2022 --database Cobaltdesk_Legacy
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
SOURCE_DIR  = ROOT / "sample_data" / "source"
SCHEMA_FILE = ROOT / "Source Schema.csv"
SQL_DIR     = ROOT / "sql" / "source"

DEFAULT_SERVER = r"localhost\SQLEXPRESS"
DEFAULT_DB     = "Cobaltdesk_Legacy"


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

def load_schema() -> dict[str, list[dict]]:
    """{table: [{col, type, desc, key}, ...]} in schema order.

    Tolerates unquoted DECIMAL(p,s) types (e.g. Addresses.Longitude), which
    split into an extra CSV field.
    """
    schema: dict[str, list[dict]] = defaultdict(list)
    with open(SCHEMA_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if not row or not row[0].strip():
                continue
            table, col, dtype, *rest = [c.strip() for c in row]
            if dtype.upper().startswith("DECIMAL(") and ")" not in dtype and rest:
                dtype = f"{dtype},{rest.pop(0)}"
            rest += ["", ""]
            schema[table].append({"col": col, "type": dtype.upper(),
                                  "desc": rest[0], "key": rest[1]})
    from relationships import TYPE_OVERRIDES
    for (table, col), new_type in TYPE_OVERRIDES.items():
        for c in schema.get(table, []):
            if c["col"] == col:
                c["declared_type"], c["type"] = c["type"], new_type
    return dict(schema)


# ══════════════════════════════════════════════════════════════════════════════
# CSV HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def read_csv(table: str) -> list[dict]:
    with open(SOURCE_DIR / f"{table}.csv", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(table: str, rows: list[dict], columns: list[str]):
    with open(SOURCE_DIR / f"{table}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: "" if r.get(c) is None else r.get(c) for c in columns})


def column_is_blank(rows: list[dict], col: str) -> bool:
    return all(not (r.get(col) or "").strip() for r in rows)


def dt(d: datetime | date) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S") if isinstance(d, datetime) else d.strftime("%Y-%m-%d")


def parse_d(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — FILL GAPS
# ══════════════════════════════════════════════════════════════════════════════

FIRST = ["Oliver", "Amelia", "Harry", "Isla", "George", "Ava", "Noah", "Mia", "Jack", "Sophie",
         "Mohammed", "Aisha", "Daniel", "Grace", "Ravi", "Chloe", "Tom", "Fatima", "Liam", "Hannah",
         "Kwame", "Zara", "Ethan", "Priya", "Lewis", "Niamh", "Callum", "Leah", "Adam", "Megan",
         "Tomasz", "Ewa", "Samuel", "Olivia", "Arjun", "Emily", "Connor", "Yusuf", "Rachel", "Ben"]
LAST = ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Patel",
        "Robinson", "Wright", "Thompson", "Evans", "Walker", "White", "Roberts", "Green", "Hall",
        "Khan", "Hughes", "Edwards", "Clarke", "Turner", "Hill", "Mensah", "Kowalski", "Murphy",
        "O'Brien", "Campbell", "Stewart", "Ahmed", "Begum", "Shah", "Morgan", "Cooper", "Ward"]

JOB_TITLES = {
    "Contract": ["Data Engineer", "Senior Data Engineer", "BI Developer", "Data Migration Analyst",
                 "SQL Server DBA", "Azure Data Engineer", "Power BI Developer", "Integration Developer",
                 "Business Analyst", "Technical Project Manager", "Dynamics 365 Consultant",
                 "Cloud Infrastructure Engineer", "QA Test Analyst", "Python Developer"],
    "Permanent": ["Head of Data", "Data Analyst", "Analytics Engineer", "Software Engineer",
                  "Finance Systems Analyst", "HR Systems Administrator", "Product Owner",
                  "CRM Manager", "Information Governance Officer", "Data Architect",
                  "Full Stack Developer", "IT Service Manager", "Payroll Specialist"],
}

REQ_STATUSES = [  # (StatusID, StatusText, ReqStat)
    (1, "Open", "Active"), (2, "Interviewing", "Active"), (3, "Offer Made", "Active"),
    (4, "Filled", "Closed"), (5, "On Hold", "Inactive"), (6, "Cancelled", "Closed"),
]


def fake_phone(rng: random.Random) -> str:
    return rng.choice([f"07{rng.randint(100, 999)} {rng.randint(100000, 999999)}",
                       f"+44 20 {rng.randint(7000, 8999)} {rng.randint(1000, 9999)}",
                       f"0161 {rng.randint(200, 999)} {rng.randint(1000, 9999)}"])


def fill_gaps(schema: dict, force: bool = False) -> list[str]:
    rng = random.Random(2024)
    log: list[str] = []

    accounts    = read_csv("Accounts")
    acct_by_id  = {a["Account_ID"]: a for a in accounts}
    acct_assoc  = defaultdict(list)
    for r in read_csv("AccountAssociates"):
        acct_assoc[r["AccountID"]].append(r["AssociateID"])
    recruiters  = [r["RecruiterID"] for r in read_csv("Recruiter")]
    hired       = read_csv("Req_Hired")
    pos         = read_csv("PONo")

    # ── Req + Req_Rates ───────────────────────────────────────────────────────
    if force or not (SOURCE_DIR / "Req.csv").exists():
        reqs, rates = [], []
        reqs_by_acct_type: dict[tuple, list[dict]] = defaultdict(list)

        def new_req(account_id: str, worktype: str, start: datetime, filled: bool) -> dict:
            rid = len(reqs) + 1
            acct = acct_by_id.get(account_id, {})
            title = rng.choice(JOB_TITLES[worktype])
            created = start - timedelta(days=rng.randint(20, 75))
            status = REQ_STATUSES[3] if filled else rng.choices(
                REQ_STATUSES, weights=[30, 20, 8, 0, 10, 12])[0]
            contract = worktype == "Contract"
            end = start + timedelta(days=rng.choice([90, 180, 182, 270, 365])) if contract else None
            owner = rng.choice(recruiters)
            req = {
                "ReqID": rid, "Req_Title": title,
                "AssociateID": rng.choice(acct_assoc[account_id]) if acct_assoc.get(account_id) else "",
                "AccountID": account_id, "ReqStat": status[2], "Req_RateID": rid,
                "Compensation_package": (
                    "Day rate outside IR35, hybrid 2 days on site." if contract and rng.random() < .5 else
                    "Day rate inside IR35 via umbrella, fully remote." if contract else
                    rng.choice(["Base salary + 10% bonus, 25 days holiday, 5% pension match.",
                                "Competitive salary, private healthcare, hybrid working.",
                                "Salary DOE, car allowance, 28 days holiday."])),
                "StatusID": status[0], "StatusText": status[1],
                "StatusDate": dt(created + timedelta(days=rng.randint(1, 30))).split(" ")[0],
                "CurrencyCode": "GBP", "WorktypeID": 2 if contract else 1, "Worktype": worktype,
                "Vacancy": rng.choices([1, 2, 3, 5], weights=[70, 18, 8, 4])[0],
                "WorkingHours": rng.choice([35, 37, 37, 40]),
                "Address_ID": acct.get("AddressID", ""), "ReqSource": rng.randint(1, 5),
                "StartDate": dt(start), "ExpiryDate": dt(created + timedelta(days=60)),
                "EndDate": dt(end) if end else "",
                "Req_Description": f"{acct.get('Account_name', 'Client')} is hiring a {title} "
                                   f"({worktype.lower()}). " + rng.choice([
                    "Must have strong SQL Server and stakeholder skills.",
                    "Experience of large-scale data migration essential.",
                    "Public sector or higher education experience preferred.",
                    "Azure and CI/CD experience highly desirable.",
                    "Immediate start, SC clearance an advantage."]),
                "PONumber": "", "Deleted": 1 if rng.random() < .03 else 0,
                "CreatedBy": owner, "UpdatedBy": rng.choice(recruiters),
                "CreatedAt": dt(created), "UpdatedAt": dt(created + timedelta(days=rng.randint(1, 90))),
            }
            if contract:
                pay = round(rng.uniform(300, 750), 2)
                rate = {"Payrate": pay, "BillRate": round(pay * rng.uniform(1.15, 1.35), 2), "Salary": "",
                        "Notes": "Day rates (GBP)."}
            else:
                rate = {"Payrate": "", "BillRate": "", "Salary": f"{rng.randrange(32000, 95000, 500)}.00",
                        "Notes": f"Fee {rng.choice([15, 18, 20, 22])}% of first-year salary."}
            rates.append({"Req_RateID": rid, "Req_ID": rid, **rate, "UpdatedAt": req["UpdatedAt"],
                          "CreatedBy": owner, "UpdatedBy": req["UpdatedBy"]})
            reqs.append(req)
            reqs_by_acct_type[(account_id, worktype)].append(req)
            return req

        # jobs that produced the existing placements / pipeline rows
        if force or column_is_blank(hired, "Req_ID"):
            for h in sorted(hired, key=lambda r: r["StartDate"]):
                key = (h["Account_ID"], h["Worktype"] or "Contract")
                start = parse_d(h["StartDate"]) or datetime(2023, 1, 1)
                # only reuse a job that was raised at least a week before this placement starts
                existing = [r for r in reqs_by_acct_type.get(key, [])
                            if parse_d(r["CreatedAt"]) <= start - timedelta(days=7)]
                if existing and rng.random() < .55:
                    req = rng.choice(existing)
                else:
                    req = new_req(key[0], key[1], start, filled=h["Pipeline_Stage"] == "Placed")
                h["Req_ID"] = req["ReqID"]
                if h["Pipeline_Stage"] == "Placed" and req["StatusID"] != 4:
                    req.update(StatusID=4, StatusText="Filled", ReqStat="Closed")
            write_csv("Req_Hired", hired, [c["col"] for c in schema["Req_Hired"]])
            log.append(f"Req_Hired.Req_ID backfilled ({len(hired)} rows)")

        # open jobs with no pipeline yet
        for _ in range(60):
            new_req(rng.choice(accounts)["Account_ID"], rng.choice(["Contract", "Permanent"]),
                    datetime(2024, 1, 1) + timedelta(days=rng.randint(0, 300)), filled=False)

        # PONo.ReqID: purchase orders raised by the client for one of its contract jobs
        if force or column_is_blank(pos, "ReqID"):
            # POs fund contract jobs that actually have a placed contractor (timesheets hang off them)
            placed_contract = {h["Req_ID"] for h in hired if h["Pipeline_Stage"] == "Placed" and h["Worktype"] == "Contract"}
            contract_reqs = [r for r in reqs if r["ReqID"] in placed_contract] or \
                            [r for r in reqs if r["Worktype"] == "Contract"]
            for po in pos:
                same = [r for r in contract_reqs if r["AccountID"] == po["VendorID"]]
                req = rng.choice(same or contract_reqs)
                po["ReqID"] = req["ReqID"]
                po["VendorID"] = req["AccountID"]          # the client on the PO is the client of the job
                req["PONumber"] = req["PONumber"] or po["PONo"]
            write_csv("PONo", pos, [c["col"] for c in schema["PONo"]])
            log.append(f"PONo.ReqID backfilled ({len(pos)} rows)")

        write_csv("Req", reqs, [c["col"] for c in schema["Req"]])
        write_csv("Req_Rates", rates, [c["col"] for c in schema["Req_Rates"]])
        log.append(f"Req.csv generated ({len(reqs)} rows)")
        log.append(f"Req_Rates.csv generated ({len(rates)} rows)")

    reqs = read_csv("Req")
    reqs_by_acct = defaultdict(list)
    for r in reqs:
        reqs_by_acct[r["AccountID"]].append(r["ReqID"])
    po_to_req = {p["PONo"]: p["ReqID"] for p in read_csv("PONo")}

    # ── Schedule.Req_ID ───────────────────────────────────────────────────────
    sched = read_csv("Schedule")
    if force or column_is_blank(sched, "Req_ID"):
        for s in sched:
            if s["ScheduleType"] != "Client Meeting" and reqs_by_acct.get(s["Account_ID"]):
                s["Req_ID"] = rng.choice(reqs_by_acct[s["Account_ID"]])
        write_csv("Schedule", sched, [c["col"] for c in schema["Schedule"]])
        log.append("Schedule.Req_ID backfilled")

    # ── TimesheetItems.Req_ID (via TimeSheets.PONo -> PONo.ReqID) ─────────────
    items = read_csv("TimesheetItems")
    if force or column_is_blank(items, "Req_ID"):
        ts_po = {t["ID"]: t["PONo"] for t in read_csv("TimeSheets")}
        for it in items:
            it["Req_ID"] = po_to_req.get(ts_po.get(it["Timesheet_ID"], ""), "")
        write_csv("TimesheetItems", items, [c["col"] for c in schema["TimesheetItems"]])
        log.append("TimesheetItems.Req_ID backfilled via TimeSheets.PONo")

    # ── Req_Documents.Req_ID ──────────────────────────────────────────────────
    rdocs = read_csv("Req_Documents")
    if force or column_is_blank(rdocs, "Req_ID"):
        for d in rdocs:
            d["Req_ID"] = rng.choice(reqs)["ReqID"]
        write_csv("Req_Documents", rdocs, [c["col"] for c in schema["Req_Documents"]])
        log.append("Req_Documents.Req_ID backfilled")

    # ── Referees + EmpRef.Ref_ID ──────────────────────────────────────────────
    if force or not (SOURCE_DIR / "Referees.csv").exists():
        emprefs = read_csv("EmpRef")
        companies = sorted({h["PlaceofWork"] for h in read_csv("EmpHist") if h["PlaceofWork"]}) \
            or [a["Account_name"] for a in accounts]
        titles = {"Line Manager": ["Engineering Manager", "Head of Data", "Delivery Manager", "Team Lead"],
                  "HR Contact": ["HR Business Partner", "HR Advisor", "People Operations Manager"],
                  "Colleague": ["Senior Developer", "Data Analyst", "Project Manager"]}
        referees = []
        for i, e in enumerate(emprefs, 1):
            fn, ln = rng.choice(FIRST), rng.choice(LAST)
            company = rng.choice(companies)
            domain = re.sub(r"[^a-z]", "", company.lower())[:18] or "example"
            referees.append({
                "Referee_ID": i, "Fullname": f"{fn} {ln}",
                "email": f"{fn.lower()}.{re.sub('[^a-z]', '', ln.lower())}@{domain}.co.uk",
                "Telephone": fake_phone(rng), "Company": company,
                "Job_Title": rng.choice(titles.get(e["Relationship"], sum(titles.values(), []))),
                "Notes": rng.choice(["Prefers contact by email.", "Available after 2pm.", "",
                                     "Former direct manager.", "Reference via HR only."]),
                "CreatedAt": dt((parse_d(e["CreatedAt"]) or datetime(2023, 1, 1)) - timedelta(days=rng.randint(1, 14))),
            })
            e["Ref_ID"] = i
        write_csv("Referees", referees, [c["col"] for c in schema["Referees"]])
        write_csv("EmpRef", emprefs, [c["col"] for c in schema["EmpRef"]])
        log.append(f"Referees.csv generated ({len(referees)} rows); EmpRef.Ref_ID backfilled")

    # ── Leads ─────────────────────────────────────────────────────────────────
    if force or not (SOURCE_DIR / "Leads.csv").exists():
        addresses = {a["AddressID"]: a for a in read_csv("Addresses")}
        doc_ids = [d["Doc_ID"] for d in read_csv("Documents")]
        leads = []
        for i in range(1, 121):
            acct = rng.choice(accounts)
            fn, ln = rng.choice(FIRST), rng.choice(LAST)
            addr = addresses.get(acct["AddressID"], {})
            sourced = datetime(2023, 1, 1) + timedelta(days=rng.randint(0, 640), hours=rng.randint(8, 17))
            domain = re.sub(r"https?://(www\.)?", "", acct.get("Website") or "").strip("/") or "example.co.uk"
            status = rng.choices(["New", "Contacted", "Qualified", "Proposal Sent", "Won", "Lost"],
                                 weights=[20, 25, 20, 12, 10, 13])[0]
            leads.append({
                "Lead_ID": i, "Name": f"{fn} {ln}", "Lead_Status": status,
                "Lead_Source": rng.choice(["LinkedIn", "Referral", "Website Form", "Cold Call",
                                           "Job Board", "Event"]),
                "Lead_Name": rng.choice(["Data team expansion", "CRM replacement programme",
                                         "Azure migration contractors", "Graduate scheme",
                                         "Interim finance cover", "Dynamics 365 rollout"]),
                "Associate_ID": rng.choice(acct_assoc[acct["Account_ID"]]) if acct_assoc.get(acct["Account_ID"]) and rng.random() < .6 else "",
                "Account_ID": acct["Account_ID"],
                "Req_ID": rng.choice(reqs_by_acct[acct["Account_ID"]]) if status == "Won" and reqs_by_acct.get(acct["Account_ID"]) else "",
                "Email": f"{fn.lower()}.{re.sub('[^a-z]', '', ln.lower())}@{domain}",
                "Phone": fake_phone(rng),
                "Note": rng.choice(["Met at the Data Leaders breakfast.", "Asked for rate card.",
                                    "Budget signed off for Q3.", "Follow up after their restructure.", ""]),
                "Consent_GDPR": 1 if rng.random() < .8 else 0,
                "URL": acct.get("Website", ""),
                "Address_Line1": addr.get("Address_line1", ""), "Address_Line2": addr.get("Address_line2", ""),
                "City": addr.get("City", ""), "Country": addr.get("Country", ""),
                "Document_ID": rng.choice(doc_ids) if rng.random() < .2 else "",
                "Sourced_Date": dt(sourced), "Assigned_To": rng.choice(recruiters),
                "CreatedBy": rng.choice(recruiters), "UpdatedBy": rng.choice(recruiters),
                "Lead_Score": rng.randint(1, 5),
            })
        write_csv("Leads", leads, [c["col"] for c in schema["Leads"]])
        log.append(f"Leads.csv generated ({len(leads)} rows)")

    log += repair_references(schema)
    import repair_baseline
    log += repair_baseline.run(read_csv, write_csv, {t: [c["col"] for c in cs] for t, cs in schema.items()}, ROOT)
    return log


def repair_references(schema: dict) -> list[str]:
    """Fix the few broken references in the AI-generated baseline so every FK validates."""
    log = []
    persons, consents = read_csv("Person"), read_csv("GDPR_Consent")
    consent_ids = {c["GDPR_ConsentID"] for c in consents}
    consent_by_person = {c["Person_ID"]: c["GDPR_ConsentID"] for c in consents}
    fixed = 0
    for p in persons:
        if p["GDPRConsent_ID"] and p["GDPRConsent_ID"] not in consent_ids:
            p["GDPRConsent_ID"] = consent_by_person.get(p["Person_ID"], "")
            fixed += 1
    if fixed:
        write_csv("Person", persons, [c["col"] for c in schema["Person"]])
        log.append(f"Person.GDPRConsent_ID: {fixed} dangling reference(s) repaired")

    prof_person = {e["Emp_ProfileID"]: e["Person_ID"] for e in read_csv("Emp_Profile")}
    docs, fixed = read_csv("Emp_Documents"), 0
    for d in docs:
        want = prof_person.get(d["Emp_ID"])
        if want and d["Person_ID"] != want:
            d["Person_ID"], fixed = want, fixed + 1
    if fixed:
        write_csv("Emp_Documents", docs, [c["col"] for c in schema["Emp_Documents"]])
        log.append(f"Emp_Documents.Person_ID: {fixed} aligned with the employee profile's person")
    return log


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 + 3 — SQL GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def q(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def sql_str(s: str) -> str:
    return "N'" + s.replace("'", "''") + "'"


def to_sql_literal(value: str, dtype: str) -> tuple[str, str | None]:
    """Return (literal, reject_reason). Empty -> NULL."""
    v = (value or "").strip()
    if v == "" or v.upper() == "NULL":
        return "NULL", None
    t = dtype.upper()
    try:
        if t == "INT":
            f = float(v)
            if f != int(f) or not -2**31 <= f < 2**31:
                raise ValueError
            return str(int(f)), None
        if t == "BIT":
            m = {"1": "1", "0": "0", "TRUE": "1", "FALSE": "0", "Y": "1", "N": "0", "YES": "1", "NO": "0"}
            if v.upper() not in m:
                raise ValueError
            return m[v.upper()], None
        if t == "FLOAT":
            return repr(float(v)), None
        if t.startswith("DECIMAL"):
            p, s = map(int, re.findall(r"\d+", t))
            d = Decimal(v).quantize(Decimal(1).scaleb(-s))
            if len(d.as_tuple().digits) - (-d.as_tuple().exponent) > p - s:
                raise ValueError
            return str(d), None
        if t in ("DATETIME", "DATE"):
            d = parse_d(v)
            if not d or not (1753 <= d.year <= 9999):
                raise ValueError
            return ("'" + (d.strftime("%Y-%m-%dT%H:%M:%S") if t == "DATETIME" else d.strftime("%Y-%m-%d")) + "'"), None
        if t == "TIME":
            datetime.strptime(v, "%H:%M:%S" if v.count(":") == 2 else "%H:%M")
            return "'" + v + "'", None
        m = re.match(r"N?VARCHAR\((\d+|MAX)\)", t)
        if m:
            if m.group(1) != "MAX" and len(value) > int(m.group(1)):
                return "NULL", f"length {len(value)} > {m.group(1)}"
            return sql_str(value), None
    except (ValueError, InvalidOperation, OverflowError):
        return "NULL", f"not a valid {t}"
    return sql_str(value), None


def write_ddl(schema: dict, db: str):
    out = [f"-- Generated by sample_data/build_source_db.py from 'Source Schema.csv' — do not edit by hand.",
           f"-- Legacy recruitment CRM (source system). Tables + PKs; FKs are added by 03_add_constraints.sql after the load.",
           "SET NOCOUNT ON;", "USE master;", "GO",
           f"IF DB_ID(N'{db}') IS NOT NULL",
           "BEGIN",
           f"    ALTER DATABASE {q(db)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE;",
           f"    DROP DATABASE {q(db)};",
           "END", "GO",
           f"CREATE DATABASE {q(db)};", "GO",
           # SQL Express defaults AUTO_CLOSE ON: the DB shuts after every connection and
           # metadata/plan caches are lost, making each new query (e.g. from DBeaver) crawl.
           f"ALTER DATABASE {q(db)} SET AUTO_CLOSE OFF;", "GO",
           f"USE {q(db)};", "GO", ""]
    for table, cols in schema.items():
        pks = [c["col"] for c in cols if c["key"].lower() == "primary key"]
        lines = []
        for c in cols:
            nn = " NOT NULL" if c["col"] in pks else " NULL"
            lines.append(f"    {q(c['col'])} {c['type']}{nn}")
        if pks:
            lines.append(f"    CONSTRAINT {q('PK_' + table)} PRIMARY KEY ({', '.join(map(q, pks))})")
        out.append(f"CREATE TABLE dbo.{q(table)} (\n" + ",\n".join(lines) + "\n);")
        # descriptions -> extended properties (shows up in SSMS / data dictionary queries)
        for c in cols:
            desc = c["desc"] or ("Foreign key" if c["key"].lower() == "foreign key" else "")
            if desc:
                out.append(f"EXEC sys.sp_addextendedproperty N'MS_Description', {sql_str(desc)}, "
                           f"N'SCHEMA', N'dbo', N'TABLE', {sql_str(table)}, N'COLUMN', {sql_str(c['col'])};")
        out.append("GO\n")
    (SQL_DIR / "01_create_source_db.sql").write_text("\n".join(out), encoding="utf-8")


def fk_name(child: str, col: str) -> str:
    return f"FK_{child}_{col}"


def write_constraints(schema: dict, db: str) -> int:
    """Unique keys + foreign keys, created WITH CHECK so the clean baseline is proven consistent."""
    from relationships import UNIQUE_KEYS, all_foreign_keys
    out = ["-- Generated by sample_data/build_source_db.py — do not edit by hand.",
           "-- Relational integrity for the clean baseline. Every FK is validated (WITH CHECK):",
           "-- if this script fails, the baseline data has a broken reference.",
           "SET NOCOUNT ON;", "SET XACT_ABORT ON;", f"USE {q(db)};", "GO", "BEGIN TRANSACTION;"]
    for t, c in UNIQUE_KEYS:
        out.append(f"ALTER TABLE dbo.{q(t)} ADD CONSTRAINT {q(f'UQ_{t}_{c}')} UNIQUE ({q(c)});")
    fks = all_foreign_keys(schema)
    for child, col, parent, pcol in fks:
        out.append(f"ALTER TABLE dbo.{q(child)} WITH CHECK ADD CONSTRAINT {q(fk_name(child, col))} "
                   f"FOREIGN KEY ({q(col)}) REFERENCES dbo.{q(parent)} ({q(pcol)});")
        out.append(f"CREATE INDEX {q(f'IX_{child}_{col}')} ON dbo.{q(child)} ({q(col)});")
    out += ["COMMIT;", f"PRINT 'Added {len(fks)} foreign keys';", "GO"]
    (SQL_DIR / "03_add_constraints.sql").write_text("\n".join(out), encoding="utf-8")
    return len(fks)


def write_data(schema: dict, db: str) -> tuple[dict, list, list]:
    out = ["-- Generated by sample_data/build_source_db.py — do not edit by hand.",
           "SET NOCOUNT ON;", f"USE {q(db)};", "GO", ""]
    counts, rejects, notes = {}, [], []
    for table, cols in schema.items():
        path = SOURCE_DIR / f"{table}.csv"
        if not path.exists():
            notes.append(f"{table}: no CSV, table created empty")
            counts[table] = 0
            continue
        rows = read_csv(table)
        csv_cols = list(rows[0].keys()) if rows else []
        extra = [c for c in csv_cols if c not in {s["col"] for s in cols}]
        if extra:
            notes.append(f"{table}: CSV columns not in schema, ignored: {extra}")
        missing = [s["col"] for s in cols if s["col"] not in csv_cols]
        if missing and rows:
            notes.append(f"{table}: schema columns missing from CSV, loaded as NULL: {missing}")
        pk = next((c["col"] for c in cols if c["key"].lower() == "primary key"), None)
        col_list = ", ".join(q(c["col"]) for c in cols)
        values = []
        for i, r in enumerate(rows, 2):
            lits = []
            for c in cols:
                lit, why = to_sql_literal(r.get(c["col"], ""), c["type"])
                if why:
                    rejects.append({"table": table, "csv_line": i, "pk": r.get(pk, "") if pk else "",
                                    "column": c["col"], "declared_type": c["type"],
                                    "value": (r.get(c["col"]) or "")[:200], "reason": why})
                lits.append(lit)
            values.append("(" + ", ".join(lits) + ")")
        out.append(f"PRINT 'Loading dbo.{table} ({len(values)} rows)';")
        for b in range(0, len(values), 500):
            out.append(f"INSERT INTO dbo.{q(table)} ({col_list}) VALUES\n" + ",\n".join(values[b:b + 500]) + ";")
        out.append("GO")
        counts[table] = len(values)
    (SQL_DIR / "02_load_source_data.sql").write_text("\n".join(out), encoding="utf-8")

    with open(SQL_DIR / "load_rejects.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["table", "csv_line", "pk", "column", "declared_type", "value", "reason"])
        w.writeheader()
        w.writerows(rejects)
    with open(SQL_DIR / "expected_row_counts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["table", "csv_rows"])
        w.writerows(sorted(counts.items()))
    return counts, rejects, notes


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — LOAD
# ══════════════════════════════════════════════════════════════════════════════

def run_sqlcmd(server: str, script: Path):
    cmd = ["sqlcmd", "-S", server, "-E", "-b", "-f", "65001", "-i", str(script)]
    print(f"  > sqlcmd -S {server} -i {script.relative_to(ROOT)}")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(res.stdout[-3000:], res.stderr[-3000:], sep="\n")
        sys.exit(f"sqlcmd failed on {script.name}")


def verify(server: str, db: str, counts: dict):
    query = ("SET NOCOUNT ON; SELECT t.name + ',' + CAST(SUM(p.rows) AS varchar(20)) FROM sys.tables t "
             "JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1) GROUP BY t.name")
    res = subprocess.run(["sqlcmd", "-S", server, "-E", "-d", db, "-h", "-1", "-W", "-Q", query],
                         capture_output=True, text=True)
    actual = dict(line.split(",") for line in res.stdout.split() if "," in line)
    bad = {t: (n, int(actual.get(t, -1))) for t, n in counts.items() if int(actual.get(t, -1)) != n}
    print(f"  Row-count check: {len(counts) - len(bad)}/{len(counts)} tables match CSV row counts")
    for t, (exp, got) in bad.items():
        print(f"    MISMATCH {t}: csv={exp} db={got}")


# ══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--load", action="store_true", help="run the generated scripts with sqlcmd")
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--database", default=DEFAULT_DB)
    ap.add_argument("--skip-fill", action="store_true", help="don't generate missing tables / backfill FKs")
    ap.add_argument("--force-fill", action="store_true", help="regenerate gap tables even if they exist")
    ap.add_argument("--no-defects", action="store_true", help="load the clean baseline only (skip 04_inject_legacy_defects.sql)")
    args = ap.parse_args()

    SQL_DIR.mkdir(parents=True, exist_ok=True)
    schema = load_schema()
    print(f"Schema: {len(schema)} tables, {sum(map(len, schema.values()))} columns")

    if not args.skip_fill:
        import dedupe_generated
        print("Step 0  remove unintended repeats from AI-generated data")
        cols = {t: [c["col"] for c in cs] for t, cs in schema.items()}
        for line in dedupe_generated.run(read_csv, write_csv, cols) or ["nothing to do"]:
            print("  -", line)
        print("Step 1  fill gaps")
        for line in fill_gaps(schema, force=args.force_fill) or ["nothing to do"]:
            print("  -", line)

    print("Step 2  DDL  -> sql/source/01_create_source_db.sql")
    write_ddl(schema, args.database)
    print("Step 3  data -> sql/source/02_load_source_data.sql")
    counts, rejects, notes = write_data(schema, args.database)
    print(f"  {sum(counts.values())} rows across {len(counts)} tables, {len(rejects)} rejected values "
          f"(sql/source/load_rejects.csv)")
    for n in notes:
        print("  !", n)

    overridden = [f"{t}.{c['col']} {c['declared_type']} -> {c['type']}" for t, cs in schema.items()
                  for c in cs if "declared_type" in c]
    if overridden:
        print("  type overrides (so FKs can be declared):", "; ".join(overridden))
    n_fk = write_constraints(schema, args.database)
    print(f"Step 3b constraints -> sql/source/03_add_constraints.sql  ({n_fk} foreign keys, validated)")

    expected = dict(counts)
    if not args.no_defects:
        from inject_defects import build as build_defects
        inserted, manifest = build_defects(schema, args.database)
        for t, n in inserted.items():
            expected[t] += n
        print(f"Step 4  defects -> sql/source/04_inject_legacy_defects.sql  ({len(manifest)} planted, "
              f"answer key: sql/source/defect_manifest.csv, summary: docs/source_defects.md)")

    if args.load:
        print(f"Step 5  load into {args.server} / {args.database}")
        run_sqlcmd(args.server, SQL_DIR / "01_create_source_db.sql")
        run_sqlcmd(args.server, SQL_DIR / "02_load_source_data.sql")
        run_sqlcmd(args.server, SQL_DIR / "03_add_constraints.sql")
        if not args.no_defects:
            run_sqlcmd(args.server, SQL_DIR / "04_inject_legacy_defects.sql")
        profiling = ROOT / "sql" / "profiling" / "00_install_profiling.sql"
        if profiling.exists():   # dq.* helper procs used by sql/profiling/01_profiling_queries.sql
            run_sqlcmd(args.server, profiling)
        verify(args.server, args.database, expected)


if __name__ == "__main__":
    main()
