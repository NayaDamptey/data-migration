"""
validation/baseline_rules.py

Data-quality rules for the legacy recruitment CRM source (DuckDB SQL).

Every rule is a query returning the violating rows as (pk, detail). On the
clean baseline every rule must return 0 rows (tests/test_baseline.py). On the
legacy DB with planted defects every answer-key entry must be hit by at least
one rule (tests/test_defects.py).

`category` matches the defect categories in sql/source/defect_manifest.csv,
or CONSISTENCY / FINANCE / ROLE for rules that guard the baseline's logic.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sample_data"))
from build_source_db import load_schema          # noqa: E402
from relationships import all_foreign_keys        # noqa: E402


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    table: str
    description: str
    sql: str            # SELECT <pk> AS pk, <detail> AS detail ...


SCHEMA = load_schema()
PK = {t: next(c["col"] for c in cs if c["key"].lower() == "primary key") for t, cs in SCHEMA.items()}

EMAIL_RE = r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$"
POSTCODE_RE = r"^([A-Z]{1,2}[0-9]{1,2}|[A-Z]{1,2}[0-9][A-Z]) [0-9][A-Z]{2}$"
NI_RE = r"^[ABCEGHJ-PR-TW-Z][ABCEGHJ-NPR-TW-Z][0-9]{6}[A-D]$"
MOJIBAKE = "(Â|â€|Ã|�)"


def q(name: str) -> str:
    return f'"{name}"'


def _key_rules() -> list[Rule]:
    rules = []
    for t, pk in PK.items():
        rules.append(Rule(f"pk_unique.{t}", "INTEGRITY", t, f"{t}.{pk} unique and not null",
                          f"SELECT {q(pk)}, 'duplicate or NULL key' FROM {q(t)} GROUP BY {q(pk)} "
                          f"HAVING COUNT(*) > 1 OR {q(pk)} IS NULL"))
    for child, col, parent, pcol in all_foreign_keys(SCHEMA):
        rules.append(Rule(f"fk.{child}.{col}", "ORPHAN_FK", child, f"{child}.{col} -> {parent}.{pcol} resolves",
                          f"SELECT c.{q(PK[child])}, CAST(c.{q(col)} AS VARCHAR) FROM {q(child)} c "
                          f"WHERE c.{q(col)} IS NOT NULL AND NOT EXISTS "
                          f"(SELECT 1 FROM {q(parent)} p WHERE p.{q(pcol)} = c.{q(col)})"))
    return rules


def _poly(table: str, pk: str, type_col: str, id_col: str) -> Rule:
    return Rule(f"poly.{table}.{id_col}", "ORPHAN_FK", table,
                f"{table}.{id_col} resolves via {type_col} (polymorphic, no FK)", f"""
        SELECT x.{q(pk)}, x.{q(type_col)} || ' ' || CAST(x.{q(id_col)} AS VARCHAR) FROM {q(table)} x
        WHERE x.{q(id_col)} IS NOT NULL AND NOT (
               (x.{q(type_col)} = 'Associate' AND x.{q(id_col)} IN (SELECT AssociateID FROM Associates))
            OR (x.{q(type_col)} = 'Req'       AND x.{q(id_col)} IN (SELECT ReqID FROM Req))
            OR (x.{q(type_col)} = 'Account'   AND x.{q(id_col)} IN (SELECT Account_ID FROM Accounts))
            OR (x.{q(type_col)} = 'Person'    AND x.{q(id_col)} IN (SELECT Person_ID FROM Person))
            OR (x.{q(type_col)} = 'Timesheet' AND x.{q(id_col)} IN (SELECT ID FROM TimeSheets))
            OR (x.{q(type_col)} = 'Invoice'   AND x.{q(id_col)} IN (SELECT InvoiceID FROM Invoice)))""")


def _blank(table, col):
    return Rule(f"required.{table}.{col}", "MISSING_REQUIRED", table, f"{table}.{col} present",
                f"SELECT {q(PK[table])}, 'missing' FROM {q(table)} WHERE NULLIF(TRIM({q(col)}), '') IS NULL")


def _regex(rule_id, category, table, col, pattern, desc):
    return Rule(rule_id, category, table, desc,
                f"SELECT {q(PK[table])}, {q(col)} FROM {q(table)} "
                f"WHERE {q(col)} IS NOT NULL AND NOT regexp_matches({q(col)}, '{pattern.replace(chr(39), chr(39) * 2)}')")


def _domain(table, col, allowed):
    vals = ", ".join("'" + v + "'" for v in allowed)
    return Rule(f"domain.{table}.{col}", "NON_STANDARD_DOMAIN", table, f"{table}.{col} in ({', '.join(allowed)})",
                f"SELECT {q(PK[table])}, '[' || {q(col)} || ']' FROM {q(table)} WHERE {q(col)} IS NOT NULL AND {q(col)} NOT IN ({vals})")


def _name_hygiene(table, col):
    return Rule(f"hygiene.{table}.{col}", "WHITESPACE_CASE", table,
                f"{table}.{col}: no padding/double spaces/tabs, not ALL CAPS or all lower", f"""
        SELECT {q(PK[table])}, '[' || {q(col)} || ']' FROM {q(table)}
        WHERE NULLIF(TRIM({q(col)}), '') IS NOT NULL AND (
              {q(col)} <> TRIM({q(col)}) OR {q(col)} LIKE '%  %' OR {q(col)} LIKE '%' || chr(9) || '%'
           OR (length({q(col)}) > 3 AND {q(col)} = upper({q(col)}) AND regexp_matches({q(col)}, '[A-Z].*[A-Z]'))
           OR ({q(col)} = lower({q(col)}) AND regexp_matches({q(col)}, '[a-z]')))""")


def _contact_in_account(rule_id, table, assoc_col, acct_col, where="TRUE"):
    return Rule(rule_id, "CONSISTENCY", table, f"{table}.{assoc_col} is a contact of {table}.{acct_col}", f"""
        SELECT x.{q(PK[table])}, 'contact ' || x.{q(assoc_col)} || ' not at account ' || x.{q(acct_col)}
        FROM {q(table)} x
        WHERE {where} AND x.{q(assoc_col)} IS NOT NULL AND x.{q(acct_col)} IS NOT NULL
          AND x.{q(acct_col)} IN (SELECT Account_ID FROM Accounts)            -- missing company = orphan, not a mismatch
          AND x.{q(assoc_col)} IN (SELECT AssociateID FROM Associates)
          AND NOT EXISTS (SELECT 1 FROM AccountAssociates aa
                          WHERE aa.AssociateID = x.{q(assoc_col)} AND aa.AccountID = x.{q(acct_col)})""")


def _is_candidate(rule_id, table, col, where="TRUE"):
    return Rule(rule_id, "ROLE", table, f"{table}.{col} is a candidate (not a client contact)", f"""
        SELECT x.{q(PK[table])}, 'person ' || x.{q(col)} || ' is a client contact' FROM {q(table)} x
        WHERE {where} AND x.{q(col)} IN (SELECT Person_ID FROM Associates)
          AND x.{q(col)} NOT IN (SELECT person_id FROM edge_cases)""")


ACCOUNT_KEY = """regexp_replace(regexp_replace(
                   ' ' || lower(trim(Account_name)) || ' ',
                   '[.,]|\\(uk\\)| - london', '', 'g'),
                   ' (the|limited|ltd|plc|llp|group|and|&) ', ' ', 'g')"""


# candidate duplicate people: p2 is the later record of each pair (shared by dup.person / dup.associate)
PERSON_PAIRS = """Person p1 JOIN Person p2 ON p1.Person_ID < p2.Person_ID AND (
       (lower(p1.Last_Name) = lower(p2.Last_Name) AND p1.DOB = p2.DOB
        AND jaro_winkler_similarity(lower(p1.First_Name), lower(p2.First_Name)) >= 0.75)
    OR (lower(p1.First_Name) = lower(p2.First_Name) AND p1.DOB = p2.DOB
        AND damerau_levenshtein(lower(p1.Last_Name), lower(p2.Last_Name)) <= 2)
    OR (lower(p1.First_Name) = lower(p2.First_Name) AND lower(p1.Last_Name) = lower(p2.Last_Name)
        AND (p1.DOB IS NULL OR p2.DOB IS NULL OR (day(p1.DOB) = month(p2.DOB) AND month(p1.DOB) = day(p2.DOB)))))"""


RULES: list[Rule] = [
    *_key_rules(),
    _poly("TagEntity", "TagEntity_ID", "EntityType", "EntityID"),
    _poly("Log", "LogID", "Entity_Type", "Entity_ID"),

    # ── mandatory ────────────────────────────────────────────────────────────
    _blank("Person", "First_Name"), _blank("Person", "Last_Name"), _blank("Accounts", "Account_name"),
    _blank("Req", "Req_Title"), _blank("Addresses", "Address_line1"), _blank("Addresses", "City"),

    # ── formats ──────────────────────────────────────────────────────────────
    *[_regex(f"email.{t}.{c}", "INVALID_EMAIL", t, c, EMAIL_RE, f"{t}.{c} is a valid email")
      for t, c in [("Addresses", "Email"), ("Recruiter", "email"), ("Referees", "email"), ("Leads", "Email")]],
    _regex("postcode.Addresses", "INVALID_POSTCODE", "Addresses", "ZipCode", POSTCODE_RE, "UK postcode format"),
    _regex("ni.Emp_Profile", "INVALID_NI_NUMBER", "Emp_Profile", "NI_number", NI_RE, "National Insurance number format"),
    _regex("sortcode.Emp_Profile", "INVALID_SORT_CODE", "Emp_Profile", "SortCode", r"^[0-9]{2}-[0-9]{2}-[0-9]{2}$", "Sort code NN-NN-NN"),
    *[Rule(f"phone.{t}.{c}", "INVALID_PHONE", t, f"{t}.{c}: 10-13 digits, no text, no '+44 (0)', not dummy", f"""
        SELECT {q(PK[t])}, {q(c)} FROM {q(t)}
        WHERE NULLIF(TRIM({q(c)}), '') IS NOT NULL AND (
              NOT regexp_matches({q(c)}, '^\\+?[0-9 ]+$')
           OR length(regexp_replace({q(c)}, '[^0-9]', '', 'g')) NOT BETWEEN 10 AND 13
           OR NOT regexp_matches({q(c)}, '[1-9]'))""")
      for t, c in [("Addresses", "Phone"), ("Addresses", "OtherPhone"), ("Addresses", "WorkPhone"),
                   ("Referees", "Telephone"), ("Leads", "Phone")]],

    # ── coded values ─────────────────────────────────────────────────────────
    _domain("Req_Hired", "Pipeline_Stage", ["Applied", "Screening", "Interview", "Offer", "Placed", "Rejected"]),
    _domain("Req_Hired", "Worktype", ["Contract", "Permanent"]),
    _domain("Req", "Worktype", ["Contract", "Permanent"]),
    _domain("Req", "CurrencyCode", ["GBP"]), _domain("Req_Hired", "CurrencyCode", ["GBP"]),
    _domain("Invoice", "Currency", ["GBP"]), _domain("Invoice", "VAT", ["20%"]),
    _domain("Leads", "Lead_Source", ["LinkedIn", "Referral", "Website Form", "Cold Call", "Job Board", "Event"]),
    _domain("Leads", "Lead_Status", ["New", "Contacted", "Qualified", "Proposal Sent", "Won", "Lost"]),
    _domain("Req", "StatusText", ["Open", "Interviewing", "Offer Made", "Filled", "On Hold", "Cancelled"]),

    # ── hygiene ──────────────────────────────────────────────────────────────
    _name_hygiene("Accounts", "Account_name"), _name_hygiene("Person", "First_Name"), _name_hygiene("Person", "Last_Name"),
    Rule("hygiene.Addresses.ZipCode", "INVALID_POSTCODE", "Addresses", "Postcode has no leading/trailing spaces",
         "SELECT AddressID, '[' || ZipCode || ']' FROM Addresses WHERE ZipCode <> TRIM(ZipCode)"),

    # ── dates ────────────────────────────────────────────────────────────────
    Rule("dob.range", "SENTINEL_DATE", "Person", "DOB between 1940 and 16 years ago",
         "SELECT Person_ID, CAST(DOB AS VARCHAR) FROM Person WHERE DOB < DATE '1940-01-01' OR DOB > current_date - INTERVAL 16 YEAR"),
    Rule("req.start.placeholder", "SENTINEL_DATE", "Req", "Req.StartDate after 2000",
         "SELECT ReqID, CAST(StartDate AS VARCHAR) FROM Req WHERE StartDate < DATE '2000-01-01'"),
    Rule("placement.end_after_start", "DATE_LOGIC", "Req_Hired", "Placement EndDate >= StartDate",
         "SELECT Req_HiredID, CAST(StartDate AS VARCHAR) || ' > ' || CAST(EndDate AS VARCHAR) FROM Req_Hired WHERE EndDate < StartDate"),
    Rule("req.end_after_start", "DATE_LOGIC", "Req", "Job EndDate >= StartDate",
         "SELECT ReqID, CAST(EndDate AS VARCHAR) FROM Req WHERE EndDate < StartDate"),
    Rule("invoice.due_after_issue", "DATE_LOGIC", "Invoice", "Invoice DateDue >= InvoiceDate",
         "SELECT InvoiceID, CAST(DateDue AS VARCHAR) FROM Invoice WHERE DateDue < InvoiceDate"),
    *[Rule(f"created.not_future.{t}", "DATE_LOGIC", t, f"{t}.CreatedAt not in the future",
           f"SELECT {q(PK[t])}, CAST(CreatedAt AS VARCHAR) FROM {q(t)} WHERE CreatedAt > now()")
      for t in ("Req", "Accounts", "Person", "Req_Hired")],
    Rule("req.updated_after_created", "DATE_LOGIC", "Req", "Req UpdatedAt >= CreatedAt",
         "SELECT ReqID, CAST(CreatedAt AS VARCHAR) FROM Req WHERE UpdatedAt < CreatedAt"),
    Rule("placement.after_job_created", "DATE_LOGIC", "Req_Hired", "Placement starts on/after its job was raised",
         "SELECT h.Req_HiredID, CAST(h.StartDate AS VARCHAR) || ' < job created ' || CAST(r.CreatedAt AS VARCHAR) "
         "FROM Req_Hired h JOIN Req r ON r.ReqID = h.Req_ID WHERE CAST(h.StartDate AS DATE) < CAST(r.CreatedAt AS DATE)"),

    # ── ranges ───────────────────────────────────────────────────────────────
    Rule("rates.pay_positive", "OUT_OF_RANGE", "Req_Rates", "Payrate > 0",
         "SELECT Req_RateID, CAST(Payrate AS VARCHAR) FROM Req_Rates WHERE Payrate <= 0"),
    Rule("rates.margin", "OUT_OF_RANGE", "Req_Rates", "BillRate >= Payrate",
         "SELECT Req_RateID, CAST(BillRate AS VARCHAR) || ' < ' || CAST(Payrate AS VARCHAR) FROM Req_Rates WHERE BillRate < Payrate"),
    Rule("leads.score", "OUT_OF_RANGE", "Leads", "Lead_Score 1-5",
         "SELECT Lead_ID, CAST(Lead_Score AS VARCHAR) FROM Leads WHERE Lead_Score NOT BETWEEN 1 AND 5"),
    Rule("timesheet.hours", "OUT_OF_RANGE", "TimesheetItems", "TotalHours in (0, 24]",
         "SELECT ItemID, CAST(TotalHours AS VARCHAR) FROM TimesheetItems WHERE TotalHours <= 0 OR TotalHours > 24"),
    Rule("address.geo_uk", "OUT_OF_RANGE", "Addresses", "Lat/long inside the UK",
         "SELECT AddressID, CAST(Latitude AS VARCHAR) || ',' || CAST(Longitude AS VARCHAR) FROM Addresses "
         "WHERE Latitude NOT BETWEEN 49.8 AND 60.9 OR Longitude NOT BETWEEN -8.7 AND 1.8"),

    # ── encoding (all text columns) ──────────────────────────────────────────
    *[Rule(f"encoding.{t}.{c['col']}", "ENCODING", t, f"{t}.{c['col']} has no mojibake",
           f"SELECT {q(PK[t])}, left({q(c['col'])}, 60) FROM {q(t)} WHERE regexp_matches({q(c['col'])}, '{MOJIBAKE}')")
      for t, cs in SCHEMA.items() for c in cs if c["type"].startswith("NVARCHAR")],

    # ── soft deletes ─────────────────────────────────────────────────────────
    Rule("softdelete.account_open_jobs", "SOFT_DELETE_CONFLICT", "Accounts", "Deleted account has no open jobs",
         "SELECT a.Account_ID, 'open jobs' FROM Accounts a WHERE a.Deleted = 1 AND EXISTS (SELECT 1 FROM Req r "
         "WHERE r.AccountID = a.Account_ID AND r.Deleted = 0 AND r.StatusText IN ('Open','Interviewing','Offer Made'))"),
    Rule("softdelete.job_placements", "SOFT_DELETE_CONFLICT", "Req", "Deleted job has no live placements",
         "SELECT r.ReqID, 'live placements' FROM Req r WHERE r.Deleted = 1 AND EXISTS "
         "(SELECT 1 FROM Req_Hired h WHERE h.Req_ID = r.ReqID AND h.Deleted = 0)"),
    Rule("softdelete.person_active_contact", "SOFT_DELETE_CONFLICT", "Associates", "Deleted person is not an active contact",
         "SELECT s.AssociateID, 'person deleted' FROM Associates s JOIN Person p ON p.Person_ID = s.Person_ID "
         "WHERE p.Deleted = 1 AND s.Active = 1"),

    # ── duplicates ───────────────────────────────────────────────────────────
    Rule("dup.account", "DUPLICATE_ACCOUNT", "Accounts", "No two accounts share a normalised name or website", f"""
        WITH k AS (SELECT Account_ID, Website, regexp_replace({ACCOUNT_KEY}, '[^a-z0-9]', '', 'g') AS name_key
                   FROM Accounts WHERE NULLIF(TRIM(Account_name), '') IS NOT NULL)
        SELECT DISTINCT b.Account_ID, 'duplicate of ' || a.Account_ID FROM k a JOIN k b
          ON a.Account_ID < b.Account_ID AND (a.name_key = b.name_key OR a.Website = b.Website)"""),
    Rule("dup.account.split_history", "SPLIT_HISTORY", "Req", "Job does not sit on a duplicate account", f"""
        WITH k AS (SELECT Account_ID, Website, regexp_replace({ACCOUNT_KEY}, '[^a-z0-9]', '', 'g') AS name_key
                   FROM Accounts WHERE NULLIF(TRIM(Account_name), '') IS NOT NULL),
             d AS (SELECT DISTINCT b.Account_ID FROM k a JOIN k b
                   ON a.Account_ID < b.Account_ID AND (a.name_key = b.name_key OR a.Website = b.Website))
        SELECT ReqID, 'on duplicate account ' || AccountID FROM Req WHERE AccountID IN (SELECT Account_ID FROM d)"""),
    Rule("dup.person", "DUPLICATE_PERSON", "Person", "No near-duplicate people (nickname/typo/DOB swap/missing DOB)",
         f"SELECT DISTINCT p2.Person_ID, 'duplicate of ' || p1.Person_ID FROM {PERSON_PAIRS}"),
    Rule("dup.associate", "DUPLICATE_ASSOCIATE", "Associates", "No contact whose person duplicates another contact's person",
         f"""SELECT DISTINCT a2.AssociateID, 'duplicate of contact ' || a1.AssociateID FROM {PERSON_PAIRS}
             JOIN Associates a1 ON a1.Person_ID = p1.Person_ID JOIN Associates a2 ON a2.Person_ID = p2.Person_ID"""),
    Rule("dup.timesheet_line", "DUPLICATE_TRANSACTION", "TimesheetItems", "No timesheet line entered twice", """
        SELECT ItemID, 'copy of ' || first_id FROM (
            SELECT ItemID, min(ItemID) OVER w AS first_id, row_number() OVER (w ORDER BY ItemID) AS rn FROM TimesheetItems
            WINDOW w AS (PARTITION BY Timesheet_ID, Timesheet_TypeID, Person_ID, Req_ID,
                         StartTime, EndTime, TotalHours, CreatedAt)) WHERE rn > 1"""),
    Rule("dup.job", "DUPLICATE_JOB", "Req", "No job raised twice (same client, title, type and start date)", """
        SELECT ReqID, 'copy of job ' || first_id FROM (
            SELECT ReqID, min(ReqID) OVER w AS first_id, row_number() OVER (w ORDER BY ReqID) AS rn FROM Req
            WINDOW w AS (PARTITION BY AccountID, lower(trim(Req_Title)), Worktype, CAST(StartDate AS DATE))) WHERE rn > 1"""),

    # ── orphans: records linked to nothing ───────────────────────────────────
    Rule("orphan.contact", "ORPHAN_CONTACT", "Associates", "Every contact is linked to a company", """
        SELECT s.AssociateID, 'contact linked to no company' FROM Associates s
        WHERE NOT EXISTS (SELECT 1 FROM AccountAssociates aa JOIN Accounts a ON a.Account_ID = aa.AccountID
                          WHERE aa.AssociateID = s.AssociateID)"""),
    Rule("orphan.candidate", "ORPHAN_CANDIDATE", "Person", "Every candidate is linked to a job (application or placement)", """
        SELECT p.Person_ID, 'candidate linked to no job' FROM Person p
        WHERE p.Person_ID NOT IN (SELECT Person_ID FROM Associates WHERE Person_ID IS NOT NULL)
          AND NOT EXISTS (SELECT 1 FROM Req_Hired h JOIN Req r ON r.ReqID = h.Req_ID WHERE h.Invoiced_PersonID = p.Person_ID)"""),
    Rule("orphan.document", "ORPHAN_DOCUMENT", "Documents", "Every document is linked to a record", """
        SELECT d.Doc_ID, coalesce(d.ObjectType, '?') || ' ' || coalesce(CAST(d.Doc_AssocID AS VARCHAR), 'no id') FROM Documents d
        WHERE (d.Doc_AssocID IS NULL OR d.ObjectType IS NULL OR NOT (
               (d.ObjectType = 'Associate' AND d.Doc_AssocID IN (SELECT AssociateID FROM Associates))
            OR (d.ObjectType = 'Req'       AND d.Doc_AssocID IN (SELECT ReqID FROM Req))
            OR (d.ObjectType = 'Account'   AND d.Doc_AssocID IN (SELECT Account_ID FROM Accounts))
            OR (d.ObjectType = 'Person'    AND d.Doc_AssocID IN (SELECT Person_ID FROM Person))))
          AND d.Doc_ID NOT IN (SELECT Document_ID FROM Req_Documents WHERE Document_ID IS NOT NULL)
          AND d.Doc_ID NOT IN (SELECT Document_ID FROM Emp_Documents WHERE Document_ID IS NOT NULL)
          AND d.Doc_ID NOT IN (SELECT Document_ID FROM RecruiterDocuments WHERE Document_ID IS NOT NULL)
          AND d.Doc_ID NOT IN (SELECT Doc_ID FROM BackgroundChecks WHERE Doc_ID IS NOT NULL)
          AND d.Doc_ID NOT IN (SELECT Document_ID FROM Leads WHERE Document_ID IS NOT NULL)
          AND d.Doc_ID NOT IN (SELECT Document_ID FROM Invoice WHERE Document_ID IS NOT NULL)"""),
    Rule("orphan.cv", "ORPHAN_DOCUMENT", "CV_Docs", "Every CV is linked to a person",
         "SELECT Doc_ID, 'CV linked to no person' FROM CV_Docs WHERE CV_AssocID IS NULL OR CV_AssocID NOT IN (SELECT Person_ID FROM Person)"),
    Rule("orphan.note", "ORPHAN_NOTE", "Notes", "Every note is linked to a record", """
        SELECT n.Note_ID, coalesce(n.ObjectType, '?') || ' ' || coalesce(CAST(n.ObjectId AS VARCHAR), 'no id') FROM Notes n
        WHERE (n.ObjectId IS NULL OR n.ObjectType IS NULL OR NOT (
               (n.ObjectType = 'Associate' AND n.ObjectId IN (SELECT AssociateID FROM Associates))
            OR (n.ObjectType = 'Req'       AND n.ObjectId IN (SELECT ReqID FROM Req))
            OR (n.ObjectType = 'Account'   AND n.ObjectId IN (SELECT Account_ID FROM Accounts))
            OR (n.ObjectType = 'Person'    AND n.ObjectId IN (SELECT Person_ID FROM Person))))"""),

    # ── roles & consistency ──────────────────────────────────────────────────
    Rule("contact.title_gender", "CONSISTENCY", "Associates", "Title matches the first name's gender", """
        SELECT s.AssociateID, s.AssociateTitle || ' ' || p.First_Name FROM Associates s
        JOIN Person p ON p.Person_ID = s.Person_ID JOIN first_name_gender g ON g.first_name = p.First_Name
        WHERE (g.gender = 'M' AND s.AssociateTitle IN ('Ms','Mrs','Miss')) OR (g.gender = 'F' AND s.AssociateTitle = 'Mr')"""),
    Rule("contact.office_address", "CONSISTENCY", "Associates", "Contact's address is their account's office", """
        SELECT s.AssociateID, 'address ' || s.Associate_AddressID FROM Associates s
        WHERE NOT EXISTS (SELECT 1 FROM AccountAssociates aa JOIN Accounts a ON a.Account_ID = aa.AccountID
                          WHERE aa.AssociateID = s.AssociateID AND a.AddressID = s.Associate_AddressID)
          -- the company's office must exist; a company pointing at a missing address is an orphan
          AND EXISTS (SELECT 1 FROM AccountAssociates aa JOIN Accounts a ON a.Account_ID = aa.AccountID
                      JOIN Addresses ad ON ad.AddressID = a.AddressID WHERE aa.AssociateID = s.AssociateID)"""),
    Rule("account.email_domain", "CONSISTENCY", "Addresses", "Office email uses the account's website domain", f"""
        SELECT ad.AddressID, ad.Email || ' vs ' || a.Website FROM Accounts a JOIN Addresses ad ON ad.AddressID = a.AddressID
        WHERE a.Website IS NOT NULL AND ad.Email LIKE '%@%'
          AND regexp_matches(ad.Email, '{EMAIL_RE.replace(chr(39), chr(39) * 2)}')   -- malformed emails: reported as invalid emails
          AND lower(split_part(ad.Email, '@', 2)) <> lower(regexp_extract(a.Website, '^(https?://)?(www\\.)?([^/]+)', 3))"""),
    Rule("contact.type", "CONSISTENCY", "Associates", "Contact has exactly one 'Contact' type row", """
        SELECT s.AssociateID, CAST(COUNT(r.TypeID) AS VARCHAR) FROM Associates s
        LEFT JOIN AssociateTypeRelation r ON r.AssociateID = s.AssociateID
             AND r.TypeID = (SELECT Associate_TypeID FROM AssociateTypes WHERE TypeName = 'Contact')
        GROUP BY s.AssociateID HAVING COUNT(r.TypeID) <> 1"""),
    Rule("contact.type_unique", "CONSISTENCY", "AssociateTypeRelation", "No duplicate (associate, type) rows",
         "SELECT MAX(AssociateRelationID), 'dup' FROM AssociateTypeRelation GROUP BY AssociateID, TypeID HAVING COUNT(*) > 1"),
    _contact_in_account("contact.on_job", "Req", "AssociateID", "AccountID"),
    _contact_in_account("contact.on_placement", "Req_Hired", "Associate_ID", "Account_ID"),
    _contact_in_account("contact.on_lead", "Leads", "Associate_ID", "Account_ID"),
    Rule("contact.on_meeting", "CONSISTENCY", "Schedule", "Contact meeting is with a contact of that account", """
        SELECT sc.Schedule_ID, 'person ' || sc.Person_ID FROM Schedule sc WHERE sc.Person_Type = 'Contact'
          AND sc.Account_ID IN (SELECT Account_ID FROM Accounts)
          AND NOT EXISTS (SELECT 1 FROM Associates s JOIN AccountAssociates aa ON aa.AssociateID = s.AssociateID
                          WHERE s.Person_ID = sc.Person_ID AND aa.AccountID = sc.Account_ID)"""),
    Rule("job.account_matches", "CONSISTENCY", "Req_Hired", "Placement account = its job's account",
         "SELECT h.Req_HiredID, h.Account_ID || ' vs ' || r.AccountID FROM Req_Hired h JOIN Req r ON r.ReqID = h.Req_ID WHERE h.Account_ID <> r.AccountID "
         "AND h.Account_ID IN (SELECT Account_ID FROM Accounts) AND r.AccountID IN (SELECT Account_ID FROM Accounts)"),
    Rule("meeting.job_account", "CONSISTENCY", "Schedule", "Meeting's job belongs to the meeting's account",
         "SELECT s.Schedule_ID, s.Account_ID || ' vs ' || r.AccountID FROM Schedule s JOIN Req r ON r.ReqID = s.Req_ID WHERE s.Account_ID <> r.AccountID "
         "AND s.Account_ID IN (SELECT Account_ID FROM Accounts) AND r.AccountID IN (SELECT Account_ID FROM Accounts)"),
    _is_candidate("role.emp_profile", "Emp_Profile", "Person_ID"),
    _is_candidate("role.cv", "CV_Docs", "CV_AssocID"),
    _is_candidate("role.background_check", "BackgroundChecks", "Person_ID"),
    _is_candidate("role.hotlist", "ObjectHotlist", "Person_ID"),
    _is_candidate("role.interviewee", "Interview_Feedback", "Interviewee_ID"),
    _is_candidate("role.placed_person", "Req_Hired", "Invoiced_PersonID"),
    _is_candidate("role.candidate_meeting", "Schedule", "Person_ID", "x.Person_Type = 'Candidate'"),
    *[Rule(f"role.interviewer.{c}", "ROLE", "Interview_Feedback", f"Interview_Feedback.{c} is a client contact",
           f"SELECT Interview_FeedbackID, 'person ' || {c} FROM Interview_Feedback "
           f"WHERE {c} IS NOT NULL AND {c} NOT IN (SELECT Person_ID FROM Associates)")
      for c in ("Interviewer_ID", "Second_InterviewerID", "Other_InterviewerID")],
    Rule("role.placement_has_candidate", "ROLE", "Req_Hired", "Every pipeline row names a candidate",
         "SELECT Req_HiredID, 'no candidate' FROM Req_Hired WHERE Invoiced_PersonID IS NULL"),
    Rule("role.one_profile_per_person", "ROLE", "Emp_Profile", "One employee profile per person",
         "SELECT MAX(Emp_ProfileID), 'person ' || Person_ID FROM Emp_Profile GROUP BY Person_ID HAVING COUNT(*) > 1"),
    Rule("role.person_flags", "ROLE", "Person", "Person.Associate / Person.Emp flags match their records", """
        SELECT p.Person_ID, 'Associate=' || p.Associate || ' Emp=' || p.Emp FROM Person p
        WHERE p.Associate <> CASE WHEN p.Person_ID IN (SELECT Person_ID FROM Associates) THEN 1 ELSE 0 END
           OR p.Emp <> CASE WHEN p.Person_ID IN (SELECT Person_ID FROM Emp_Profile) THEN 1 ELSE 0 END"""),
    Rule("timesheet.placed_contractor", "CONSISTENCY", "TimesheetItems", "Timesheet line belongs to a contractor placed on that job", """
        SELECT t.ItemID, 'person ' || t.Person_ID || ' job ' || t.Req_ID FROM TimesheetItems t
        WHERE NOT EXISTS (SELECT 1 FROM Req_Hired h WHERE h.Req_ID = t.Req_ID AND h.Invoiced_PersonID = t.Person_ID
                          AND h.Pipeline_Stage = 'Placed' AND h.Worktype = 'Contract')"""),

    # ── timesheets ───────────────────────────────────────────────────────────
    Rule("timesheet.week_shape", "DATE_LOGIC", "TimeSheets", "Timesheet covers one Monday-Sunday week",
         "SELECT ID, CAST(StartDate AS VARCHAR) || '..' || CAST(Enddate AS VARCHAR) FROM TimeSheets "
         "WHERE isodow(StartDate) <> 1 OR date_diff('day', StartDate, Enddate) <> 6"),
    Rule("timesheet.not_future", "DATE_LOGIC", "TimeSheets", "Timesheet week is not in the future",
         "SELECT ID, CAST(StartDate AS VARCHAR) FROM TimeSheets WHERE StartDate > current_date"),
    Rule("timesheet.one_job_one_person", "CONSISTENCY", "TimeSheets", "All lines of a timesheet are for one contractor and one job",
         "SELECT Timesheet_ID, 'mixed lines' FROM TimesheetItems GROUP BY Timesheet_ID "
         "HAVING COUNT(DISTINCT Person_ID) > 1 OR COUNT(DISTINCT Req_ID) > 1"),
    Rule("timesheet.within_placement", "DATE_LOGIC", "TimeSheets", "Timesheet week falls inside the contractor's placement", """
        SELECT DISTINCT t.ID, CAST(t.StartDate AS VARCHAR) || ' not in ' || CAST(CAST(h.StartDate AS DATE) AS VARCHAR)
               || '..' || CAST(CAST(h.EndDate AS DATE) AS VARCHAR)
        FROM TimeSheets t JOIN TimesheetItems i ON i.Timesheet_ID = t.ID
        JOIN Req_Hired h ON h.Req_ID = i.Req_ID AND h.Invoiced_PersonID = i.Person_ID
             AND h.Pipeline_Stage = 'Placed' AND h.Worktype = 'Contract'
        WHERE t.StartDate < CAST(h.StartDate AS DATE) OR t.Enddate > CAST(h.EndDate AS DATE)"""),
    Rule("timesheet.no_repeat_week", "DUPLICATE_TRANSACTION", "TimeSheets", "No contractor has two timesheets of the same type for the same week", """
        SELECT MAX(t.ID), 'repeat week ' || CAST(t.StartDate AS VARCHAR) FROM TimeSheets t
        JOIN (SELECT DISTINCT Timesheet_ID, Person_ID, Req_ID FROM TimesheetItems) i ON i.Timesheet_ID = t.ID
        GROUP BY i.Person_ID, i.Req_ID, t.StartDate, t.Timesheet_TypeID HAVING COUNT(*) > 1"""),
    Rule("timesheet.line_type", "CONSISTENCY", "TimesheetItems", "Line type = its timesheet's type",
         "SELECT i.ItemID, i.Timesheet_TypeID || ' vs ' || t.Timesheet_TypeID FROM TimesheetItems i "
         "JOIN TimeSheets t ON t.ID = i.Timesheet_ID WHERE i.Timesheet_TypeID <> t.Timesheet_TypeID"),
    Rule("timesheet.line_hours", "CONSISTENCY", "TimesheetItems", "TotalHours = clock span minus 30-min break (shifts >= 6h)", """
        SELECT ItemID, CAST(TotalHours AS VARCHAR) || 'h for ' || CAST(StartTime AS VARCHAR) || '-' || CAST(EndTime AS VARCHAR)
        FROM TimesheetItems, LATERAL (SELECT date_diff('minute', StartTime, EndTime) / 60.0 AS span)
        WHERE abs(TotalHours - (span - CASE WHEN span >= 6 THEN 0.5 ELSE 0 END)) > 0.01"""),
    Rule("timesheet.line_submitted_in_week", "DATE_LOGIC", "TimesheetItems", "Line submitted at the end of its timesheet week",
         "SELECT i.ItemID, CAST(i.CreatedAt AS VARCHAR) FROM TimesheetItems i JOIN TimeSheets t ON t.ID = i.Timesheet_ID "
         "WHERE CAST(i.CreatedAt AS DATE) < t.StartDate OR CAST(i.CreatedAt AS DATE) > t.Enddate + INTERVAL 7 DAY"),
    Rule("timesheet.approval", "CONSISTENCY", "TimeSheets", "Approved <=> approval date + approver; approved after the week ends", """
        SELECT ID, Status FROM TimeSheets
        WHERE (Status = 'Approved' AND (Approved_Date IS NULL OR Approved_By IS NULL OR CAST(Approved_Date AS DATE) <= Enddate))
           OR (Status <> 'Approved' AND (Approved_Date IS NOT NULL OR Approved_By IS NOT NULL))"""),
    Rule("timesheet.po_is_jobs", "FINANCE", "TimeSheets", "Timesheet PO funds the job worked on", """
        SELECT DISTINCT t.ID, t.PONo FROM TimeSheets t JOIN TimesheetItems i ON i.Timesheet_ID = t.ID
        JOIN PONo p ON p.PONo = t.PONo WHERE p.ReqID <> i.Req_ID"""),
    Rule("timesheet.rates_from_job", "FINANCE", "TimeSheets", "Hourly rates = job day rate / 7.5 x type multiplier (0 bill if non-billable)", """
        SELECT DISTINCT t.ID, CAST(t.Payrate AS VARCHAR) || '/' || CAST(t.Billrate AS VARCHAR)
        FROM TimeSheets t JOIN TimesheetType ty ON ty.Timesheet_TypeID = t.Timesheet_TypeID
        JOIN TimesheetItems i ON i.Timesheet_ID = t.ID JOIN Req_Rates r ON r.Req_ID = i.Req_ID,
        LATERAL (SELECT CASE t.Timesheet_TypeID WHEN 2 THEN 1.5 WHEN 4 THEN 0 WHEN 5 THEN 0 ELSE 1 END AS m)
        WHERE abs(t.Payrate - round(r.Payrate / 7.5 * m, 2)) > 0.01
           OR abs(t.Billrate - CASE WHEN ty.Billable = 1 THEN round(r.BillRate / 7.5 * m, 2) ELSE 0 END) > 0.01"""),

    # ── finance ──────────────────────────────────────────────────────────────
    Rule("invoice.line_amount", "FINANCE", "InvoiceEntries", "Line amount = quantity x unit price",
         "SELECT Invoice_EntryID, CAST(Amount AS VARCHAR) FROM InvoiceEntries WHERE abs(Amount - round(Quantity * Unit_Price, 2)) > 0.01"),
    Rule("invoice.net_is_sum_of_lines", "FINANCE", "Invoice", "NET = SubTotal = sum of lines", """
        SELECT i.InvoiceID, CAST(i.NETAmount AS VARCHAR) || ' vs ' || CAST(l.s AS VARCHAR) FROM Invoice i
        JOIN (SELECT Invoice_ID, SUM(Amount) s FROM InvoiceEntries GROUP BY Invoice_ID) l ON l.Invoice_ID = i.InvoiceID
        WHERE abs(i.NETAmount - l.s) > 0.01 OR abs(i.SubTotal_Amount - i.NETAmount) > 0.01"""),
    Rule("invoice.gross_is_net_plus_vat", "FINANCE", "Invoice", "Amount = NET + 20% VAT",
         "SELECT InvoiceID, CAST(Amount AS VARCHAR) FROM Invoice WHERE abs(Amount - round(NETAmount * 1.2, 2)) > 0.01"),
    Rule("invoice.balance", "FINANCE", "Invoice", "Paid <= Amount and Balance = Amount - Paid (0 if cancelled)", """
        SELECT InvoiceID, Status FROM Invoice
        WHERE Amount_Paid > Amount + 0.01
           OR (Status <> 'Cancelled' AND abs(Balance_Due - (Amount - Amount_Paid)) > 0.01)
           OR (Status = 'Cancelled' AND (Balance_Due <> 0 OR Amount_Paid <> 0))
           OR (Status = 'Paid' AND abs(Amount_Paid - Amount) > 0.01)"""),
    Rule("invoice.po_vendor", "FINANCE", "Invoice", "Invoice's PO belongs to the invoiced client",
         "SELECT i.InvoiceID, i.PONo FROM Invoice i JOIN PONo p ON p.PONo = i.PONo WHERE p.VendorID <> i.Vendor_ID"),
    Rule("po.job_client", "FINANCE", "PONo", "PO client = the client of the job it funds",
         "SELECT p.PONo, p.VendorID || ' vs ' || r.AccountID FROM PONo p JOIN Req r ON r.ReqID = p.ReqID WHERE p.VendorID <> r.AccountID "
         "AND p.VendorID IN (SELECT Account_ID FROM Accounts) AND r.AccountID IN (SELECT Account_ID FROM Accounts)"),
    Rule("invoice.line_placement_client", "FINANCE", "InvoiceEntries", "Invoice line's placement is with the invoiced client", """
        SELECT e.Invoice_EntryID, 'placement ' || e.Plac_ID FROM InvoiceEntries e
        JOIN Invoice i ON i.InvoiceID = e.Invoice_ID JOIN Req_Hired h ON h.Req_HiredID = e.Plac_ID
        WHERE h.Account_ID <> i.Vendor_ID AND h.Account_ID IN (SELECT Account_ID FROM Accounts) AND i.Vendor_ID IN (SELECT Account_ID FROM Accounts)"""),
]
