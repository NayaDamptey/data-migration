"""
sample_data/inject_defects.py

Makes the clean source data look like a real 10-year-old legacy CRM by
planting known data-quality defects in the SQL Server source database.

The CSVs in sample_data/source/ stay clean (the baseline). Defects are only
applied in SQL, by:
    sql/source/04_inject_legacy_defects.sql
and every single one is recorded in the answer key:
    sql/source/defect_manifest.csv      (one row per planted defect)
    docs/source_defects.md              (summary by category)

The profiling script should be judged by how many manifest rows it finds.
Output is deterministic (fixed seed), so the answer key never drifts.

Run directly (only generates files):      python sample_data/inject_defects.py
Normally invoked by:                      python sample_data/build_source_db.py --load
"""

from __future__ import annotations

import csv
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from build_source_db import ROOT, SQL_DIR, fk_name, load_schema, q, read_csv, sql_str, to_sql_literal, parse_d
from relationships import all_foreign_keys

SEED = 1337

CATEGORY_INFO = {
    "ORPHAN_FK":            "Foreign key value with no parent row (the FK constraint was disabled, as in a forced legacy import)",
    "MISSING_REQUIRED":     "Business-mandatory field is NULL, empty or whitespace",
    "INVALID_EMAIL":        "Email address is malformed or a placeholder",
    "INVALID_POSTCODE":     "UK postcode is malformed, placeholder or non-standard",
    "INVALID_PHONE":        "Phone number is free text, too short or a dummy value",
    "INVALID_NI_NUMBER":    "National Insurance number fails the UK format",
    "INVALID_SORT_CODE":    "Bank sort code not in NN-NN-NN format",
    "NON_STANDARD_DOMAIN":  "Coded value outside the expected list (case, spelling, synonyms)",
    "WHITESPACE_CASE":      "Leading/trailing/double spaces or inconsistent casing",
    "SENTINEL_DATE":        "Placeholder or impossible date (1900-01-01, future DOB)",
    "DATE_LOGIC":           "Dates in the wrong order or in the future",
    "OUT_OF_RANGE":         "Numeric value outside its plausible range",
    "ENCODING":             "Mojibake from a past UTF-8 / Windows-1252 conversion",
    "SOFT_DELETE_CONFLICT": "Record soft-deleted while still referenced by live records",
    "DUPLICATE_ACCOUNT":    "Near-duplicate client account (new row, name variant)",
    "DUPLICATE_PERSON":     "Near-duplicate person (new row, nickname/typo/DOB swap)",
    "DUPLICATE_ASSOCIATE":  "Duplicate contact record pointing at a duplicate person",
    "DUPLICATE_TRANSACTION":"Same timesheet line entered twice under a new ID",
    "SPLIT_HISTORY":        "Child rows re-pointed to the duplicate, splitting history across both records",
    "DUPLICATE_JOB":        "Same job raised twice under a new ID",
    "ORPHAN_CONTACT":       "Contact linked to no company",
    "PLACEMENT_ON_DELETED": "Live placement on a soft-deleted job or company",
    "ORPHAN_DOCUMENT":      "Document linked to no record",
    "ORPHAN_NOTE":          "Note linked to no record",
}

NICKNAMES = {"James": "Jim", "Robert": "Bob", "William": "Bill", "Elizabeth": "Liz", "Michael": "Mike",
             "Thomas": "Tom", "Daniel": "Dan", "Katherine": "Kate", "Catherine": "Cathy",
             "Christopher": "Chris", "Jonathan": "Jon", "Samuel": "Sam", "Alexander": "Alex",
             "Rebecca": "Becky", "Benjamin": "Ben", "Mohammed": "Mohammad", "Muhammad": "Mohammed",
             "Margaret": "Maggie", "Richard": "Rick", "Joseph": "Joe", "Matthew": "Matt",
             "Andrew": "Andy", "Jennifer": "Jen", "Nicholas": "Nick", "Victoria": "Vicky",
             "Stephen": "Steve", "Edward": "Ed", "Patricia": "Trish", "Susan": "Sue", "David": "Dave"}


class Injector:
    def __init__(self, schema: dict):
        self.schema = schema
        self.types = {t: {c["col"]: c["type"] for c in cols} for t, cols in schema.items()}
        self.pk = {t: next(c["col"] for c in cols if c["key"].lower() == "primary key")
                   for t, cols in schema.items()}
        self.rng = random.Random(SEED)
        self.data = {}
        self.inserts: list[str] = []
        self.updates: list[str] = []
        self.manifest: list[dict] = []
        self.used: set[tuple] = set()
        self.inserted = Counter()
        self.disabled_fks: list[tuple] = []
        self._next: dict[str, int] = {}

    # ── helpers ───────────────────────────────────────────────────────────────
    def rows(self, table):
        if table not in self.data:
            self.data[table] = read_csv(table)
        return self.data[table]

    def pick(self, table, col, n, pred=lambda r: True):
        pool = [r for r in self.rows(table)
                if (table, r[self.pk[table]], col) not in self.used and pred(r)]
        chosen = self.rng.sample(pool, min(n, len(pool)))
        for r in chosen:
            self.used.add((table, r[self.pk[table]], col))
        return chosen

    def lit(self, table, col, value):
        if value is None:
            return "NULL"
        if value == "" or (isinstance(value, str) and value.strip() == "" and self.types[table][col].startswith("NVARCHAR")):
            return sql_str(value)
        lit, why = to_sql_literal(str(value), self.types[table][col])
        if why:
            raise ValueError(f"{table}.{col}={value!r}: {why}")
        return lit

    def record(self, category, table, pk, col, original, injected, detail=""):
        self.manifest.append({
            "defect_id": f"D{len(self.manifest) + 1:04d}", "category": category, "table": table,
            "pk_column": self.pk[table], "pk_value": pk, "column": col,
            "original_value": "" if original is None else original,
            "injected_value": "NULL" if injected is None else injected, "detail": detail})

    def set(self, category, table, row, col, value, detail=""):
        pkc = self.pk[table]
        if value is not None and str(value) == (row.get(col) or ""):
            raise ValueError(f"no-op defect {category} on {table}.{col} pk={row[pkc]}: value unchanged ({value!r})")
        self.updates.append(f"UPDATE dbo.{q(table)} SET {q(col)} = {self.lit(table, col, value)} "
                            f"WHERE {q(pkc)} = {self.lit(table, pkc, row[pkc])};")
        self.record(category, table, row[pkc], col, row.get(col), value, detail)

    def copy_row(self, category, table, src_pk, overrides: dict, detail="", record: bool = True):
        pkc = self.pk[table]
        cols = [c["col"] for c in self.schema[table]]
        select = ", ".join(self.lit(table, c, overrides[c]) if c in overrides else q(c) for c in cols)
        self.inserts.append(f"INSERT INTO dbo.{q(table)} ({', '.join(map(q, cols))}) "
                            f"SELECT {select} FROM dbo.{q(table)} WHERE {q(pkc)} = {self.lit(table, pkc, src_pk)};")
        self.inserted[table] += 1
        if record:
            changed = {k: v for k, v in overrides.items() if k != pkc}
            self.record(category, table, overrides[pkc], "*", f"copy of {pkc}={src_pk}",
                        "; ".join(f"{k}={v}" for k, v in changed.items()), detail)

    def raw_set(self, table, row, col, value):
        """An update that is part of another planted defect (keeps it consistent); not in the manifest."""
        pkc = self.pk[table]
        self.updates.append(f"UPDATE dbo.{q(table)} SET {q(col)} = {self.lit(table, col, value)} "
                            f"WHERE {q(pkc)} = {self.lit(table, pkc, row[pkc])};")

    def alloc(self, table, floor: int = 0) -> int:
        """Next free id for an inserted row (never collides with other inserted rows)."""
        base = self.next_id(table) if table in self.pk else 0
        nxt = max(self._next.get(table, 0), base, floor)
        self._next[table] = nxt + 1
        return nxt

    def contact_helpers(self, src_assoc: str, new_assoc, with_company: bool = True):
        """A new contact row is linked to the same company and typed 'Contact', like the one it copies."""
        for aa in self.rows("AccountAssociates") if with_company else []:
            if aa["AssociateID"] == src_assoc:
                self.copy_row("", "AccountAssociates", aa["AccountAssociateID"],
                              {"AccountAssociateID": self.alloc("AccountAssociates"), "AssociateID": new_assoc}, record=False)
                break
        for tr in self.rows("AssociateTypeRelation"):
            if tr["AssociateID"] == src_assoc:
                self.copy_row("", "AssociateTypeRelation", tr["AssociateRelationID"],
                              {"AssociateRelationID": self.alloc("AssociateTypeRelation"), "AssociateID": new_assoc}, record=False)

    def next_id(self, table, start=None):
        ids = [int(r[self.pk[table]]) for r in self.rows(table) if r[self.pk[table]].isdigit()]
        return max(ids + [start or 0]) + 1

    # ── defect families ───────────────────────────────────────────────────────
    def orphans(self):
        # (table, column, how many, how): "insert" = a NEW record pointing at nothing (re-pointing a real record
        # would strip its links and break unrelated rules); "update" = an existing record loses its parent id
        specs = [("Req_Hired", "Account_ID", 5, "insert"), ("Req_Hired", "Req_ID", 4, "insert"),
                 ("Req", "AccountID", 4, "update"), ("Associates", "Person_ID", 5, "insert"),
                 ("Accounts", "AddressID", 4, "update"), ("TimesheetItems", "Timesheet_ID", 5, "insert"),
                 ("InvoiceEntries", "Invoice_ID", 4, "insert"), ("Emp_Profile", "Person_ID", 3, "insert"),
                 ("Notes", "ObjectId", 3, "update")]
        fk_cols = {(c, cc) for c, cc, _, _ in all_foreign_keys(self.schema)}
        for table, col, n, how in specs:
            if (table, col) in fk_cols:   # Notes.ObjectId is polymorphic -> no FK to disable
                self.disabled_fks.append((table, col))
            pkc = self.pk[table]
            for r in self.pick(table, col, n, lambda r, c=col: r[c] != ""):
                bad = 90000 + self.rng.randint(1, 9999)
                if how == "update":
                    self.set("ORPHAN_FK", table, r, col, bad, f"{col} points at a non-existent parent")
                    continue
                new = self.alloc(table)
                ov = {pkc: str(new) if table == "Associates" else new, col: bad}
                if table == "Emp_Profile":
                    ov["Emp_No"] = self.alloc("Emp_Profile.Emp_No", floor=5001)
                self.copy_row("ORPHAN_FK", table, r[pkc], ov, f"new {table} row whose {col} points at a non-existent parent")
                if table == "Associates":
                    self.contact_helpers(r["AssociateID"], str(new))

    def missing(self):
        for r in self.pick("Person", "Last_Name", 6):
            self.set("MISSING_REQUIRED", "Person", r, "Last_Name", None)
        for r in self.pick("Accounts", "Account_name", 3):
            self.set("MISSING_REQUIRED", "Accounts", r, "Account_name", "")
        for r in self.pick("Req", "Req_Title", 4):
            self.set("MISSING_REQUIRED", "Req", r, "Req_Title", None)
        for r in self.pick("Addresses", "Address_line1", 3):
            self.set("MISSING_REQUIRED", "Addresses", r, "Address_line1", "   ")

    def emails(self):
        def corrupt(e: str, k: int) -> str:
            local, _, domain = e.partition("@")
            spaced = local.replace(".", " ") if "." in local else f"{local[:1]} {local[1:]}"
            return [f"{local}@@{domain}", f"{local}.{domain}", f"{spaced}@{domain}",
                    f"{local}@{domain.split('.')[0]}", "n/a", f"{e}.", f"{local}@{domain},{local}@gmail.com",
                    "unknown"][k % 8]
        for table, col, n in [("Addresses", "Email", 8), ("Recruiter", "email", 2),
                              ("Referees", "email", 6), ("Leads", "Email", 6)]:
            limit = re.search(r"\((\d+)\)", self.types[table][col])
            limit = int(limit.group(1)) if limit else 10_000
            for i, r in enumerate(self.pick(table, col, n, lambda r, c=col: "@" in r[c])):
                k = i + self.rng.randint(0, 7)
                # take the first corruption that still fits the column (a legacy DB could not store a longer one)
                bad = next(v for v in (corrupt(r[col], k + j) for j in range(8)) if len(v) <= limit)
                self.set("INVALID_EMAIL", table, r, col, bad)

    def postcodes(self):
        def corrupt(p: str, k: int):
            return [(p.lower().replace(" ", ""), "lowercase, no space"), ("TBC", "placeholder"),
                    (p.replace(" ", ""), "missing space"), (p + " UK", "trailing text"),
                    ("12345", "non-UK format"), (p.replace("0", "O", 1) if "0" in p else p[::-1], "O/0 or garbled"),
                    (" " + p + " ", "padded")][k % 7]
        for i, r in enumerate(self.pick("Addresses", "ZipCode", 12, lambda r: " " in r["ZipCode"])):
            v, why = corrupt(r["ZipCode"], i)
            self.set("INVALID_POSTCODE", "Addresses", r, "ZipCode", v, why)

    def phones(self):
        bad = ["ask for reception", "0207", "00000000000", "+44 (0) 20 7946 0000", "07700900123 ext 4",
               "TBC", "+44 7911 1234567890", "see email"]
        for i, r in enumerate(self.pick("Addresses", "Phone", 8, lambda r: r["Phone"] != "")):
            self.set("INVALID_PHONE", "Addresses", r, "Phone", bad[i])
        for i, r in enumerate(self.pick("Referees", "Telephone", 4)):
            self.set("INVALID_PHONE", "Referees", r, "Telephone", bad[(i + 3) % len(bad)])

    def ni_and_bank(self):
        def ni(v, k):
            return [v[:-1], " ".join([v[:2], v[2:4], v[4:6], v[6:8], v[8:]]), "TBC",
                    "123456789", v.lower(), "QQ123456C"][k % 6]
        for i, r in enumerate(self.pick("Emp_Profile", "NI_number", 6, lambda r: len(r["NI_number"]) == 9)):
            self.set("INVALID_NI_NUMBER", "Emp_Profile", r, "NI_number", ni(r["NI_number"], i))
        for i, r in enumerate(self.pick("Emp_Profile", "SortCode", 4, lambda r: r["SortCode"].count("-") == 2)):
            self.set("INVALID_SORT_CODE", "Emp_Profile", r, "SortCode",
                     [r["SortCode"].replace("-", ""), r["SortCode"][:5], "N/A", r["SortCode"].replace("-", " ")][i])

    def domains(self):
        specs = [("Req_Hired", "Pipeline_Stage", ["placed", "PLACED ", "Plcd", "Interviewing", "1st Interview",
                                                  "rejected - client", "Offer accepted", "Screen"]),
                 ("Req", "Worktype", ["contract", "Perm", "Temp to Perm", "C", "PERMANENT", "Fixed Term"]),
                 ("Req", "CurrencyCode", ["£", "gbp", "UKP", "GBP ", "Pounds"]),
                 ("Invoice", "Currency", ["£", "Sterling", "gbp"]),
                 ("Invoice", "VAT", ["0.2", "20", "twenty percent", "VAT exempt", "17.5%"]),
                 ("Leads", "Lead_Source", ["linkedin", "Linked In", "LI", "referal", "web"])]
        for table, col, vals in specs:
            for r, v in zip(self.pick(table, col, len(vals)), vals):
                self.set("NON_STANDARD_DOMAIN", table, r, col, v, f"was '{r[col]}'")

    def whitespace(self):
        for i, r in enumerate(self.pick("Accounts", "Account_name", 6, lambda r: r["Account_name"] != "")):
            n = r["Account_name"]
            self.set("WHITESPACE_CASE", "Accounts", r, "Account_name",
                     [n + "  ", n.upper(), n.replace(" ", "  ", 1), " " + n, n.lower(), n + "\t"][i])
        for i, r in enumerate(self.pick("Person", "First_Name", 6, lambda r: r["First_Name"] != "")):
            n = r["First_Name"]
            self.set("WHITESPACE_CASE", "Person", r, "First_Name",
                     [n.lower(), " " + n, n.upper(), n + " ", n.lower(), n + "  "][i])

    def dates(self):
        for r in self.pick("Person", "DOB", 5, lambda r: r["DOB"] != ""):
            self.set("SENTINEL_DATE", "Person", r, "DOB", "1900-01-01")
        for r, y in zip(self.pick("Person", "DOB", 2, lambda r: r["DOB"] != ""), (2031, 2045)):
            self.set("SENTINEL_DATE", "Person", r, "DOB", f"{y}-03-14", "DOB in the future")
        for r in self.pick("Req", "StartDate", 3):
            self.set("SENTINEL_DATE", "Req", r, "StartDate", "1900-01-01 00:00:00")
        for r in self.pick("Req_Hired", "EndDate", 5, lambda r: parse_d(r["StartDate"]) is not None):
            end = parse_d(r["StartDate"]) - timedelta(days=self.rng.randint(5, 200))
            self.set("DATE_LOGIC", "Req_Hired", r, "EndDate", end.strftime("%Y-%m-%d"), "EndDate before StartDate")
        for r in self.pick("Req", "CreatedAt", 2):
            self.set("DATE_LOGIC", "Req", r, "CreatedAt", "2099-12-31 00:00:00", "CreatedAt in the future")
        for r in self.pick("Invoice", "DateDue", 4, lambda r: parse_d(r["InvoiceDate"]) is not None):
            due = parse_d(r["InvoiceDate"]) - timedelta(days=30)
            self.set("DATE_LOGIC", "Invoice", r, "DateDue", due.strftime("%Y-%m-%d"), "DateDue before InvoiceDate")

    def ranges(self):
        for r in self.pick("Req_Rates", "Payrate", 3, lambda r: r["Payrate"] != ""):
            self.set("OUT_OF_RANGE", "Req_Rates", r, "Payrate", -float(r["Payrate"]), "negative pay rate")
        for r in self.pick("Req_Rates", "BillRate", 3, lambda r: r["Payrate"] != ""):
            self.set("OUT_OF_RANGE", "Req_Rates", r, "BillRate", round(float(r["Payrate"]) * 0.8, 2),
                     "bill rate below pay rate (negative margin)")
        for r, v in zip(self.pick("Leads", "Lead_Score", 4), (0, 7, 99, -1)):
            self.set("OUT_OF_RANGE", "Leads", r, "Lead_Score", v, "expected 1-5")
        for r, v in zip(self.pick("TimesheetItems", "TotalHours", 4), (26, -4, 0, 168)):
            self.set("OUT_OF_RANGE", "TimesheetItems", r, "TotalHours", v, "impossible hours for one day")
        for r in self.pick("Addresses", "Latitude", 3, lambda r: r["Latitude"] != ""):
            self.set("OUT_OF_RANGE", "Addresses", r, "Latitude", 0, "0,0 'null island' geocode")
            self.used.add(("Addresses", r["AddressID"], "Longitude"))
            self.set("OUT_OF_RANGE", "Addresses", r, "Longitude", 0, "0,0 'null island' geocode")

    def encoding(self):
        for r in self.pick("Accounts", "About", 5, lambda r: "£" in r["About"]):
            self.set("ENCODING", "Accounts", r, "About", r["About"].replace("£", "Â£"), "£ -> Â£")
        for r in self.pick("Notes", "Notetext", 5, lambda r: "'" in r["Notetext"]):
            self.set("ENCODING", "Notes", r, "Notetext", r["Notetext"].replace("'", "â€™"), "' -> â€™")

    def soft_delete(self):
        live = {r["AccountID"] for r in self.rows("Req") if r["Deleted"] == "0" and r["StatusID"] in ("1", "2", "3")
                and ("Req", r["ReqID"], "AccountID") not in self.used}
        placed = {h["Account_ID"] for h in self.rows("Req_Hired") if h["Pipeline_Stage"] == "Placed" and h["Deleted"] == "0"}
        for r in self.pick("Accounts", "Deleted", 3, lambda r: r["Deleted"] == "0" and r["Account_ID"] in live
                           and r["Account_ID"] not in placed):
            self.set("SOFT_DELETE_CONFLICT", "Accounts", r, "Deleted", 1, "account deleted but has open jobs")

    def account_dupes(self):
        def variant(n: str, k: int) -> str:
            opts = [n.replace(" Ltd", " Limited") if " Ltd" in n else n + " Ltd",
                    n + " UK", n + ".", "The " + n,
                    n.replace(" & ", " and ") if " & " in n else n.replace(" and ", " & ") if " and " in n else n + " (UK)",
                    n.replace(" Limited", "").replace(" Ltd", "").replace(" plc", "").replace(" PLC", ""),
                    re.sub(r"(\w)(\w)(\w*)$", r"\2\1\3", n, count=1),  # typo in last word
                    n + " - London"]
            return opts[k % len(opts)]
        # only jobs with nothing hanging off them move to the duplicate (placements, meetings, POs, timesheets
        # and leads would otherwise disagree with the job's new company: a second, unrelated problem)
        busy = ({r["Req_ID"] for r in self.rows("Req_Hired")} | {r["Req_ID"] for r in self.rows("Schedule")}
                | {r["ReqID"] for r in self.rows("PONo")} | {r["Req_ID"] for r in self.rows("TimesheetItems")}
                | {r["Req_ID"] for r in self.rows("Leads")})
        reqs_by_acct = defaultdict(list)
        for r in self.rows("Req"):
            reqs_by_acct[r["AccountID"]].append(r)
        free_jobs = {a: [r for r in rs if r["ReqID"] not in busy] for a, rs in reqs_by_acct.items()}
        srcs = self.pick("Accounts", "*dup", 8,
                         lambda r: len(reqs_by_acct[r["Account_ID"]]) >= 2 and bool(free_jobs.get(r["Account_ID"])))
        for i, src in enumerate(srcs):
            new_id = self.alloc("Accounts")
            name = variant(src["Account_name"], i)
            self.copy_row("DUPLICATE_ACCOUNT", "Accounts", src["Account_ID"],
                          {"Account_ID": new_id, "Account_name": name, "AccountReferenceNo": None,
                           "CreatedAt": "2023-06-01 09:00:00", "Note": None},
                          f"duplicate of Account_ID {src['Account_ID']} ('{src['Account_name']}')")
            for req in self.rng.sample(free_jobs[src["Account_ID"]], 1):
                self.used.add(("Req", req["ReqID"], "AccountID"))
                self.set("SPLIT_HISTORY", "Req", req, "AccountID", new_id,
                         f"job moved from Account_ID {src['Account_ID']} to its duplicate")
                if req["AssociateID"]:     # the hiring contact belongs to the original company, not the copy
                    self.raw_set("Req", req, "AssociateID", None)

    def person_dupes(self):
        def variant(p: dict, k: int) -> tuple[dict, str]:
            fn, ln, dob = p["First_Name"], p["Last_Name"], p["DOB"]
            if k % 5 == 0 and fn in NICKNAMES:
                return {"First_Name": NICKNAMES[fn]}, "nickname"
            if k % 5 == 1 and len(ln) > 4:
                i = len(ln) // 2
                return {"Last_Name": ln[:i - 1] + ln[i] + ln[i - 1] + ln[i + 1:]}, "transposed letters in surname"
            if k % 5 == 2 and dob and int(dob[8:10]) <= 12 and dob[5:7] != dob[8:10]:
                return {"DOB": f"{dob[:4]}-{dob[8:10]}-{dob[5:7]}"}, "day/month swapped in DOB"
            if k % 5 == 3:
                return {"Middle_name": None}, "no middle name"
            return {"DOB": None}, "DOB missing on duplicate"
        assoc_by_person = {}
        for a in self.rows("Associates"):
            assoc_by_person.setdefault(a["Person_ID"], a)
        srcs = self.pick("Person", "*dup", 12, lambda r: r["Last_Name"] and r["DOB"])
        for i, src in enumerate(srcs):
            new_id = self.alloc("Person", floor=10001)
            ov, why = variant(src, i)
            a = assoc_by_person.get(src["Person_ID"])
            with_contact = bool(a and i % 2 == 0)
            # the copy's role flags match what it has: a contact row only if one is copied, never a profile
            self.copy_row("DUPLICATE_PERSON", "Person", src["Person_ID"],
                          {"Person_ID": new_id, **ov, "GDPRConsent_ID": None, "CreatedAt": "2022-02-14 11:00:00",
                           "Associate": 1 if with_contact else 0, "Emp": 0},
                          f"duplicate of Person_ID {src['Person_ID']}: {why}")
            if with_contact:
                new_assoc = str(self.alloc("Associates"))
                self.copy_row("DUPLICATE_ASSOCIATE", "Associates", a["AssociateID"],
                              {"AssociateID": new_assoc, "Person_ID": new_id, "CreatedAt": "2022-02-14 11:05:00"},
                              f"duplicate contact of AssociateID {a['AssociateID']}")
                self.contact_helpers(a["AssociateID"], new_assoc)

    def transaction_dupes(self):
        for src in self.pick("TimesheetItems", "*dup", 5):
            self.copy_row("DUPLICATE_TRANSACTION", "TimesheetItems", src["ItemID"],
                          {"ItemID": self.alloc("TimesheetItems")}, f"double entry of ItemID {src['ItemID']}")

    def job_dupes(self):
        for src in self.pick("Req", "*dup", 3, lambda r: r["Deleted"] == "0"):
            self.copy_row("DUPLICATE_JOB", "Req", src["ReqID"],
                          {"ReqID": self.alloc("Req"), "CreatedAt": "2024-11-04 10:00:00", "UpdatedAt": "2024-11-04 10:00:00"},
                          f"job {src['ReqID']} raised a second time")

    def orphan_candidates(self):
        """New candidates with nothing attached: e.g. a half-finished web registration."""
        names = [("Evelyn", "Marchetti", "1991-02-03"), ("Rufus", "Okonjo", "1987-07-21"), ("Imogen", "Fairweather", "1995-11-30")]
        srcs = self.pick("Person", "*orphan", len(names), lambda r: r["Associate"] == "0")
        for src, (fn, ln, dob) in zip(srcs, names):
            self.copy_row("ORPHAN_CANDIDATE", "Person", src["Person_ID"],
                          {"Person_ID": self.alloc("Person", floor=10101), "First_Name": fn, "Middle_name": None,
                           "Last_Name": ln, "DOB": dob, "GDPRConsent_ID": None, "Associate": 0, "Emp": 0,
                           "CreatedAt": "2024-10-01 09:00:00"},
                          "candidate registered with no profile, CV or activity")

    def placements_on_deleted(self):
        """Jobs and companies soft-deleted while their placements stay live (each live placement is a finding)."""
        def taken(table, pk):
            return any(u[0] == table and u[1] == pk for u in self.used)
        placed = [h for h in self.rows("Req_Hired") if h["Pipeline_Stage"] == "Placed" and h["Deleted"] == "0"]
        by_req, by_acc = {}, {}
        for h in placed:
            by_req.setdefault(h["Req_ID"], []).append(h)
            by_acc.setdefault(h["Account_ID"], []).append(h)
        open_acc = {r["AccountID"] for r in self.rows("Req") if r["Deleted"] == "0" and r["StatusID"] in ("1", "2", "3")}
        jobs = self.pick("Req", "Deleted", 2, lambda r: r["Deleted"] == "0" and r["StatusID"] == "4" and r["ReqID"] in by_req
                         and not taken("Req", r["ReqID"]) and not taken("Accounts", r["AccountID"]))
        for r in jobs:
            self.raw_set("Req", r, "Deleted", 1)
            for h in by_req[r["ReqID"]]:
                self.record("PLACEMENT_ON_DELETED", "Req_Hired", h["Req_HiredID"], "Req.Deleted", "0", "1",
                            f"job {r['ReqID']} deleted while placement is live")
        skip = {r["AccountID"] for r in jobs}
        for a in self.pick("Accounts", "Deleted", 2, lambda a: a["Deleted"] == "0" and a["Account_ID"] in by_acc
                           and a["Account_ID"] not in open_acc and a["Account_ID"] not in skip and not taken("Accounts", a["Account_ID"])):
            self.raw_set("Accounts", a, "Deleted", 1)
            for h in by_acc[a["Account_ID"]]:
                self.record("PLACEMENT_ON_DELETED", "Req_Hired", h["Req_HiredID"], "Accounts.Deleted", "0", "1",
                            f"company {a['Account_ID']} deleted while placement is live")

    def unattached(self):
        """Notes and documents linked to no record: the id was lost, or points at a record that does not exist."""
        for r in self.pick("Notes", "ObjectId", 4, lambda r: r["ObjectId"] != ""):
            self.set("ORPHAN_NOTE", "Notes", r, "ObjectId", None, f"{r['ObjectType']} note lost its record id")
        for r in self.pick("Notes", "ObjectId", 3, lambda r: r["ObjectId"] != ""):
            self.set("ORPHAN_NOTE", "Notes", r, "ObjectId", 90000 + self.rng.randint(1, 9999),
                     f"{r['ObjectType']} note points at a record that does not exist")
        linked = ({r["Document_ID"] for t in ("Req_Documents", "Emp_Documents", "RecruiterDocuments", "Leads", "Invoice")
                   for r in self.rows(t)} | {r["Doc_ID"] for r in self.rows("BackgroundChecks")})
        for r in self.pick("Documents", "Doc_AssocID", 3, lambda r: r["Doc_AssocID"] != "" and r["Doc_ID"] not in linked):
            self.set("ORPHAN_DOCUMENT", "Documents", r, "Doc_AssocID", None, f"{r['ObjectType']} document lost its owner")

    def orphan_contacts(self):
        """New contacts linked to no company (e.g. added from an email signature, never attached)."""
        people = [("Ms", "Harriet", "Lindqvist"), ("Mr", "Graham", "Achterberg"), ("Ms", "Mhairi", "Vasudevan"),
                  ("Mr", "Fraser", "Rennie")]
        srcs = self.pick("Associates", "*orphan", len(people))
        persons = {p["Person_ID"]: p for p in self.rows("Person")}
        for src, (title, fn, ln) in zip(srcs, people):
            pid = self.alloc("Person", floor=10201)
            self.copy_row("", "Person", src["Person_ID"],
                          {"Person_ID": pid, "First_Name": fn, "Middle_name": None, "Last_Name": ln, "DOB": None,
                           "GDPRConsent_ID": None, "Associate": 1, "Emp": 0, "Deleted": 0,
                           "CreatedAt": "2024-09-01 09:00:00"}, record=False)
            aid = str(self.alloc("Associates"))
            self.copy_row("ORPHAN_CONTACT", "Associates", src["AssociateID"],
                          {"AssociateID": aid, "Person_ID": pid, "AssociateTitle": title, "Active": 1,
                           "CreatedAt": "2024-09-01 09:05:00"}, f"{fn} {ln}: contact linked to no company")
            self.contact_helpers(src["AssociateID"], aid, with_company=False)

    def run(self):
        # Only defects the STANDARD CHECKS look for are planted (validation/standard_checks.py):
        # duplicate people and entities, deleted-but-active records,
        # live placements on deleted jobs or companies, orphaned contacts / documents / notes. Everything else is clean at source.
        # (emails, phones, postcodes, missing, ni_and_bank, domains, whitespace, dates, ranges and encoding are
        # kept below but not run: contact details are fixed at source, not checked on the dashboard.)
        # duplicates first: INSERT..SELECT copies must see the clean source rows
        # (orphans() — broken links in other tables — is kept but not run: fixed at source)
        for step in (self.account_dupes, self.person_dupes, self.transaction_dupes, self.job_dupes,
                     self.orphan_contacts, self.unattached, self.placements_on_deleted,
                     self.soft_delete):
            step()


def build(schema: dict, database: str) -> tuple[Counter, list[dict]]:
    inj = Injector(schema)
    inj.run()
    sql = ["-- Generated by sample_data/inject_defects.py — do not edit by hand.",
           "-- Plants known data-quality defects in the legacy source DB.",
           "-- Answer key: sql/source/defect_manifest.csv", "SET NOCOUNT ON;", f"USE {q(database)};", "GO",
           "BEGIN TRANSACTION;",
           "-- 0. a past 'quick fix' import disabled these FKs; they are left disabled / not trusted",
           *[f"ALTER TABLE dbo.{q(t)} NOCHECK CONSTRAINT {q(fk_name(t, c))};" for t, c in inj.disabled_fks],
           "-- 1. duplicate rows (copied from clean originals)", *inj.inserts,
           "-- 2. in-place corruption", *inj.updates, "COMMIT;",
           f"PRINT 'Injected {len(inj.manifest)} defects';", "GO"]
    (SQL_DIR / "04_inject_legacy_defects.sql").write_text("\n".join(sql), encoding="utf-8")

    with open(SQL_DIR / "defect_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(inj.manifest[0].keys()))
        w.writeheader()
        w.writerows(inj.manifest)

    by_cat = Counter(m["category"] for m in inj.manifest)
    by_cat_tables = defaultdict(set)
    for m in inj.manifest:
        by_cat_tables[m["category"]].add(f"{m['table']}.{m['column']}" if m["column"] != "*" else m["table"])
    md = ["# Planted source data defects", "",
          "Generated by `sample_data/inject_defects.py`. The CSVs in `sample_data/source/` are the clean "
          "baseline; these defects exist only in the SQL Server source database after "
          "`sql/source/04_inject_legacy_defects.sql` runs. Row-level answer key: "
          "`sql/source/defect_manifest.csv`.", "",
          f"**{len(inj.manifest)} defects** across {len(by_cat)} categories. "
          f"Rows added by duplication: {dict(inj.inserted)}.", "",
          "| Category | Count | What it is | Where |", "|---|---:|---|---|"]
    for cat in CATEGORY_INFO:
        if by_cat[cat]:
            md.append(f"| `{cat}` | {by_cat[cat]} | {CATEGORY_INFO[cat]} | {', '.join(sorted(by_cat_tables[cat]))} |")
    md += ["", "Defects that already existed in the generated data (not in the manifest) include "
           "same-name/same-DOB people, people with no DOB, and invoice totals that don't add up. "
           "Profiling should find those too."]
    (ROOT / "docs" / "source_defects.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return inj.inserted, inj.manifest


if __name__ == "__main__":
    from build_source_db import DEFAULT_DB
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    inserted, manifest = build(load_schema(), DEFAULT_DB)
    print(f"{len(manifest)} defects, inserted rows: {dict(inserted)}")
    print(Counter(m["category"] for m in manifest).most_common())
