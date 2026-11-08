"""
sample_data/repair_baseline.py

Makes the clean baseline CSVs logically consistent (not just referentially valid).
The AI-generated data linked people at random, so this step imposes the role
model documented in docs/source_data_model.md:

  CONTACTS   = people with an Associates row (client-side). Every contact belongs
               to an account, uses that account's office address, and has a
               title that matches their first name.
  CANDIDATES = people without an Associates row. Candidate-side tables
               (Emp_Profile, CV_Docs, BackgroundChecks, ObjectHotlist,
               Interview_Feedback.Interviewee_ID, Schedule[Candidate],
               Req_Hired.Invoiced_PersonID, TimesheetItems) point at candidates.
  EDGE CASES = 5 people deliberately kept as contact AND candidate
               (sql/source/edge_cases.csv). They are valid data, not defects.

Also repairs: duplicate associate-type rows, account-address email domains,
invoice arithmetic, invoice/PO vendor mismatches, invalid NI numbers,
placeholder postcodes, and soft-delete conflicts.

Idempotent and deterministic. Rules that prove the result live in
validation/baseline_rules.py.
"""

from __future__ import annotations

import csv
import random
import re
import string
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import dedupe_generated as dg

SEED = 99
N_DUAL_ROLE = 5
VAT_RATE = 0.20

NI_FIRST = "ABCEGHJKLMNOPRSTWXYZ"          # not D F I Q U V
NI_SECOND = "ABCEGHJKLMNPRSTWXYZ"          # not D F I O Q U V
NI_BANNED = {"BG", "GB", "NK", "KN", "TN", "NT", "ZZ"}
POSTCODE_RE = re.compile(r"^(?:[A-Z]{1,2}\d{1,2}|[A-Z]{1,2}\d[A-Z]) \d[A-Z]{2}$")
NI_RE = re.compile(rf"^[{NI_FIRST}][{NI_SECOND}]\d{{6}}[A-D]$")


def gender_of(first_name: str) -> str | None:
    g = dg.FIRST_NAME_GROUP.get(first_name)
    if g:
        return g[1]
    for grp in dg.GROUPS.values():
        if first_name in grp["F"]:
            return "F"
        if first_name in grp["M"]:
            return "M"
    if first_name in dg.BRITISH_F:
        return "F"
    return None


def domain_of(website: str, name: str) -> str:
    d = re.sub(r"^https?://(www\.)?", "", (website or "").strip()).split("/")[0]   # host only, no path
    return d or (dg.slug(" ".join(dg.brand_stem(name).split()[:2])) or "example") + ".co.uk"


HOURS_PER_DAY = 7.5                                   # day rate -> hourly rate
PAY_MULT = {"1": 1.0, "2": 1.5, "3": 1.0, "4": 0.0, "5": 0.0}   # Regular, Overtime, Training, Sick, Bank Hol
LATEST_WEEK = date(2026, 10, 26)                      # no timesheets in the future


def _mondays(start: date, end: date) -> list[date]:
    first = start + timedelta(days=(7 - start.weekday()) % 7)
    out = []
    d = first
    while d + timedelta(days=6) <= min(end, LATEST_WEEK + timedelta(days=6)):
        out.append(d)
        d += timedelta(days=7)
    return out


def _repair_timesheets(T: dict, setv, req_by_id: dict) -> list[str]:
    """Timesheet = one contractor, one job, one Monday-Sunday week inside their placement.
    Lines carry the timesheet's type, hours = clock span minus a 30-min break (shifts >= 6h),
    rates come from the job's day rates, approval fields follow the status."""
    items_by_ts = defaultdict(list)
    for it in T["TimesheetItems"]:
        items_by_ts[it["Timesheet_ID"]].append(it)
    placement = {}
    for h in T["Req_Hired"]:
        if h["Pipeline_Stage"] == "Placed" and h["Worktype"] == "Contract":
            placement[(h["Req_ID"], h["Invoiced_PersonID"])] = h
    rates = {r["Req_ID"]: r for r in T["Req_Rates"]}
    billable = {t["Timesheet_TypeID"]: t["Billable"] == "1" for t in T["TimesheetType"]}
    po_of_job = defaultdict(list)
    for p in T["PONo"]:
        po_of_job[p["ReqID"]].append(p["PONo"])
    recruiters = sorted((r["RecruiterID"] for r in T["Recruiter"]), key=int)

    by_placement = defaultdict(list)
    orphan_ts = 0
    for ts in sorted(T["TimeSheets"], key=lambda t: int(t["ID"])):
        its = items_by_ts.get(ts["ID"])
        h = placement.get((its[0]["Req_ID"], its[0]["Person_ID"])) if its else None
        if h:
            by_placement[h["Req_HiredID"]].append((ts, h))
        else:
            orphan_ts += 1

    short = 0
    for _, group in by_placement.items():
        h = group[0][1]
        weeks = _mondays(datetime.strptime(h["StartDate"][:10], "%Y-%m-%d").date(),
                         datetime.strptime(h["EndDate"][:10], "%Y-%m-%d").date())
        if not weeks:
            continue
        short += max(0, len(group) - len(weeks))
        offset = int(h["Req_HiredID"]) % len(weeks)
        for i, (ts, _) in enumerate(group):
            mon = weeks[(offset + i) % len(weeks)]
            sun = mon + timedelta(days=6)
            setv("TimeSheets", ts, "StartDate", mon.isoformat())
            setv("TimeSheets", ts, "Enddate", sun.isoformat())
            k = int(ts["ID"])
            if ts["Status"] == "Approved":
                setv("TimeSheets", ts, "Approved_Date", f"{(sun + timedelta(days=1 + k % 3)).isoformat()} 09:00:00")
                setv("TimeSheets", ts, "Approved_By", ts["Approved_By"] or recruiters[k % len(recruiters)])
            else:
                setv("TimeSheets", ts, "Approved_Date", "")
                setv("TimeSheets", ts, "Approved_By", "")
            job = ts_job = group[0][1]["Req_ID"]
            if ts["PONo"] and ts["PONo"] not in po_of_job.get(ts_job, []):
                setv("TimeSheets", ts, "PONo", po_of_job[ts_job][0] if po_of_job.get(ts_job) else "")
            rate = rates.get(job, {})
            mult = PAY_MULT.get(ts["Timesheet_TypeID"], 1.0)
            pay = round(float(rate.get("Payrate") or 0) / HOURS_PER_DAY * mult, 2)
            bill = round(float(rate.get("BillRate") or 0) / HOURS_PER_DAY * mult, 2) if billable.get(ts["Timesheet_TypeID"]) else 0.0
            setv("TimeSheets", ts, "Payrate", f"{pay:.2f}")
            setv("TimeSheets", ts, "Billrate", f"{bill:.2f}")
            lines = sorted(items_by_ts[ts["ID"]], key=lambda r: int(r["ItemID"]))
            for day, it in enumerate(lines):
                # the schema has no work-date on a line: CreatedAt records the day worked (Mon, Tue, ...)
                # (more than 7 lines = a second shift that day, entered an hour later)
                submitted = f"{(mon + timedelta(days=day % 7)).isoformat()} {17 + day // 7}:30:00"
                setv("TimesheetItems", it, "Timesheet_TypeID", ts["Timesheet_TypeID"])
                s = datetime.strptime(it["StartTime"][:5], "%H:%M")
                e = datetime.strptime(it["EndTime"][:5], "%H:%M")
                span = (e - s).seconds / 3600
                setv("TimesheetItems", it, "TotalHours", f"{span - (0.5 if span >= 6 else 0):g}")
                setv("TimesheetItems", it, "CreatedAt", submitted)
                setv("TimesheetItems", it, "UpdatedAt", ts["Approved_Date"] or submitted)
    # empty timesheets (created, never filled in) are kept, but approval fields must still follow the status
    for ts in T["TimeSheets"]:
        if ts["ID"] not in items_by_ts:
            k = int(ts["ID"])
            if ts["Status"] == "Approved":
                end = datetime.strptime(ts["Enddate"][:10], "%Y-%m-%d").date()
                setv("TimeSheets", ts, "Approved_Date", f"{(end + timedelta(days=1 + k % 3)).isoformat()} 09:00:00")
                setv("TimeSheets", ts, "Approved_By", ts["Approved_By"] or recruiters[k % len(recruiters)])
            else:
                setv("TimeSheets", ts, "Approved_Date", "")
                setv("TimeSheets", ts, "Approved_By", "")
    log = [f"Timesheets: {sum(len(g) for g in by_placement.values())} placed in Mon-Sun weeks inside their placement; "
           f"line types, hours, rates and approval aligned"]
    if orphan_ts:
        log.append(f"  Timesheets: {orphan_ts} are empty (no lines) - kept, approval fields aligned")
    if short:
        log.append(f"! Timesheets: {short} share a week because the placement is shorter than its timesheet count")
    return log


def run(read_csv, write_csv, columns: dict, root: Path) -> list[str]:
    rng = random.Random(SEED)
    log: list[str] = []
    T = {t: read_csv(t) for t in [
        "Person", "Associates", "AccountAssociates", "AssociateTypeRelation", "AssociateTypes", "Accounts",
        "Addresses", "Emp_Profile", "Emp_Documents", "CV_Docs", "BackgroundChecks", "ObjectHotlist",
        "Interview_Feedback", "Schedule", "Req", "Req_Hired", "TimesheetItems", "TimeSheets", "PONo",
        "Invoice", "InvoiceEntries", "Log", "Req_Rates", "TimesheetType", "Recruiter", "Notes", "EmpHist"]}
    changed: set[str] = set()

    def setv(table, row, col, val):
        val = "" if val is None else str(val)
        if row.get(col, "") != val:
            row[col] = val
            changed.add(table)
            return 1
        return 0

    accounts = {a["Account_ID"]: a for a in T["Accounts"]}
    persons = {p["Person_ID"]: p for p in T["Person"]}

    # ── 1. every contact belongs to an account ────────────────────────────────
    acct_contacts = defaultdict(list)
    for aa in T["AccountAssociates"]:
        acct_contacts[aa["AccountID"]].append(aa["AssociateID"])
    linked = {aa["AssociateID"] for aa in T["AccountAssociates"]}
    next_aa = max(int(aa["AccountAssociateID"]) for aa in T["AccountAssociates"]) + 1
    added = 0
    for s in T["Associates"]:
        if s["AssociateID"] not in linked:
            # the account with the fewest contacts (ties -> lowest id): spreads contacts evenly
            acct = min(accounts, key=lambda a: (len(acct_contacts[a]), int(a)))
            T["AccountAssociates"].append({"AccountAssociateID": str(next_aa), "AssociateID": s["AssociateID"], "AccountID": acct})
            acct_contacts[acct].append(s["AssociateID"])
            linked.add(s["AssociateID"])
            next_aa += 1
            added += 1
    if added:
        changed.add("AccountAssociates")
        log.append(f"AccountAssociates: {added} contacts without an account linked to one")
    account_of = {}
    for aa in sorted(T["AccountAssociates"], key=lambda r: int(r["AccountAssociateID"])):
        account_of.setdefault(aa["AssociateID"], aa["AccountID"])
    assoc_by_id = {s["AssociateID"]: s for s in T["Associates"]}
    contact_persons_of_acct = defaultdict(list)
    for acct, assocs in acct_contacts.items():
        for a in assocs:
            contact_persons_of_acct[acct].append(assoc_by_id[a]["Person_ID"])

    # ── 2. titles match first-name gender; contact uses account office address ─
    n_title = n_addr = 0
    for s in T["Associates"]:
        p = persons.get(s["Person_ID"])
        g = gender_of(p["First_Name"]) if p else None
        if g == "M" and s["AssociateTitle"] in ("Ms", "Mrs", "Miss"):
            n_title += setv("Associates", s, "AssociateTitle", "Mr")
        elif g == "F" and s["AssociateTitle"] == "Mr":
            n_title += setv("Associates", s, "AssociateTitle", "Ms")
        acct = accounts.get(account_of.get(s["AssociateID"], ""))
        if acct and acct["AddressID"]:
            n_addr += setv("Associates", s, "Associate_AddressID", acct["AddressID"])
    log.append(f"Associates: {n_title} titles aligned with gender, {n_addr} contacts moved to their account's office address")

    # office address email domain = the account's domain
    addr = {a["AddressID"]: a for a in T["Addresses"]}
    n_dom = 0
    for a in T["Accounts"]:
        ad = addr.get(a["AddressID"])
        if ad and "@" in ad["Email"]:
            want = ad["Email"].split("@")[0] + "@" + domain_of(a["Website"], a["Account_name"])
            n_dom += setv("Addresses", ad, "Email", want)
    log.append(f"Addresses: {n_dom} office emails moved onto their account's domain")

    # ── 3. roles: contacts vs candidates ──────────────────────────────────────
    contacts = sorted({s["Person_ID"] for s in T["Associates"]}, key=int)
    contact_set = set(contacts)
    candidates = sorted((p for p in persons if p not in contact_set), key=int)
    rng_dual = random.Random(SEED + 1)
    profiles_on_contacts = [e for e in T["Emp_Profile"] if e["Person_ID"] in contact_set]
    edge_path = root / "sql" / "source" / "edge_cases.csv"
    if edge_path.exists():   # keep the same edge cases across runs
        with open(edge_path, newline="", encoding="utf-8") as f:
            dual = {r["person_id"] for r in csv.DictReader(f)}
    else:
        dual = {e["Person_ID"] for e in rng_dual.sample(profiles_on_contacts, min(N_DUAL_ROLE, len(profiles_on_contacts)))}

    used = {e["Person_ID"] for e in T["Emp_Profile"] if e["Person_ID"] not in contact_set}
    free = [c for c in candidates if c not in used]
    remap: dict[str, str] = {}
    for e in T["Emp_Profile"]:
        p = e["Person_ID"]
        if p in contact_set and p not in dual:
            remap[p] = free.pop(0)
            setv("Emp_Profile", e, "Person_ID", remap[p])
    spare = free or candidates

    def as_candidate(p: str) -> str:
        if not p or p not in contact_set or p in dual:
            return p
        if p not in remap:
            remap[p] = spare[int(p) % len(spare)]
        return remap[p]

    def as_contact(p: str) -> str:
        if not p or p in contact_set:
            return p
        return contacts[(int(p) * 7) % len(contacts)]

    profile_person = {e["Emp_ProfileID"]: e["Person_ID"] for e in T["Emp_Profile"]}
    for d in T["Emp_Documents"]:
        setv("Emp_Documents", d, "Person_ID", profile_person.get(d["Emp_ID"], d["Person_ID"]))
    for d in T["CV_Docs"]:
        setv("CV_Docs", d, "CV_AssocID", as_candidate(d["CV_AssocID"]))
    for t in ("BackgroundChecks", "ObjectHotlist"):
        for r in T[t]:
            setv(t, r, "Person_ID", as_candidate(r["Person_ID"]))
    for r in T["Interview_Feedback"]:
        setv("Interview_Feedback", r, "Interviewee_ID", as_candidate(r["Interviewee_ID"]))
        for c in ("Interviewer_ID", "Second_InterviewerID", "Other_InterviewerID"):
            setv("Interview_Feedback", r, c, as_contact(r[c]))

    # placements: client contact must belong to the account; the placed person is a candidate
    req_by_id = {r["ReqID"]: r for r in T["Req"]}
    for h in T["Req_Hired"]:
        job = req_by_id.get(h["Req_ID"], {})
        acct = h["Account_ID"]
        job_contact = job.get("AssociateID", "")
        if job_contact and account_of.get(job_contact) == acct:
            setv("Req_Hired", h, "Associate_ID", job_contact)
        elif acct_contacts.get(acct):
            setv("Req_Hired", h, "Associate_ID", acct_contacts[acct][int(h["Req_HiredID"]) % len(acct_contacts[acct])])
        else:
            setv("Req_Hired", h, "Associate_ID", "")
        cand = h["Invoiced_PersonID"] or candidates[int(h["Req_HiredID"]) % len(candidates)]
        setv("Req_Hired", h, "Invoiced_PersonID", as_candidate(cand))
    # jobs: client contact must belong to the account
    for r in T["Req"]:
        if r["AssociateID"] and account_of.get(r["AssociateID"]) != r["AccountID"]:
            setv("Req", r, "AssociateID", acct_contacts[r["AccountID"]][0] if acct_contacts.get(r["AccountID"]) else "")

    # schedule: contact meetings with a contact of that account; candidate meetings with a candidate
    for s in T["Schedule"]:
        if s["Person_Type"] == "Contact":
            people = contact_persons_of_acct.get(s["Account_ID"])
            if people:
                if s["Person_ID"] not in people:
                    setv("Schedule", s, "Person_ID", people[int(s["Schedule_ID"]) % len(people)])
            else:
                p = as_contact(s["Person_ID"])
                setv("Schedule", s, "Person_ID", p)
                a = next((aa for aa, ps in contact_persons_of_acct.items() if p in ps), "")
                setv("Schedule", s, "Account_ID", a)
            if s["Req_ID"] and req_by_id.get(s["Req_ID"], {}).get("AccountID") != s["Account_ID"]:
                setv("Schedule", s, "Req_ID", "")
        else:
            setv("Schedule", s, "Person_ID", as_candidate(s["Person_ID"]))

    # timesheet lines belong to the contractor placed on that job
    placed = defaultdict(list)
    for h in sorted(T["Req_Hired"], key=lambda r: int(r["Req_HiredID"])):
        if h["Pipeline_Stage"] == "Placed" and h["Worktype"] == "Contract" and h["Invoiced_PersonID"]:
            placed[h["Req_ID"]].append(h["Invoiced_PersonID"])
    no_placement = 0
    placed_jobs = sorted(placed, key=int)
    for it in T["TimesheetItems"]:
        if not it["Req_ID"] and placed_jobs:   # timesheet with no PO: still worked on a placed contract job
            setv("TimesheetItems", it, "Req_ID", placed_jobs[int(it["Timesheet_ID"]) % len(placed_jobs)])
        who = placed.get(it["Req_ID"])
        if who:
            setv("TimesheetItems", it, "Person_ID", who[int(it["Timesheet_ID"]) % len(who)])
        else:
            no_placement += 1
    if no_placement:
        log.append(f"! TimesheetItems: {no_placement} lines on jobs with no contract placement")
    log += _repair_timesheets(T, setv, req_by_id)

    # person flags reflect the roles
    emp_people = {e["Person_ID"] for e in T["Emp_Profile"]}
    for p in T["Person"]:
        setv("Person", p, "Associate", 1 if p["Person_ID"] in contact_set else 0)
        setv("Person", p, "Emp", 1 if p["Person_ID"] in emp_people else 0)
    for e in T["Emp_Profile"]:   # profile notes start with the person's name
        pp = persons.get(e["Person_ID"])
        m = re.match(r"^([A-Z][\w'’-]+(?: [A-Z][\w'’-]+){1,2}) - ", e["Profile_Notes"])
        if pp and m:
            setv("Emp_Profile", e, "Profile_Notes", f"{pp['First_Name']} {pp['Last_Name']}" + e["Profile_Notes"][len(m.group(1)):])
    log.append(f"Roles: {len(contacts)} contacts, {len(candidates)} candidates, {len(remap)} candidate-side references moved "
               f"off contacts, {len(dual)} deliberate dual-role people")

    # associate types: one 'Contact' row each, plus 'Candidate' for the dual-role people
    types = {t["TypeName"]: t["Associate_TypeID"] for t in T["AssociateTypes"]}
    rel = []
    for s in sorted(T["Associates"], key=lambda r: int(r["AssociateID"])):
        rel.append((s["AssociateID"], types["Contact"]))
        if s["Person_ID"] in dual:
            rel.append((s["AssociateID"], types["Candidate"]))
    new_rel = [{"AssociateRelationID": str(i), "AssociateID": a, "TypeID": t} for i, (a, t) in enumerate(rel, 1)]
    if [(r["AssociateID"], r["TypeID"]) for r in T["AssociateTypeRelation"]] != rel:
        T["AssociateTypeRelation"] = new_rel
        changed.add("AssociateTypeRelation")
        log.append(f"AssociateTypeRelation: rebuilt as {len(new_rel)} rows (one type per contact, no duplicates)")

    with open(edge_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["person_id", "associate_id", "emp_profile_id", "case", "why_it_is_valid"])
        for p in sorted(dual, key=int):
            w.writerow([p, next((s["AssociateID"] for s in T["Associates"] if s["Person_ID"] == p), ""),
                        next((e["Emp_ProfileID"] for e in T["Emp_Profile"] if e["Person_ID"] == p), ""),
                        "DUAL_ROLE_CONTACT_AND_CANDIDATE",
                        "A client contact who is also on the books as a candidate; common in recruitment, must be kept"])

    # ── 4. finance ────────────────────────────────────────────────────────────
    po_vendor = {p["PONo"]: p["VendorID"] for p in T["PONo"]}
    placements_of = defaultdict(list)
    for h in T["Req_Hired"]:
        if h["Pipeline_Stage"] == "Placed":
            placements_of[h["Account_ID"]].append(h["Req_HiredID"])
    inv_by_id = {i["InvoiceID"]: i for i in T["Invoice"]}
    lines = defaultdict(list)
    for e in T["InvoiceEntries"]:
        amt = round(int(e["Quantity"]) * float(e["Unit_Price"]), 2)
        setv("InvoiceEntries", e, "Amount", f"{amt:.2f}")
        inv = inv_by_id.get(e["Invoice_ID"])
        if inv:
            ps = placements_of.get(inv["Vendor_ID"])
            if e["Plac_ID"] and e["Plac_ID"] not in (ps or []):
                setv("InvoiceEntries", e, "Plac_ID", ps[int(e["Invoice_EntryID"]) % len(ps)] if ps else "")
        lines[e["Invoice_ID"]].append(amt)
    for inv in T["Invoice"]:
        if inv["PONo"] and po_vendor.get(inv["PONo"]) != inv["Vendor_ID"]:
            setv("Invoice", inv, "PONo", "")
        net = round(sum(lines[inv["InvoiceID"]]), 2) if lines.get(inv["InvoiceID"]) else round(float(inv["NETAmount"]), 2)
        gross = round(net * (1 + VAT_RATE), 2)
        paid = {"Paid": gross, "Cancelled": 0.0, "Draft": 0.0, "Sent": 0.0}.get(
            inv["Status"], round(gross * (int(inv["InvoiceID"]) % 5) / 10, 2))       # Overdue: 0-40% paid
        balance = 0.0 if inv["Status"] == "Cancelled" else round(gross - paid, 2)
        for col, v in (("SubTotal_Amount", net), ("NETAmount", net), ("Amount", gross),
                       ("Amount_Paid", paid), ("Balance_Due", balance), ("VAT", "20%")):
            setv("Invoice", inv, col, f"{v:.2f}" if isinstance(v, float) else v)
    log.append("Invoices: lines = qty x price, net = sum of lines, gross = net + 20% VAT, paid/balance follow status")

    # ── 5. formats ────────────────────────────────────────────────────────────
    n_ni = 0
    for e in T["Emp_Profile"]:
        ni = e["NI_number"]
        if ni and (not NI_RE.match(ni) or ni[:2] in NI_BANNED):
            k = int(e["Emp_ProfileID"])
            prefix = NI_FIRST[k % len(NI_FIRST)] + NI_SECOND[(k * 7) % len(NI_SECOND)]
            if prefix in NI_BANNED:
                prefix = "AB"
            digits = re.sub(r"\D", "", ni)[:6].ljust(6, "0")
            n_ni += setv("Emp_Profile", e, "NI_number", f"{prefix}{digits}{'ABCD'[k % 4]}")
    n_pc = 0
    for a in T["Addresses"]:
        if not POSTCODE_RE.match(a["ZipCode"] or ""):
            districts, _ = dg.CITY_STREETS.get(a["City"], dg.CITY_STREETS["London"])
            k = int(a["AddressID"])
            pc = f"{districts[k % len(districts)]} {k % 9 + 1}{dg.POSTCODE_LETTERS[k % 20]}{dg.POSTCODE_LETTERS[(k * 3) % 20]}"
            n_pc += setv("Addresses", a, "ZipCode", pc)
    log.append(f"Formats: {n_ni} invalid NI numbers and {n_pc} placeholder/invalid postcodes regenerated")

    # implausible dates of birth (under 16 / before 1940) -> a working-age year, same day and month
    n_dob = 0
    for p in T["Person"]:
        if p["DOB"] and not ("1940-01-01" <= p["DOB"] <= "2008-01-01"):
            n_dob += setv("Person", p, "DOB", f"{1960 + int(p['Person_ID']) % 40}{p['DOB'][4:]}".replace("-02-29", "-02-28"))
    # polymorphic Log.Entity_ID -> a real record of that entity type
    ids = {"Associate": sorted((s["AssociateID"] for s in T["Associates"]), key=int),
           "Account": sorted(accounts, key=int), "Person": sorted(persons, key=int),
           "Req": sorted(req_by_id, key=int), "Timesheet": sorted((t["ID"] for t in T["TimeSheets"]), key=int),
           "Invoice": sorted(inv_by_id, key=int)}
    id_sets = {k: set(v) for k, v in ids.items()}
    n_log = 0
    for lg in T["Log"]:
        pool = ids.get(lg["Entity_Type"])
        if pool and lg["Entity_ID"] and lg["Entity_ID"] not in id_sets[lg["Entity_Type"]]:
            n_log += setv("Log", lg, "Entity_ID", pool[int(lg["Entity_ID"]) % len(pool)])
    log.append(f"Dates/links: {n_dob} implausible DOBs fixed, {n_log} Log.Entity_ID values pointed at real records")

    # notes written about a job must be attached to one (the generator left every job note's ObjectId empty)
    reqs_of_acct = defaultdict(list)
    for r in sorted(T["Req"], key=lambda r: int(r["ReqID"])):
        reqs_of_acct[r["AccountID"]].append(r["ReqID"])
    brands = [(a["Account_ID"], w) for a in T["Accounts"] for w in [a["Account_name"].split()[0]] if len(w) >= 4]
    all_reqs = sorted(req_by_id, key=int)
    n_notes = 0
    for nt in T["Notes"]:
        if nt["ObjectType"] == "Req" and not nt["ObjectId"]:
            hit = next((acct for acct, w in brands if re.search(rf"\b{re.escape(w)}\b", nt["Notetext"]) and reqs_of_acct.get(acct)), None)
            pool = reqs_of_acct[hit] if hit else all_reqs
            n_notes += setv("Notes", nt, "ObjectId", pool[int(nt["Note_ID"]) % len(pool)])
    # the same job raised twice (same client, title, type and start) -> the later one is a separate, senior role
    seen_jobs, n_jobs = set(), 0
    for r in sorted(T["Req"], key=lambda r: int(r["ReqID"])):
        k = (r["AccountID"], r["Req_Title"].lower(), r["Worktype"], r["StartDate"][:10])
        if k in seen_jobs:
            n_jobs += setv("Req", r, "Req_Title", ("Senior " + r["Req_Title"])[:50])
        seen_jobs.add((r["AccountID"], r["Req_Title"].lower(), r["Worktype"], r["StartDate"][:10]))
    log.append(f"Links: {n_notes} job notes attached to a job, {n_jobs} duplicate job(s) made distinct")

    # every candidate is linked to a job: candidates the generator left without any application get one
    # ("Applied", no dates yet) to an open job; client, contact and work type follow the job
    recruiters = sorted((r["RecruiterID"] for r in T["Recruiter"]), key=int)
    applied = {h["Invoiced_PersonID"] for h in T["Req_Hired"] if h["Invoiced_PersonID"]}
    open_jobs = [r for r in sorted(T["Req"], key=lambda r: int(r["ReqID"]))
                 if r["Deleted"] == "0" and r["StatusText"] in ("Open", "Interviewing")]
    next_id = max(int(h["Req_HiredID"]) for h in T["Req_Hired"]) + 1
    n_apps = 0
    for p in sorted(T["Person"], key=lambda p: int(p["Person_ID"])):
        if p["Person_ID"] in contact_set or p["Person_ID"] in applied or not open_jobs:
            continue
        k = int(p["Person_ID"])
        job = open_jobs[k % len(open_jobs)]
        contact = job["AssociateID"] if account_of.get(job["AssociateID"]) == job["AccountID"] else ""
        created = max(job["CreatedAt"][:10], "2024-01-01") + " 09:00:00"
        T["Req_Hired"].append({
            "Req_HiredID": str(next_id), "Account_ID": job["AccountID"], "Associate_ID": contact, "Req_ID": job["ReqID"],
            "Worktype": job["Worktype"], "StartDate": "", "EndDate": "", "Burden": "", "Invoiced_PersonID": p["Person_ID"],
            "Pipeline_Stage": "Applied", "RateID": "", "CurrencyCode": "GBP", "CurrencyID": "1",
            "Source": ["Direct", "LinkedIn", "Job Board", "Referral"][k % 4], "FeeValue": "0",
            "Owner_ID": recruiters[k % len(recruiters)], "Second_OwnerID": "", "Reason_ID": "", "Hired_Status": "0",
            "Deleted": "0", "CreatedBy": recruiters[k % len(recruiters)], "UpdatedBy": recruiters[(k + 3) % len(recruiters)],
            "CreatedAt": created})
        changed.add("Req_Hired")
        next_id += 1
        n_apps += 1
    if n_apps:
        log.append(f"Candidates: {n_apps} without any job given an 'Applied' application to an open job")

    # ── 6. soft deletes ───────────────────────────────────────────────────────
    live_children = {h["Req_ID"] for h in T["Req_Hired"] if h["Deleted"] == "0"}
    n_sd = sum(setv("Req", r, "Deleted", 0) for r in T["Req"] if r["Deleted"] == "1" and r["ReqID"] in live_children)
    open_jobs = {r["AccountID"] for r in T["Req"] if r["Deleted"] == "0" and r["StatusText"] in ("Open", "Interviewing", "Offer Made")}
    n_sd += sum(setv("Accounts", a, "Deleted", 0) for a in T["Accounts"] if a["Deleted"] == "1" and a["Account_ID"] in open_jobs)
    deleted_people = {p["Person_ID"] for p in T["Person"] if p["Deleted"] == "1"}
    n_sd += sum(setv("Associates", s, "Active", 0) for s in T["Associates"] if s["Person_ID"] in deleted_people and s["Active"] == "1")
    log.append(f"Soft deletes: {n_sd} conflicts resolved (deleted parent with live children)")

    # ── employment history: a real career per candidate (the generator gave every row the same title and dates) ──
    ROLES = [  # keyword in the profile note -> role title (first match wins)
        ("business analyst", "Business Analyst"), ("finance systems", "Finance Systems Analyst"), ("data analyst", "Data Analyst"),
        ("data engineer", "Data Engineer"), ("python/ml", "Machine Learning Engineer"), ("python", "Python Developer"),
        ("qa lead", "QA Engineer"), ("qa", "QA Automation Engineer"), ("test", "Test Analyst"), ("frontend", "Front-end Developer"),
        ("full-stack", "Full Stack Developer"), ("mobile", "Mobile Developer"), ("c++", "C++ Engineer"), ("c#", "C# Developer"),
        (".net", ".NET Developer"), ("java", "Java Developer"), ("devops", "DevOps Engineer"), ("cloud architect", "Cloud Architect"),
        ("aws", "Cloud Infrastructure Engineer"), ("infrastructure", "Infrastructure Engineer"), ("project manager", "Project Manager"),
        ("scrum", "Scrum Master"), ("dba", "Database Administrator"), ("sql", "SQL Developer"), ("security", "Security Analyst"),
        ("network", "Network Engineer"), ("support", "IT Support Analyst"), ("developer", "Software Developer"), ("dev", "Software Developer"),
    ]

    def base_role(note: str) -> str:
        text = (note or "").split(" - ", 1)[-1].split(".")[0].lower()
        return next((title for key, title in ROLES if key in text), "Software Developer")

    def ladder(role: str, n: int, note: str) -> list[str]:
        """n titles, oldest first, ending at the candidate's current level (from the note: graduate / senior / lead)."""
        levels = [f"Junior {role}", role, f"Senior {role}", f"Lead {role}", f"Principal {role}"]
        text = (note or "").lower()
        top = 0 if "graduate" in text or "first role" in text else 3 if re.search(r"lead|architect|principal", text)             else 2 if re.search(r"senior|1[0-9]\s*yrs|20\s*yrs|[6-9]\s*yrs", text) else 1
        return [levels[max(0, top - (n - 1 - k))] for k in range(n)]

    profile_note = {e["Emp_ProfileID"]: e["Profile_Notes"] for e in T["Emp_Profile"]}
    by_emp = defaultdict(list)
    for h in T["EmpHist"]:
        by_emp[h["Emp_ID"]].append(h)
    n_hist = 0
    for emp, rows in sorted(by_emp.items(), key=lambda kv: int(kv[0])):
        rows.sort(key=lambda h: int(h["Hist_ID"]))
        note = profile_note.get(emp, "")
        titles = ladder(base_role(note), len(rows), note)
        current = rows[-1]["Ended_At"] == ""
        end = date(2024, rng.randint(1, 12), 1) if not current else None
        start_next = date(2024, 9, 1) if current else end
        spans = []
        for _ in rows:                      # newest first: each job 1-4 years, short gaps between jobs
            start = date(start_next.year - rng.randint(1, 4), rng.randint(1, 12), 1)
            spans.append((start, start_next))
            start_next = date(start.year, start.month, 1) - timedelta(days=rng.choice([0, 0, 31, 62]))
        spans.reverse()
        for k, (h, (st, en)) in enumerate(zip(rows, spans)):
            last = k == len(rows) - 1
            n_hist += setv("EmpHist", h, "Title", titles[k])
            n_hist += setv("EmpHist", h, "Started_At", f"{st.isoformat()} 00:00:00")
            n_hist += setv("EmpHist", h, "Ended_At", "" if last and current else f"{(en - timedelta(days=1)).isoformat()} 00:00:00")
    log.append(f"Careers: {len(by_emp)} candidates given a career history ({n_hist} values)")

    # ── candidate contact details: a home address, email and mobile for every candidate ──
    # (separate rng so the values are the same on every rebuild, whatever ran before)
    crng = random.Random(SEED + 7)
    TOWNS = [  # city, county, postcode districts, lat, long
        ("London", "Greater London", ["N4", "SE15", "E17", "SW11", "NW6", "W12"], 51.507, -0.128),
        ("Manchester", "Greater Manchester", ["M14", "M20", "M21", "M4"], 53.480, -2.243),
        ("Leeds", "West Yorkshire", ["LS6", "LS8", "LS17", "LS27"], 53.800, -1.549),
        ("Birmingham", "West Midlands", ["B13", "B15", "B29", "B17"], 52.486, -1.890),
        ("Bristol", "Bristol", ["BS6", "BS7", "BS3"], 51.454, -2.588),
        ("Glasgow", "Glasgow City", ["G12", "G41", "G3"], 55.864, -4.252),
        ("Edinburgh", "City of Edinburgh", ["EH6", "EH10", "EH9"], 55.953, -3.188),
        ("Sheffield", "South Yorkshire", ["S7", "S10", "S11"], 53.381, -1.470),
        ("Nottingham", "Nottinghamshire", ["NG5", "NG7", "NG9"], 52.954, -1.158),
        ("Liverpool", "Merseyside", ["L15", "L17", "L18"], 53.408, -2.991),
        ("Newcastle upon Tyne", "Tyne and Wear", ["NE2", "NE6", "NE3"], 54.978, -1.617),
        ("Cardiff", "Cardiff", ["CF5", "CF14", "CF24"], 51.481, -3.179),
        ("Reading", "Berkshire", ["RG1", "RG4", "RG30"], 51.454, -0.978),
        ("Cambridge", "Cambridgeshire", ["CB1", "CB4"], 52.205, 0.122),
        ("Brighton", "East Sussex", ["BN1", "BN2", "BN3"], 50.822, -0.137),
    ]
    STREETS = ["Victoria Road", "Church Lane", "Park Avenue", "Station Road", "Mill Lane", "Grange Road", "Albert Street",
               "Queens Road", "Kingsway", "Elm Grove", "Willow Close", "Highfield Road", "Clarendon Road", "Manor Way",
               "Beech Avenue", "Orchard Street", "Hamilton Road", "Westbourne Grove", "St John's Road", "Belmont Street"]
    PROVIDERS = ["gmail.com", "outlook.com", "yahoo.co.uk", "hotmail.co.uk", "icloud.com", "btinternet.com"]
    LETTERS = "ABDEFGHJLNPQRSTUWXYZ"
    import unicodedata

    def ascii_name(x: str) -> str:
        x = unicodedata.normalize("NFKD", x or "").encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z]", "", x.lower())

    contact_people = {a["Person_ID"] for a in T["Associates"] if a["Person_ID"]}
    addr_by_id = {a["AddressID"]: a for a in T["Addresses"]}
    next_addr = max(int(a["AddressID"]) for a in T["Addresses"]) + 1
    n_new = n_upd = 0
    for p in sorted(T["Person"], key=lambda r: int(r["Person_ID"])):
        if p["Person_ID"] in contact_people:
            continue
        city, county, districts, lat, lon = crng.choice(TOWNS)
        fn, ln = ascii_name(p["First_Name"]), ascii_name(p["Last_Name"])
        style = crng.randint(0, 3)
        local = [f"{fn}.{ln}", f"{fn}{ln}", f"{fn[:1]}{ln}", f"{fn}.{ln}{crng.randint(1, 99)}"][style]
        values = {
            "Address_line1": f"{crng.randint(1, 180)} {crng.choice(STREETS)}",
            "Address_line2": crng.choice(["", "", "", f"Flat {crng.randint(1, 24)}"]),
            "City": city, "ZipCode": f"{crng.choice(districts)} {crng.randint(1, 9)}{crng.choice(LETTERS)}{crng.choice(LETTERS)}",
            "Province": county, "Country": "United Kingdom",
            "Email": f"{local}@{crng.choice(PROVIDERS)}",
            "Phone": f"+44 7{crng.randint(400, 999)} {crng.randint(100000, 999999)}",
            "OtherPhone": "", "WorkPhone": "",
            "Longitude": f"{lon + crng.uniform(-0.05, 0.05):.6f}", "Latitude": f"{lat + crng.uniform(-0.04, 0.04):.6f}",
            "CreatedAt": p["CreatedAt"], "CreatedBy": p["CreatedBy"],
        }
        aid = p.get("AddressID") or ""
        if aid and aid in addr_by_id:
            row = addr_by_id[aid]
            n_upd += sum(setv("Addresses", row, k, v) for k, v in values.items())
        else:
            row = {"AddressID": str(next_addr), **values}
            next_addr += 1
            T["Addresses"].append(row)
            addr_by_id[row["AddressID"]] = row
            changed.add("Addresses")
            setv("Person", p, "AddressID", row["AddressID"])
            n_new += 1
    log.append(f"Candidates: {n_new} home addresses with email and mobile added ({n_upd} values refreshed)")

    for t in sorted(changed):
        write_csv(t, T[t], columns[t])
    return log
