"""
mapping/tiers.py

The migration as traditional T-SQL: two layers of INSERT ... SELECT scripts.

    Cobaltdesk_Legacy  --(middle)-->  Migration_Staging.mid.<Entity>  --(target)-->  RecruitPlatform_Target.dbo.<Table>

    sql/middle/00_create.sql, NN_<entity>.sql      source -> middle tier (canonical layer)
    sql/load/00_create.sql,   NN_<table>.sql       middle tier -> target

Every field is one expression. A developer can override any of them from the UI; overrides are kept in
mapping/field_overrides.json and applied when the scripts are written and run.

Run
    python mapping/tiers.py               # write both layers' scripts
    python mapping/tiers.py --run         # write + run middle, then target, on localhost\\SQLEXPRESS
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
SERVER = r"localhost\SQLEXPRESS"
SOURCE_DB, STAGING_DB, TARGET_DB = "Cobaltdesk_Legacy", "Migration_Staging", "RecruitPlatform_Target"
OVERRIDES_FILE = Path(__file__).resolve().parent / "field_overrides.json"


@dataclass
class Check:
    """A condition each row must meet. 'reject': rows that fail are not loaded and are logged in
    MigrationRejects; 'flag': rows that fail are loaded and logged."""
    cond: str
    reason: str
    action: str = "reject"


@dataclass
class Insert:
    source: str                                  # FROM clause; {src} = the layer's source prefix
    columns: dict[str, str]                      # output column -> expression
    joins: list[str] = field(default_factory=list)
    where: str = ""
    checks: list[Check] = field(default_factory=list)


@dataclass
class Entity:
    key: str
    table: str
    label: str
    inserts: list[Insert]
    types: dict[str, str] | None = None          # middle tier: column types (target tables come from Target Schema.csv)


@dataclass
class Layer:
    name: str
    db: str
    schema: str
    src: str                                     # prefix for source tables
    out: Path
    entities: list[Entity]

    def entity(self, key: str) -> Entity:
        return next(e for e in self.entities if e.key == key)


T, TL, ID, DT, D, M, B = "NVARCHAR(200)", "NVARCHAR(MAX)", "NVARCHAR(50)", "DATETIME2(0)", "DATE", "DECIMAL(12,2)", "BIT"

# ── source -> middle tier ────────────────────────────────────────────────────
MIDDLE = Layer("middle", STAGING_DB, "mid", f"{SOURCE_DB}.dbo.", ROOT / "sql" / "middle", [
    Entity("users", "Users", "Users", [Insert("{src}Recruiter r", {
        "user_id": "r.RecruiterID",
        "first_name": "LEFT(r.Fullname, CHARINDEX(' ', r.Fullname + ' ') - 1)",
        "last_name": "NULLIF(LTRIM(SUBSTRING(r.Fullname, CHARINDEX(' ', r.Fullname + ' ') + 1, 200)), '')",
        "email": "r.email",
        "role": "LOWER(ro.Description)",
        "office": "NULL",
        "is_active": "1",
    }, joins=["LEFT JOIN {src}Roles ro ON ro.Role_ID = r.Role_ID"])],
        {"user_id": ID, "first_name": T, "last_name": T, "email": T, "role": T, "office": T, "is_active": B}),

    Entity("clients", "Clients", "Clients", [Insert("{src}Accounts a", {
        "client_id": "a.Account_ID",
        "company_name": "a.Account_name",
        "industry": "a.Industry",
        "website": "a.Website",
        "phone": "COALESCE(ad.WorkPhone, ad.Phone)",
        "address_line_1": "ad.Address_line1",
        "address_line_2": "ad.Address_line2",
        "city": "ad.City",
        "postcode": "ad.ZipCode",
        "country": "ad.Country",
        "status": "CASE WHEN a.Deleted = 1 THEN 'deleted' ELSE LOWER(st.Description) END",
        "owner_user_id": "a.CreatedBy",
        "created_at": "a.CreatedAt",
    }, joins=["LEFT JOIN {src}Addresses ad ON ad.AddressID = a.AddressID",
              "LEFT JOIN {src}AccountStatus st ON st.Account_StatusID = a.AccountStatusTypeID"])],
        {"client_id": ID, "company_name": T, "industry": T, "website": T, "phone": T, "address_line_1": T, "address_line_2": T,
         "city": T, "postcode": T, "country": T, "status": T, "owner_user_id": ID, "created_at": DT}),

    Entity("contacts", "Contacts", "Contacts", [Insert("{src}Associates s", {
        "contact_id": "s.AssociateID",
        "client_id": "co.AccountID",
        "first_name": "p.First_Name",
        "last_name": "p.Last_Name",
        "job_title": "s.Associate_Tag",
        "email": "ad.Email",
        "phone": "ad.WorkPhone",
        "mobile": "ad.Phone",
        "status": "CASE WHEN s.Active = 1 THEN 'active' ELSE 'inactive' END",
        "owner_user_id": "s.CreatedBy",
        "created_at": "s.CreatedAt",
    }, joins=["LEFT JOIN {src}Person p ON p.Person_ID = s.Person_ID",
              "LEFT JOIN {src}Addresses ad ON ad.AddressID = s.Associate_AddressID",
              "OUTER APPLY (SELECT MIN(aa.AccountID) AS AccountID FROM {src}AccountAssociates aa WHERE aa.AssociateID = s.AssociateID) co"])],
        {"contact_id": ID, "client_id": ID, "first_name": T, "last_name": T, "job_title": T, "email": T, "phone": T, "mobile": T,
         "status": T, "owner_user_id": ID, "created_at": DT}),

    Entity("candidates", "Candidates", "Candidates", [Insert("{src}Person p", {
        "candidate_id": "p.Person_ID",
        "first_name": "p.First_Name",
        "last_name": "p.Last_Name",
        "email": "ad.Email",
        "mobile": "ad.Phone",
        "phone": "NULLIF(ad.OtherPhone, '')",
        "current_job_title": "cj.Title",
        "current_employer": "cj.PlaceofWork",
        "address_line_1": "ad.Address_line1",
        "address_line_2": "NULLIF(ad.Address_line2, '')",
        "city": "ad.City",
        "postcode": "ad.ZipCode",
        "country": "ad.Country",
        "source": "LOWER(lh.Source)",
        "status": "LOWER(lh.Pipeline_Stage)",
        "linkedin_url": "NULL",
        "owner_user_id": "p.CreatedBy",
        "created_at": "p.CreatedAt",
    }, joins=["LEFT JOIN {src}Addresses ad ON ad.AddressID = p.AddressID",
              "OUTER APPLY (SELECT TOP 1 eh.Title, eh.PlaceofWork FROM {src}EmpHist eh\n"
              "             JOIN {src}Emp_Profile ep ON ep.Emp_ProfileID = eh.Emp_ID\n"
              "             WHERE ep.Person_ID = p.Person_ID ORDER BY eh.Started_At DESC) cj",
              "OUTER APPLY (SELECT TOP 1 h.Source, h.Pipeline_Stage FROM {src}Req_Hired h\n"
              "             WHERE h.Invoiced_PersonID = p.Person_ID ORDER BY h.CreatedAt DESC, h.Req_HiredID DESC) lh"],
       where="NOT EXISTS (SELECT 1 FROM {src}Associates s WHERE s.Person_ID = p.Person_ID)")],
        {"candidate_id": ID, "first_name": T, "last_name": T, "email": T, "mobile": T, "phone": T, "current_job_title": T,
         "current_employer": T, "address_line_1": T, "address_line_2": T, "city": T, "postcode": T, "country": T, "source": T,
         "status": T, "linkedin_url": T, "owner_user_id": ID, "created_at": DT}),

    Entity("jobs", "Jobs", "Jobs", [Insert("{src}Req r", {
        "job_id": "r.ReqID",
        "client_id": "r.AccountID",
        "contact_id": "r.AssociateID",
        "title": "r.Req_Title",
        "employment_type": "LOWER(r.Worktype)",
        "salary_min": "rt.Salary",
        "salary_max": "NULL",
        "rate": "rt.BillRate",
        "rate_unit": "CASE WHEN rt.BillRate IS NOT NULL THEN 'day' END",
        "location": "ad.City",
        "status": "CASE WHEN r.Deleted = 1 THEN 'deleted' ELSE LOWER(r.StatusText) END",
        "owner_user_id": "r.CreatedBy",
        "opened_at": "CAST(r.StartDate AS DATE)",
        "closed_at": "CAST(r.EndDate AS DATE)",
        "description": "r.Req_Description",
    }, joins=["OUTER APPLY (SELECT TOP 1 rr.BillRate, rr.Salary FROM {src}Req_Rates rr WHERE rr.Req_ID = r.ReqID ORDER BY rr.Req_RateID) rt",
              "LEFT JOIN {src}Addresses ad ON ad.AddressID = r.Address_ID"])],
        {"job_id": ID, "client_id": ID, "contact_id": ID, "title": T, "employment_type": T, "salary_min": M, "salary_max": M,
         "rate": M, "rate_unit": T, "location": T, "status": T, "owner_user_id": ID, "opened_at": D, "closed_at": D,
         "description": TL}),

    Entity("placements", "Placements", "Placements", [Insert("{src}Req_Hired h", {
        "placement_id": "h.Req_HiredID",
        "candidate_id": "h.Invoiced_PersonID",
        "job_id": "h.Req_ID",
        "start_date": "CAST(h.StartDate AS DATE)",
        "end_date": "CAST(h.EndDate AS DATE)",
        "salary": "NULL",
        "fee": "h.FeeValue",
        "placement_type": "LOWER(h.Worktype)",
        "owner_user_id": "h.Owner_ID",
    }, where="h.Pipeline_Stage = 'Placed'")],
        {"placement_id": ID, "candidate_id": ID, "job_id": ID, "start_date": D, "end_date": D, "salary": M, "fee": M,
         "placement_type": T, "owner_user_id": ID}),

    Entity("notes", "Notes", "Notes", [Insert("{src}Notes n", {
        "note_id": "n.Note_ID",
        "entity_type": "CASE n.ObjectType WHEN 'Person' THEN CASE WHEN pc.AssociateID IS NOT NULL THEN 'contact' ELSE 'candidate' END WHEN 'Associate' THEN 'contact' WHEN 'Req' THEN 'job' WHEN 'Account' THEN 'client' END",
        "entity_id": "CASE WHEN n.ObjectType = 'Person' AND pc.AssociateID IS NOT NULL THEN CAST(pc.AssociateID AS NVARCHAR(50)) ELSE CAST(n.ObjectId AS NVARCHAR(50)) END",
        "author_user_id": "n.CreatedBy",
        "note_type": "NULL",
        "body": "n.Notetext",
        "created_at": "n.CreatedAt",
    }, joins=["OUTER APPLY (SELECT MIN(s.AssociateID) AS AssociateID FROM {src}Associates s WHERE n.ObjectType = 'Person' AND s.Person_ID = n.ObjectId) pc"])], {"note_id": ID, "entity_type": T, "entity_id": ID, "author_user_id": ID, "note_type": T, "body": TL, "created_at": DT}),

    Entity("histories", "Histories", "Histories", [Insert("{src}Log l", {
        "history_id": "l.LogID",
        "entity_type": "LOWER(l.Entity_Type)",
        "entity_id": "l.Entity_ID",
        "field_changed": "l.Action",
        "old_value": "NULL",
        "new_value": "NULL",
        "changed_by": "l.User_ID",
        "changed_at": "l.Timestamp",
    })], {"history_id": ID, "entity_type": T, "entity_id": ID, "field_changed": T, "old_value": TL, "new_value": TL,
          "changed_by": ID, "changed_at": DT}),

    Entity("activities", "Activities", "Activities", [Insert("{src}Schedule sc", {
        "activity_id": "sc.Schedule_ID",
        "activity_type": "sc.ScheduleType",
        "candidate_id": "CASE WHEN sc.Person_Type = 'Candidate' THEN sc.Person_ID END",
        "contact_id": "CASE WHEN sc.Person_Type = 'Contact' THEN ct.AssociateID END",
        "job_id": "sc.Req_ID",
        "user_id": "sc.CreatedBy",
        "occurred_at": "sc.StartDate",
        "outcome": "NULL",
        "subject": "sc.Notes",
    }, joins=["OUTER APPLY (SELECT MIN(s.AssociateID) AS AssociateID FROM {src}Associates s WHERE s.Person_ID = sc.Person_ID) ct"])],
        {"activity_id": ID, "activity_type": T, "candidate_id": ID, "contact_id": ID, "job_id": ID, "user_id": ID,
         "occurred_at": DT, "outcome": T, "subject": TL}),

    Entity("documents", "Documents", "Documents", [
        Insert("{src}Documents d", {
            "document_id": "'D' + CAST(d.Doc_ID AS NVARCHAR(20))",
            "entity_type": "CASE d.ObjectType WHEN 'Person' THEN CASE WHEN pc.AssociateID IS NOT NULL THEN 'contact' ELSE 'candidate' END WHEN 'Associate' THEN 'contact' WHEN 'Req' THEN 'job' WHEN 'Account' THEN 'client' END",
            "entity_id": "CASE WHEN d.ObjectType = 'Person' AND pc.AssociateID IS NOT NULL THEN CAST(pc.AssociateID AS NVARCHAR(50)) ELSE CAST(d.Doc_AssocID AS NVARCHAR(50)) END",
            "file_name": "RIGHT(d.Path, CHARINDEX('/', REVERSE(d.Path)) - 1)",
            "file_type": "LOWER(RIGHT(d.Path, CHARINDEX('.', REVERSE(d.Path)) - 1))",
            "storage_path": "d.Path",
            "uploaded_at": "d.CreatedAt",
        }, joins=["OUTER APPLY (SELECT MIN(s.AssociateID) AS AssociateID FROM {src}Associates s WHERE d.ObjectType = 'Person' AND s.Person_ID = d.Doc_AssocID) pc"]),
        Insert("{src}CV_Docs c", {
            "document_id": "'CV' + CAST(c.Doc_ID AS NVARCHAR(20))",
            "entity_type": "'candidate'",
            "entity_id": "c.CV_AssocID",
            "file_name": "RIGHT(c.Path, CHARINDEX('/', REVERSE(c.Path)) - 1)",
            "file_type": "LOWER(RIGHT(c.Path, CHARINDEX('.', REVERSE(c.Path)) - 1))",
            "storage_path": "c.Path",
            "uploaded_at": "c.CreatedAt",
        }),
    ], {"document_id": ID, "entity_type": T, "entity_id": ID, "file_name": T, "file_type": T, "storage_path": T, "uploaded_at": DT}),
    Entity("departments", "Departments", "Departments", [Insert("{src}Departments d", {
        "department_id": "d.DepartmentID",
        "name": "d.Name",
        "deleted": "d.Deleted",
        "created_at": "d.CreatedAt",
        "updated_at": "d.UpdatedAt",
    })], {"department_id": ID, "name": T, "deleted": B, "created_at": DT, "updated_at": DT}),

    Entity("skill_categories", "SkillCategories", "Skill categories", [Insert("{src}SkillCategory sc", {
        "category_id": "sc.CategoryID",
        "name": "sc.Name",
        "deleted": "sc.Deleted",
    })], {"category_id": ID, "name": T, "deleted": B}),

    Entity("skills", "Skills", "Skills", [Insert("{src}Skills sk", {
        "skill_id": "sk.SkillID",
        "name": "sk.SkillName",
        "category_id": "sk.Skill_CategoryID",
        "deleted": "sk.Deleted",
    })], {"skill_id": ID, "name": T, "category_id": ID, "deleted": B}),

    Entity("applications", "Applications", "Applications", [Insert("{src}Req_Hired h", {
        "application_id": "h.Req_HiredID",
        "candidate_id": "h.Invoiced_PersonID",
        "job_id": "h.Req_ID",
        "client_id": "h.Account_ID",
        "contact_id": "h.Associate_ID",
        "stage": "LOWER(h.Pipeline_Stage)",
        "employment_type": "LOWER(h.Worktype)",
        "start_date": "CAST(h.StartDate AS DATE)",
        "end_date": "CAST(h.EndDate AS DATE)",
        "fee": "h.FeeValue",
        "source": "LOWER(h.Source)",
        "owner_user_id": "h.Owner_ID",
        "deleted": "h.Deleted",
        "applied_at": "h.CreatedAt",
    })], {"application_id": ID, "candidate_id": ID, "job_id": ID, "client_id": ID, "contact_id": ID, "stage": T,
          "employment_type": T, "start_date": D, "end_date": D, "fee": M, "source": T, "owner_user_id": ID, "deleted": B,
          "applied_at": DT}),

    Entity("interviews", "Interviews", "Interviews", [Insert("{src}Interview_Feedback f", {
        "interview_id": "f.Interview_FeedbackID",
        "candidate_id": "f.Interviewee_ID",
        "interviewer_person_id": "f.Interviewer_ID",
        "interview_date": "f.Interview_Date",
        "feedback": "f.Notes",
        "callback": "f.Callback",
        "created_at": "f.CreatedAt",
    })], {"interview_id": ID, "candidate_id": ID, "interviewer_person_id": ID, "interview_date": DT, "feedback": TL,
          "callback": T, "created_at": DT}),

    Entity("work_history", "WorkHistory", "Work history", [Insert("{src}EmpHist eh", {
        "history_id": "eh.Hist_ID",
        "candidate_id": "ep.Person_ID",
        "employer": "eh.PlaceofWork",
        "job_title": "eh.Title",
        "start_date": "CAST(eh.Started_At AS DATE)",
        "end_date": "CAST(eh.Ended_At AS DATE)",
        "deleted": "eh.Deleted",
    }, joins=["JOIN {src}Emp_Profile ep ON ep.Emp_ProfileID = eh.Emp_ID"])],
        {"history_id": ID, "candidate_id": ID, "employer": T, "job_title": T, "start_date": D, "end_date": D, "deleted": B}),

    Entity("references", "References", "References", [Insert("{src}EmpRef er", {
        "reference_id": "er.EmpRef_ID",
        "candidate_id": "ep.Person_ID",
        "full_name": "rf.Fullname",
        "job_title": "rf.Job_Title",
        "company": "rf.Company",
        "relationship": "er.Relationship",
        "email": "rf.email",
        "phone": "rf.Telephone",
        "status": "er.Status",
        "reference_text": "er.Reference",
        "created_at": "er.CreatedAt",
        "updated_at": "er.UpdatedAt",
    }, joins=["JOIN {src}Referees rf ON rf.Referee_ID = er.Ref_ID",
              "JOIN {src}Emp_Profile ep ON ep.Emp_No = er.EmpNo"])],
        {"reference_id": ID, "candidate_id": ID, "full_name": T, "job_title": T, "company": T, "relationship": T, "email": T,
         "phone": T, "status": T, "reference_text": TL, "created_at": DT, "updated_at": DT}),

    Entity("candidate_profiles", "CandidateProfiles", "Candidate profiles", [Insert("{src}Emp_Profile ep", {
        "profile_id": "ep.Emp_ProfileID",
        "candidate_id": "ep.Person_ID",
        "employment_type": "ep.Emp_TypeDescription",
        "notes": "ep.Profile_Notes",
        "bank": "ep.BankDetails",
        "sort_code": "ep.SortCode",
        "added_by": "ep.CreatedBy",
        "created_at": "ep.CreatedAt",
        "updated_at": "ep.UpdatedAt",
    })], {"profile_id": ID, "candidate_id": ID, "employment_type": T, "notes": TL, "bank": T, "sort_code": T,
          "added_by": ID, "created_at": DT, "updated_at": DT}),

    Entity("consents", "Consents", "Marketing consent", [Insert("{src}GDPR_Consent g", {
        "consent_id": "g.GDPR_ConsentID",
        "person_id": "g.Person_ID",
        "email_ok": "g.Email",
        "phone_ok": "g.Phone",
        "text_ok": "g.Text",
        "added_by": "g.CreatedBy",
        "created_at": "g.CreatedAt",
        "updated_at": "g.UpdatedAt",
    })], {"consent_id": ID, "person_id": ID, "email_ok": B, "phone_ok": B, "text_ok": B, "added_by": ID,
          "created_at": DT, "updated_at": DT}),

    Entity("timesheets", "Timesheets", "Timesheets", [Insert("{src}TimeSheets t", {
        "timesheet_id": "t.ID",
        "po_no": "t.PONo",
        "timesheet_type": "tt.[Desc]",
        "pay_rate": "t.Payrate",
        "charge_rate": "t.Billrate",
        "start_date": "CAST(t.StartDate AS DATE)",
        "end_date": "CAST(t.Enddate AS DATE)",
        "status": "LOWER(t.Status)",
        "approved_by": "t.Approved_By",
        "approved_at": "t.Approved_Date",
    }, joins=["LEFT JOIN {src}TimesheetType tt ON tt.Timesheet_TypeID = t.Timesheet_TypeID"])],
        {"timesheet_id": ID, "po_no": ID, "timesheet_type": T, "pay_rate": M, "charge_rate": M, "start_date": D,
         "end_date": D, "status": T, "approved_by": ID, "approved_at": DT}),

    Entity("timesheet_lines", "TimesheetLines", "Timesheet lines", [Insert("{src}TimesheetItems i", {
        "line_id": "i.ItemID",
        "timesheet_id": "i.Timesheet_ID",
        "candidate_id": "i.Person_ID",
        "job_id": "i.Req_ID",
        "line_type": "tt.[Desc]",
        "start_time": "i.StartTime",
        "end_time": "i.EndTime",
        "hours": "i.TotalHours",
        "added_by": "i.CreatedBy",
        "created_at": "i.CreatedAt",
    }, joins=["LEFT JOIN {src}TimesheetType tt ON tt.Timesheet_TypeID = i.Timesheet_TypeID"])],
        {"line_id": ID, "timesheet_id": ID, "candidate_id": ID, "job_id": ID, "line_type": T, "start_time": T,
         "end_time": T, "hours": M, "added_by": ID, "created_at": DT}),

    Entity("purchase_orders", "PurchaseOrders", "Purchase orders", [Insert("{src}PONo po", {
        "po_no": "po.PONo",
        "client_id": "po.VendorID",
        "job_id": "po.ReqID",
        "department_id": "po.DepartmentID",
        "status": "LOWER(po.POStatus)",
        "issue_date": "CAST(po.Issue_Date AS DATE)",
        "due_date": "CAST(po.DateDue AS DATE)",
        "currency": "po.Currency",
        "amount": "po.Amount",
        "tax_amount": "po.TaxAmount",
        "description": "po.[Desc]",
        "added_by": "po.CreatedBy",
        "created_at": "po.CreatedAt",
    })], {"po_no": ID, "client_id": ID, "job_id": ID, "department_id": ID, "status": T, "issue_date": D, "due_date": D,
          "currency": T, "amount": M, "tax_amount": M, "description": T, "added_by": ID, "created_at": DT}),

    Entity("invoices", "Invoices", "Invoices", [Insert("{src}Invoice inv", {
        "invoice_id": "inv.InvoiceID",
        "invoice_no": "inv.Invoice_No",
        "po_no": "inv.PONo",
        "client_id": "inv.Vendor_ID",
        "invoice_type": "it.Type_Name",
        "status": "LOWER(inv.Status)",
        "currency": "inv.Currency",
        "net_amount": "inv.NETAmount",
        "vat_amount": "inv.Amount - inv.NETAmount",
        "gross_amount": "inv.Amount",
        "invoice_date": "CAST(inv.InvoiceDate AS DATE)",
        "due_date": "CAST(inv.DateDue AS DATE)",
        "description": "inv.[Desc]",
        "added_by": "inv.CreatedBy",
    }, joins=["LEFT JOIN {src}InvoiceTypes it ON it.InvoiceType_ID = inv.InvoiceType_ID"])],
        {"invoice_id": ID, "invoice_no": T, "po_no": ID, "client_id": ID, "invoice_type": T, "status": T, "currency": T,
         "net_amount": M, "vat_amount": M, "gross_amount": M, "invoice_date": D, "due_date": D, "description": T, "added_by": ID}),

    Entity("invoice_lines", "InvoiceLines", "Invoice lines", [Insert("{src}InvoiceEntries ie", {
        "line_id": "ie.Invoice_EntryID",
        "invoice_id": "ie.Invoice_ID",
        "placement_id": "ie.Plac_ID",
        "description": "ie.[Desc]",
        "quantity": "ie.Quantity",
        "unit_price": "ie.Unit_Price",
        "amount": "ie.Amount",
        "created_at": "ie.CreatedAt",
    })], {"line_id": ID, "invoice_id": ID, "placement_id": ID, "description": T, "quantity": M, "unit_price": M,
          "amount": M, "created_at": DT}),

    Entity("leads", "Leads", "Leads", [Insert("{src}Leads ld", {
        "lead_id": "ld.Lead_ID",
        "full_name": "ld.Name",
        "title": "ld.Lead_Name",
        "status": "ld.Lead_Status",
        "source": "ld.Lead_Source",
        "client_id": "ld.Account_ID",
        "contact_id": "ld.Associate_ID",
        "job_id": "ld.Req_ID",
        "email": "ld.Email",
        "phone": "ld.Phone",
        "note": "ld.Note",
        "assigned_to": "ld.Assigned_To",
        "sourced_at": "ld.Sourced_Date",
    })], {"lead_id": ID, "full_name": T, "title": T, "status": T, "source": T, "client_id": ID, "contact_id": ID,
          "job_id": ID, "email": T, "phone": T, "note": TL, "assigned_to": ID, "sourced_at": DT}),
])

# ── checks used by the target layer ──────────────────────────────────────────
def is_candidate(col: str) -> Check:
    return Check(f"EXISTS (SELECT 1 FROM {{src}}Candidates x WHERE x.candidate_id = {col})",
                 "not a migrated candidate (a contact, a removed duplicate or missing)")


def contact_ok(col: str) -> str:   # contacts are only migrated when they belong to a company
    return f"EXISTS (SELECT 1 FROM {{src}}Contacts x WHERE x.contact_id = {col} AND x.client_id IS NOT NULL)"


def parent_ok(a: str) -> Check:   # notes and documents: the record they belong to is migrated
    return Check(f"({a}.entity_type = 'candidate' AND EXISTS (SELECT 1 FROM {{src}}Candidates x WHERE x.candidate_id = {a}.entity_id))"
                 f" OR ({a}.entity_type = 'contact' AND {contact_ok(a + '.entity_id')})"
                 f" OR ({a}.entity_type = 'job' AND EXISTS (SELECT 1 FROM {{src}}Jobs x WHERE x.job_id = {a}.entity_id))"
                 f" OR ({a}.entity_type = 'client' AND EXISTS (SELECT 1 FROM {{src}}Clients x WHERE x.client_id = {a}.entity_id))",
                 "linked to no migrated record (orphan)")


# ── middle tier -> target ────────────────────────────────────────────────────
TARGET = Layer("target", TARGET_DB, "dbo", f"{STAGING_DB}.mid.", ROOT / "sql" / "load", [
    Entity("User", "User", "Users", [Insert("{src}Users u", {
        "UserID": "u.user_id",
        "Loginname": "LEFT(u.email, CHARINDEX('@', u.email + '@') - 1)",
        "FullName": "CONCAT_WS(' ', u.first_name, u.last_name)",
        "Email": "u.email",
        "Role": "u.role",
        "Status": "CASE WHEN u.is_active = 1 THEN 'Active' ELSE 'Inactive' END",
        "IsDeleted": "0",
        "IsArchived": "0",
    })]),
    Entity("Company", "Company", "Clients", [Insert("{src}Clients c", {
        "ID": "c.client_id",
        "CompanyName": "LEFT(c.company_name, 50)",
        "Industry": "c.industry",
        "Website": "LEFT(c.website, 50)",
        "Telephone": "c.phone",
        "LocationID": "CASE WHEN c.address_line_1 IS NOT NULL THEN c.client_id END",
        "Type": "'Client'",
        "Company_OwnerID": "c.owner_user_id",
        "AddedBy": "c.owner_user_id",
        "AddedDate": "c.created_at",
        "Isdeleted": "CASE WHEN c.status = 'deleted' THEN 1 ELSE 0 END",
        "IsArchive": "0",
    })]),
    Entity("CompanyLocation", "CompanyLocation", "Client locations", [Insert("{src}Clients c", {
        "ID": "c.client_id",
        "CompanyID": "c.client_id",
        "AddressLine1": "c.address_line_1",
        "AddressLine2": "c.address_line_2",
        "City": "c.city",
        "PostCode": "c.postcode",
        "Country": "c.country",
        "AddedAt": "c.created_at",
    }, where="c.address_line_1 IS NOT NULL")]),
    Entity("Contact", "Contact", "Contacts", [Insert("{src}Contacts ct", {
        "ID": "ct.contact_id",
        "FirstName": "ct.first_name",
        "LastName": "ct.last_name",
        "CompanyID": "ct.client_id",
        "Email": "ct.email",
        "Phone": "COALESCE(ct.phone, ct.mobile)",
        "PositionTitle": "LEFT(ct.job_title, 50)",
        "Contacttype": "'Client contact'",
        "ContactOwnerID": "ct.owner_user_id",
        "IsDeleted": "0",
        "IsArchived": "CASE WHEN ct.status = 'inactive' THEN 1 ELSE 0 END",
        "AddedBy": "ct.owner_user_id",
        "AddedAt": "ct.created_at",
    }, checks=[Check("ct.client_id IS NOT NULL AND EXISTS (SELECT 1 FROM {src}Clients x WHERE x.client_id = ct.client_id)", "contact linked to no company (orphan)")])]),
    Entity("Applicant", "Applicant", "Candidates", [Insert("{src}Candidates ca", {
        "ApplicantID": "ca.candidate_id",
        "FirstName": "ca.first_name",
        "LastName": "ca.last_name",
        "ApplicantCommsID": "CASE WHEN ca.email IS NOT NULL THEN TRY_CAST(ca.candidate_id AS INT) * 10 + 1 END",
        "Status": "ca.status",
        "JobTitle": "LEFT(ca.current_job_title, 50)",
        "Source": "ca.source",
        "Active": "1",
        "ApplicantOwner": "ca.owner_user_id",
        "AddedBy": "ca.owner_user_id",
        "AddedAt": "ca.created_at",
        "Deleted": "0",
    })]),
    Entity("Comms", "Comms", "Candidate email & mobile", [
        Insert("{src}Candidates ca", {
            "ID": "TRY_CAST(ca.candidate_id AS INT) * 10 + 1",
            "ObjectID": "ca.candidate_id",
            "ObjectType": "'Applicant'",
            "Value": "ca.email",
            "Type": "'Email'",
            "Deleted": "0",
            "AddedBy": "ca.owner_user_id",
        }, where="ca.email IS NOT NULL"),
        Insert("{src}Candidates ca", {
            "ID": "TRY_CAST(ca.candidate_id AS INT) * 10 + 2",
            "ObjectID": "ca.candidate_id",
            "ObjectType": "'Applicant'",
            "Value": "ca.mobile",
            "Type": "'Mobile'",
            "Deleted": "0",
            "AddedBy": "ca.owner_user_id",
        }, where="ca.mobile IS NOT NULL"),
    ]),
    Entity("Position", "Position", "Jobs", [Insert("{src}Jobs j", {
        "ID": "TRY_CAST(j.job_id AS INT)",
        "PositionName": "LEFT(j.title, 50)",
        "CompanyID": "j.client_id",
        "ContactID": "j.contact_id",
        "Status": "j.status",
        "Filled": "CASE WHEN j.status = 'filled' THEN 1 ELSE 0 END",
        "Closed": "CASE WHEN j.status IN ('filled', 'cancelled') THEN 1 ELSE 0 END",
        "Deleted": "CASE WHEN j.status = 'deleted' THEN 1 ELSE 0 END",
        "PositionChargeRate": "j.rate",
        "Salary": "CAST(j.salary_min AS NVARCHAR(50))",
        "Currency": "'GBP'",
        "DateBegins": "j.opened_at",
        "DateEnds": "j.closed_at",
        "Addedby": "j.owner_user_id",
        "PositionOwnerID": "j.owner_user_id",
    }, checks=[Check("j.status NOT IN ('open', 'interviewing', 'offer made') OR NOT EXISTS (SELECT 1 FROM {src}Clients x WHERE x.client_id = j.client_id AND x.status = 'deleted')", "open job on a deleted company", "flag")])]),
    Entity("Placements", "Placements", "Placements", [Insert("{src}Placements pl", {
        "ID": "TRY_CAST(pl.placement_id AS INT)",
        "ApplicantID": "pl.candidate_id",
        "PositionID": "TRY_CAST(pl.job_id AS INT)",
        "CompanyID": "j.client_id",
        "EmploymentType": "pl.placement_type",
        "StartDate": "pl.start_date",
        "EndDate": "pl.end_date",
        "Fee": "pl.fee",
        "Status": "'Placed'",
        "OwnerID": "pl.owner_user_id",
    }, joins=["LEFT JOIN {src}Jobs j ON j.job_id = pl.job_id"], checks=[is_candidate("pl.candidate_id"), Check("NOT EXISTS (SELECT 1 FROM {src}Jobs x WHERE x.job_id = pl.job_id AND x.status = 'deleted')", "live placement on a deleted job", "flag"), Check("NOT EXISTS (SELECT 1 FROM {src}Clients x WHERE x.client_id = j.client_id AND x.status = 'deleted')", "live placement on a deleted company", "flag")])]),
    Entity("Notes", "Notes", "Notes", [Insert("{src}Notes n", {
        "ID": "TRY_CAST(n.note_id AS INT)",
        "Text": "n.body",
        "ApplicantID": "CASE WHEN n.entity_type = 'candidate' THEN n.entity_id END",
        "CompanyID": "CASE WHEN n.entity_type = 'client' THEN n.entity_id END",
        "PositionID": "CASE WHEN n.entity_type = 'job' THEN TRY_CAST(n.entity_id AS INT) END",
        "ContactID": "CASE WHEN n.entity_type = 'contact' THEN n.entity_id END",
        "Deleted": "0",
        "AddedAt": "n.created_at",
        "UserID": "n.author_user_id",
    }, checks=[parent_ok("n")])]),
    Entity("Task", "Task", "Activities", [Insert("{src}Activities a", {
        "ID": "TRY_CAST(a.activity_id AS INT)",
        "TaskType": "a.activity_type",
        "OwnerUserID": "a.user_id",
        "Subject": "LEFT(a.subject, 50)",
        "Note": "a.subject",
        "Status": "'Completed'",
        "StartDate": "CAST(a.occurred_at AS DATE)",
        "Completed": "1",
        "AddedAt": "a.occurred_at",
    }), Insert("{src}Interviews iv", {
        "ID": "100000 + TRY_CAST(iv.interview_id AS INT)",
        "TaskType": "'Interview'",
        "OwnerUserID": "NULL",
        "Subject": "'Interview feedback'",
        "Note": "iv.feedback",
        "Status": "'Completed'",
        "StartDate": "CAST(iv.interview_date AS DATE)",
        "Completed": "1",
        "AddedAt": "iv.created_at",
    })]),
    Entity("TaskItem", "TaskItem", "Activity links", [
        Insert("{src}Activities a", {
            "ID": "TRY_CAST(a.activity_id AS INT) * 10 + 1",
            "TaskID": "TRY_CAST(a.activity_id AS INT)",
            "ObjectID": "a.candidate_id",
            "ObjectType": "'Applicant'",
            "AddedAt": "a.occurred_at",
        }, where="a.candidate_id IS NOT NULL", checks=[is_candidate("a.candidate_id")]),
        Insert("{src}Activities a", {
            "ID": "TRY_CAST(a.activity_id AS INT) * 10 + 2",
            "TaskID": "TRY_CAST(a.activity_id AS INT)",
            "ObjectID": "a.contact_id",
            "ObjectType": "'Contact'",
            "AddedAt": "a.occurred_at",
        }, where="a.contact_id IS NOT NULL", checks=[Check(contact_ok("a.contact_id"), "contact not migrated")]),
        Insert("{src}Activities a", {
            "ID": "TRY_CAST(a.activity_id AS INT) * 10 + 3",
            "TaskID": "TRY_CAST(a.activity_id AS INT)",
            "ObjectID": "a.job_id",
            "ObjectType": "'Position'",
            "AddedAt": "a.occurred_at",
        }, where="a.job_id IS NOT NULL"),
        Insert("{src}Interviews iv", {
            "ID": "1000000 + TRY_CAST(iv.interview_id AS INT)",
            "TaskID": "100000 + TRY_CAST(iv.interview_id AS INT)",
            "ObjectID": "iv.candidate_id",
            "ObjectType": "'Applicant'",
            "AddedAt": "iv.created_at",
        }, checks=[is_candidate("iv.candidate_id")]),
    ]),
    Entity("Attachments", "Attachments", "Documents", [Insert("{src}Documents d", {
        "AttachmentID": "CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END",
        "AttachmentType": "d.entity_type",
        "AttachmentName": "LEFT(d.file_name, 50)",
        "FilePath": "LEFT(d.storage_path, 50)",
        "FileType": "d.file_type",
        "UploadedAt": "d.uploaded_at",
        "IsPrimary": "0",
        "IsArchived": "0",
        "IsDeleted": "0",
    }, checks=[parent_ok("d")])]),
    Entity("Department", "Department", "Departments", [Insert("{src}Departments d", {
        "ID": "TRY_CAST(d.department_id AS INT)",
        "Name": "d.name",
        "AddedAt": "d.created_at",
        "UpdatedAt": "d.updated_at",
    })]),
    Entity("SkillCategory", "SkillCategory", "Skill categories", [Insert("{src}SkillCategories sc", {
        "ID": "sc.category_id",
        "CategoryName": "sc.name",
        "Deleted": "sc.deleted",
    })]),
    Entity("Skills", "Skills", "Skills", [Insert("{src}Skills sk", {
        "ID": "sk.skill_id",
        "SkillName": "sk.name",
        "SkillCategoryID": "sk.category_id",
        "Status": "CASE WHEN sk.deleted = 1 THEN 'Inactive' ELSE 'Active' END",
    })]),
    Entity("PositionType", "PositionType", "Job types", [Insert("(SELECT DISTINCT employment_type FROM {src}Jobs WHERE employment_type IS NOT NULL) j", {
        "ID": "ROW_NUMBER() OVER (ORDER BY j.employment_type)",
        "Type": "UPPER(LEFT(j.employment_type, 1)) + SUBSTRING(j.employment_type, 2, 50)",
    })]),
    Entity("Position_Details", "Position_Details", "Job details", [Insert("{src}Jobs j", {
        "ID": "TRY_CAST(j.job_id AS INT)",
        "PositionID": "TRY_CAST(j.job_id AS INT)",
        "Requirement": "j.description",
        "Location": "j.location",
        "ClosingDate": "j.closed_at",
        "PayFrequency": "CASE WHEN j.rate_unit = 'day' THEN 'Daily' WHEN j.salary_min IS NOT NULL THEN 'Annual' END",
        "AddedBy": "j.owner_user_id",
    })]),
    Entity("Position_Applicant", "Position_Applicant", "Applications", [Insert("{src}Applications a", {
        "ID": "TRY_CAST(a.application_id AS INT)",
        "PositionID": "TRY_CAST(a.job_id AS INT)",
        "ApplicantID": "a.candidate_id",
        "CompanyID": "a.client_id",
        "ApplicationDate": "CAST(a.applied_at AS DATE)",
        "StatusTxt": "UPPER(LEFT(a.stage, 1)) + SUBSTRING(a.stage, 2, 50)",
        "AddedBy": "a.owner_user_id",
        "AddedAt": "a.applied_at",
        "Active": "CASE WHEN a.stage IN ('placed', 'rejected') OR a.deleted = 1 THEN 0 ELSE 1 END",
    }, checks=[is_candidate("a.candidate_id")])]),
    Entity("Shortlist", "Shortlist", "Shortlists", [Insert("{src}Applications a", {
        "ID": "TRY_CAST(a.application_id AS INT)",
        "PositionID": "TRY_CAST(a.job_id AS INT)",
        "ApplicantID": "a.candidate_id",
        "ShortlistedDate": "CAST(a.applied_at AS DATE)",
        "Status": "UPPER(LEFT(a.stage, 1)) + SUBSTRING(a.stage, 2, 50)",
        "AddedBy": "a.owner_user_id",
        "AddedAt": "a.applied_at",
    }, where="a.stage IN ('screening', 'interview', 'offer')", checks=[is_candidate("a.candidate_id")])]),
    Entity("Offer", "Offer", "Offers", [Insert("{src}Applications a", {
        "ID": "TRY_CAST(a.application_id AS INT)",
        "PlacementID": "CASE WHEN a.stage = 'placed' THEN TRY_CAST(a.application_id AS INT) END",
        "Accepted": "CASE WHEN a.stage = 'placed' THEN 1 ELSE 0 END",
        "Terms": "a.employment_type",
        "RecruiterID": "a.owner_user_id",
    }, where="a.stage IN ('offer', 'placed')", checks=[is_candidate("a.candidate_id")])]),
    Entity("Deal", "Deal", "Deals", [Insert("{src}Placements pl", {
        "ID": "TRY_CAST(pl.placement_id AS INT)",
        "PlacementID": "TRY_CAST(pl.placement_id AS INT)",
        "RecruiterID": "pl.owner_user_id",
        "CompanyID": "j.client_id",
        "DealDate": "pl.start_date",
        "DealType": "pl.placement_type",
        "DealValue": "pl.fee",
    }, joins=["LEFT JOIN {src}Jobs j ON j.job_id = pl.job_id"], checks=[is_candidate("pl.candidate_id")])]),
    Entity("Deal_Stage", "Deal_Stage", "Deal stages", [Insert("{src}Placements pl", {
        "ID": "TRY_CAST(pl.placement_id AS INT)",
        "DealID": "TRY_CAST(pl.placement_id AS INT)",
        "Stage": "'Won'",
    }, checks=[is_candidate("pl.candidate_id")])]),
    Entity("Work_History", "Work_History", "Work history", [Insert("{src}WorkHistory w", {
        "ID": "TRY_CAST(w.history_id AS INT)",
        "ApplicationID": "w.candidate_id",
        "CompanyName": "LEFT(w.employer, 50)",
        "PositionTitle": "LEFT(w.job_title, 50)",
        "StartDate": "w.start_date",
        "EndDate": "w.end_date",
    }, where="w.deleted = 0", checks=[is_candidate("w.candidate_id")])]),
    Entity("References", "References", "References", [Insert("{src}[References] r", {
        "ID": "r.reference_id",
        "ApplicantID": "r.candidate_id",
        "Fullname": "r.full_name",
        "PositionTitle": "LEFT(r.job_title, 50)",
        "CompanyName": "LEFT(r.company, 50)",
        "Relationship": "r.relationship",
        "Email": "LEFT(r.email, 50)",
        "PhoneContact": "r.phone",
        "ReferenceType": "'Employment'",
        "Notes": "LEFT(r.status, 50)",
        "VerifiedAt": "CASE WHEN r.status = 'Received' THEN r.updated_at END",
        "AddedAt": "r.created_at",
        "UpdatedAt": "r.updated_at",
    }, checks=[is_candidate("r.candidate_id")])]),
    Entity("Employment_Details", "Employment_Details", "Candidate profiles", [Insert("{src}CandidateProfiles cp", {
        "ID": "TRY_CAST(cp.profile_id AS INT)",
        "Employment_Type": "cp.employment_type",
        "ApplicantID": "cp.candidate_id",
        "MarketingEmail": "c.email_ok",
        "MarketingPhone": "c.phone_ok",
        "MarketingText": "c.text_ok",
        "Bank": "LEFT(cp.bank, 50)",
        "SortCode": "cp.sort_code",
        "Notes": "cp.notes",
        "AddedBy": "cp.added_by",
        "AddedAt": "cp.created_at",
        "UpdatedAt": "cp.updated_at",
    }, joins=["LEFT JOIN {src}Consents c ON c.person_id = cp.candidate_id"], checks=[is_candidate("cp.candidate_id")])]),
    Entity("Marketing", "Marketing", "Marketing consent", [Insert("{src}Consents c", {
        "ID": "TRY_CAST(c.consent_id AS INT)",
        "ApplicantID": "c.person_id",
        "Email": "CASE WHEN c.email_ok = 1 THEN 'Yes' ELSE 'No' END",
        "Phone": "CASE WHEN c.phone_ok = 1 THEN 'Yes' ELSE 'No' END",
        "Text": "CASE WHEN c.text_ok = 1 THEN 'Yes' ELSE 'No' END",
        "GDPRConsent": "1",
        "OptIn": "CASE WHEN c.email_ok = 1 OR c.phone_ok = 1 OR c.text_ok = 1 THEN 1 ELSE 0 END",
        "OptOut": "CASE WHEN c.email_ok = 0 AND c.phone_ok = 0 AND c.text_ok = 0 THEN 1 ELSE 0 END",
        "AddedAt": "c.created_at",
        "UpdatedAt": "c.updated_at",
        "AddedBy": "c.added_by",
    }, where="c.person_id IN (SELECT candidate_id FROM {src}Candidates)")]),
    Entity("Sources", "Sources", "Candidate sources", [Insert("(SELECT DISTINCT source FROM {src}Candidates WHERE source IS NOT NULL) s", {
        "ID": "CAST(ROW_NUMBER() OVER (ORDER BY s.source) AS NVARCHAR(50))",
        "Name": "UPPER(LEFT(s.source, 1)) + SUBSTRING(s.source, 2, 50)",
    })]),
    Entity("Currencies", "Currencies", "Currencies", [Insert("(SELECT DISTINCT currency FROM {src}Invoices WHERE currency IS NOT NULL) cu", {
        "CurrencyID": "ROW_NUMBER() OVER (ORDER BY cu.currency)",
        "CurrencyCode": "cu.currency",
    })]),
    Entity("Timesheets", "Timesheets", "Timesheets", [Insert("{src}Timesheets t", {
        "ID": "TRY_CAST(t.timesheet_id AS INT)",
        "StartDate": "t.start_date",
        "EndDate": "t.end_date",
        "Payrate": "t.pay_rate",
        "ChargeRate": "t.charge_rate",
        "Currency": "'GBP'",
        "Status": "UPPER(LEFT(t.status, 1)) + SUBSTRING(t.status, 2, 50)",
        "TimesheetType": "t.timesheet_type",
        "TotalWeekHours": "(SELECT SUM(l.hours) FROM {src}TimesheetLines l WHERE l.timesheet_id = t.timesheet_id)",
        "ApprovedBy": "t.approved_by",
        "Deleted": "0",
    })]),
    Entity("TimesheetActivity", "TimesheetActivity", "Timesheet lines", [Insert("{src}TimesheetLines l", {
        "ActivityID": "TRY_CAST(l.line_id AS INT)",
        "TimesheetID": "TRY_CAST(l.timesheet_id AS INT)",
        "AssocID": "TRY_CAST(l.candidate_id AS INT)",
        "TimesheetDate": "t.start_date",
        "HoursWorked": "l.hours",
        "Status": "t.status",
        "AddedBy": "l.added_by",
        "AddedAt": "l.created_at",
    }, joins=["LEFT JOIN {src}Timesheets t ON t.timesheet_id = l.timesheet_id"], checks=[is_candidate("l.candidate_id")])]),
    Entity("PurchaseOrder", "PurchaseOrder", "Purchase orders", [Insert("{src}PurchaseOrders po", {
        "PONo": "po.po_no",
        "CompanyID": "po.client_id",
        "PODate": "po.issue_date",
        "POAmount": "po.amount",
        "Status": "UPPER(LEFT(po.status, 1)) + SUBSTRING(po.status, 2, 50)",
        "AddedAt": "po.created_at",
        "AddedBy": "po.added_by",
    })]),
    Entity("PurchaseOrderItems", "PurchaseOrderItems", "Purchase order lines", [Insert("{src}PurchaseOrders po", {
        "ID": "ROW_NUMBER() OVER (ORDER BY po.po_no)",
        "PONo": "po.po_no",
        "PositionID": "TRY_CAST(po.job_id AS INT)",
        "Description": "po.description",
        "Quantity": "1",
        "UnitPrice": "po.amount",
        "Amount": "po.amount",
        "Status": "UPPER(LEFT(po.status, 1)) + SUBSTRING(po.status, 2, 50)",
        "AddedBy": "po.added_by",
        "AddedAt": "po.created_at",
    })]),
    Entity("Invoice", "Invoice", "Invoices", [Insert("{src}Invoices inv", {
        "ID": "TRY_CAST(inv.invoice_id AS INT)",
        "Type": "inv.invoice_type",
        "InvoiceNo": "inv.invoice_no",
        "PlacementID": "(SELECT TOP 1 TRY_CAST(l.placement_id AS INT) FROM {src}InvoiceLines l WHERE l.invoice_id = inv.invoice_id AND l.placement_id IS NOT NULL)",
        "Amount": "inv.net_amount",
        "TaxAmount": "inv.vat_amount",
        "Currency": "inv.currency",
        "InvoiceDate": "inv.invoice_date",
        "DueDate": "inv.due_date",
        "Status": "UPPER(LEFT(inv.status, 1)) + SUBSTRING(inv.status, 2, 50)",
        "Notes": "inv.description",
        "AddedBy": "inv.added_by",
    })]),
    Entity("Leads", "Leads", "Leads", [Insert("{src}Leads ld", {
        "ID": "TRY_CAST(ld.lead_id AS INT)",
        "Fullname": "ld.full_name",
        "PipelineStage": "ld.status",
        "CompanyID": "ld.client_id",
        "Type": "ld.title",
        "Source": "ld.source",
        "Notes": "ld.note",
        "Deleted": "0",
        "AddedAt": "ld.sourced_at",
        "AddedBy": "ld.assigned_to",
    })]),
    Entity("ApplicantAttachment", "ApplicantAttachment", "Candidate documents", [Insert("{src}Documents d", {
        "ID": "CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END",
        "AttachmentID": "CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END",
        "ApplicantID": "d.entity_id",
        "AddedAt": "d.uploaded_at",
    }, where="d.entity_type = 'candidate'", checks=[parent_ok("d")])]),
    Entity("ContactAttachment", "ContactAttachment", "Contact documents", [Insert("{src}Documents d", {
        "ID": "CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END",
        "AttachmentID": "CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END",
        "ContactID": "d.entity_id",
        "AddedAt": "d.uploaded_at",
    }, where="d.entity_type = 'contact'", checks=[parent_ok("d")])]),
    Entity("PositionAttachment", "PositionAttachment", "Job documents", [Insert("{src}Documents d", {
        "ID": "CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END",
        "AttachmentID": "CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END",
        "PositionID": "TRY_CAST(d.entity_id AS INT)",
        "AddedAt": "d.uploaded_at",
    }, where="d.entity_type = 'job'", checks=[parent_ok("d")])]),
])
LAYERS = {"middle": MIDDLE, "target": TARGET}


# ── overrides ────────────────────────────────────────────────────────────────
def load_overrides() -> dict:
    return json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")) if OVERRIDES_FILE.exists() else {}


def save_overrides(o: dict):
    o = {layer: {k: v for k, v in fields.items() if v is not None} for layer, fields in o.items()}
    OVERRIDES_FILE.write_text(json.dumps({k: v for k, v in o.items() if v}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def field_key(entity: str, n: int, column: str) -> str:
    return f"{entity}:{n}:{column}"


def expression(layer: Layer, e: Entity, n: int, column: str, overrides: dict | None = None) -> str:
    o = (overrides if overrides is not None else load_overrides()).get(layer.name, {})
    return o.get(field_key(e.key, n, column), e.inserts[n].columns[column])


# ── scripts ──────────────────────────────────────────────────────────────────
def q(name: str) -> str:
    return f"[{name}]" if name.lower() in {"user", "references"} else name


def insert_sql(layer: Layer, e: Entity, overrides: dict | None = None) -> str:
    o = load_overrides() if overrides is None else overrides
    fmt = lambda s: s.replace("{src}", layer.src)                    # noqa: E731
    target = f"{layer.schema}.{q(e.table)}"
    out = [f"USE {layer.db};", "", f"TRUNCATE TABLE {target};", ""]
    if any(i.checks for i in e.inserts):
        out += [f"DELETE FROM {layer.schema}.MigrationRejects WHERE target_table = N'{e.table}';", ""]
    for n, ins in enumerate(e.inserts):
        cols = list(ins.columns)
        exprs = {c: fmt(expression(layer, e, n, c, o)) for c in cols}
        width = max(len(x) for x in exprs.values() if "\n" not in x)
        frm = [f"FROM {fmt(ins.source)}"] + [fmt(j) for j in ins.joins]
        rejects = [c for c in ins.checks if c.action == "reject"]
        keep = [f"({fmt(c.cond)})" for c in rejects]
        base = [f"({fmt(ins.where)})"] if ins.where else []
        key = exprs[cols[0]]
        # rows that fail a check are logged first: rejected rows are not loaded, flagged rows are
        for c in ins.checks:
            cond = base + (keep if c.action == "flag" else []) + [f"NOT ({fmt(c.cond)})"]
            out.append(f"INSERT INTO {layer.schema}.MigrationRejects (target_table, source_key, action, reason)")
            out.append(f"SELECT N'{e.table}', CAST({key} AS NVARCHAR(200)), N'{'rejected' if c.action == 'reject' else 'flagged'}', N'{c.reason}'")
            out += frm
            out.append("WHERE " + "\n  AND ".join(cond) + ";")
            out.append("")
        out.append(f"INSERT INTO {target} (")
        out.append(",\n".join(f"    {c}" for c in cols))
        out.append(")")
        out.append("SELECT\n" + ",\n".join(f"    {exprs[c].ljust(width)}  AS {c}" for c in cols))
        out += frm
        if base + keep:
            out.append("WHERE " + "\n  AND ".join(base + keep))
        out[-1] += ";"
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ── duplicate merges: the reviewer's decisions (Data quality -> Duplicates) applied to the middle tier ──
# legacy table of the pair -> (middle entity, its id column, type used by notes/documents)
MERGE_TARGETS = {"Person": ("candidates", "candidate_id", "candidate"), "Associates": ("contacts", "contact_id", "contact"),
                 "Accounts": ("clients", "client_id", "client"), "Req": ("jobs", "job_id", "job"),
                 "TimesheetItems": ("timesheet_lines", "line_id", None)}


def resolved_merges(server: str = SERVER) -> list[dict]:
    """The reviewer's merges, resolved to the middle-tier record they apply to. A person who is a client
    contact is merged as a contact (by their contact ids); any other person as a candidate."""
    try:
        sys.path.insert(0, str(ROOT))
        from validation.duplicates import merges
        decided = merges("legacy")
    except Exception:                                      # noqa: BLE001
        return []
    contact_of: dict[str, str] = {}
    people = [m[k] for m in decided if m["table"] == "Person" for k in ("survivor", "duplicate")]
    if people:
        try:
            cn = _connect(SOURCE_DB, server)
            marks = ", ".join("?" * len(people))
            for pid, aid in cn.cursor().execute(
                    f"SELECT Person_ID, MIN(AssociateID) FROM dbo.Associates WHERE Person_ID IN ({marks}) GROUP BY Person_ID", people):
                contact_of[str(pid)] = str(aid)
            cn.close()
        except Exception:                                  # noqa: BLE001
            pass
    out = []
    for mg in decided:
        if mg["table"] not in MERGE_TARGETS:
            continue
        key, idc, poly = MERGE_TARGETS[mg["table"]]
        keep, dup = mg["survivor"], mg["duplicate"]
        if mg["table"] == "Person" and keep in contact_of and dup in contact_of:
            key, idc, poly = MERGE_TARGETS["Associates"]
            keep, dup = contact_of[keep], contact_of[dup]
        out.append({"merge_key": f"{mg['table']}:{mg['duplicate']}:{mg['survivor']}", "source_table": mg["table"],
                    "entity": key, "id_column": idc, "poly": poly, "survivor": keep, "duplicate": dup,
                    "take_from_duplicate": mg["take_from_duplicate"]})
    return out


def merges_sql() -> str:
    """Re-point everything attached to each merged duplicate at the kept record, copy the values the
    reviewer took from the duplicate, then delete the duplicate."""
    out = [f"USE {STAGING_DB};", ""]
    for mg in resolved_merges():
        key, idc, poly = mg["entity"], mg["id_column"], mg["poly"]
        e = MIDDLE.entity(key)
        tbl = f"mid.{q(e.table)}"
        dup, keep = mg["duplicate"].replace("'", "''"), mg["survivor"].replace("'", "''")
        out.append(f"-- {e.label}: {dup} merged into {keep}")
        # values taken from the duplicate: middle columns filled straight from that legacy column
        cols = [c for c, ex in e.inserts[0].columns.items()
                if re.fullmatch(r"\w+\.(\w+)", ex) and re.fullmatch(r"\w+\.(\w+)", ex).group(1) in mg["take_from_duplicate"]]
        if cols:
            out.append(f"UPDATE k SET {', '.join(f'k.{c} = d.{c}' for c in cols)} FROM {tbl} k JOIN {tbl} d ON d.{idc} = N'{dup}' WHERE k.{idc} = N'{keep}';")
        for other in MIDDLE.entities:
            if other is e:
                continue
            cs = other.types or {}
            if idc in cs:
                out.append(f"UPDATE mid.{q(other.table)} SET {idc} = N'{keep}' WHERE {idc} = N'{dup}';")
            if poly and "entity_type" in cs and "entity_id" in cs:
                out.append(f"UPDATE mid.{q(other.table)} SET entity_id = N'{keep}' WHERE entity_type = '{poly}' AND entity_id = N'{dup}';")
        if key == "candidates":
            out.append(f"DELETE FROM mid.Consents WHERE person_id = N'{dup}' AND EXISTS (SELECT 1 FROM mid.Consents WHERE person_id = N'{keep}');")
            out.append(f"UPDATE mid.Consents SET person_id = N'{keep}' WHERE person_id = N'{dup}';")
        out.append(f"DELETE FROM {tbl} WHERE {idc} = N'{dup}';")
        out.append("")
    return "\n".join(out).rstrip() + "\n"

def _target_types(e: Entity) -> dict[str, str]:
    from engine import load_target_schema
    cols = load_target_schema().tables[e.table]
    return {c.name: c.type + (" NOT NULL" if c.pk else "") for c in cols.values()}


def create_sql(layer: Layer) -> str:
    out = ["USE master;", "GO"]
    if layer is TARGET:
        out += [f"IF DB_ID(N'{layer.db}') IS NOT NULL BEGIN ALTER DATABASE {layer.db} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
                f"DROP DATABASE {layer.db}; END", "GO", f"CREATE DATABASE {layer.db};", "GO"]
    else:
        out += [f"IF DB_ID(N'{layer.db}') IS NULL CREATE DATABASE {layer.db};", "GO"]
    out += [f"ALTER DATABASE {layer.db} SET AUTO_CLOSE OFF;", "GO", f"USE {layer.db};", "GO"]
    if layer.schema != "dbo":
        out += [f"IF SCHEMA_ID(N'{layer.schema}') IS NULL EXEC (N'CREATE SCHEMA {layer.schema}');", "GO"]
    if layer is TARGET:
        out += [f"CREATE TABLE {layer.schema}.MigrationRejects (\n    target_table NVARCHAR(100) NOT NULL,\n"
                "    source_key NVARCHAR(200) NULL,\n    action NVARCHAR(20) NOT NULL,\n    reason NVARCHAR(400) NOT NULL,\n"
                "    logged_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()\n);", "GO"]
    for e in layer.entities:
        types = e.types or _target_types(e)
        cols = ",\n".join(f"    {c} {t}" for c, t in types.items())
        name = f"{layer.schema}.{q(e.table)}"
        out += [f"IF OBJECT_ID(N'{layer.schema}.{e.table}') IS NOT NULL DROP TABLE {name};", f"CREATE TABLE {name} (\n{cols}\n);", "GO"]
    return "\n".join(out) + "\n"


def script_name(layer: Layer, e: Entity) -> str:
    return f"{layer.entities.index(e) + 1:02d}_{e.key}.sql"


def write(layer: Layer) -> list[Path]:
    layer.out.mkdir(parents=True, exist_ok=True)
    for old in layer.out.glob("*.sql"):
        old.unlink()
    paths = [layer.out / "00_create.sql"]
    paths[0].write_text(create_sql(layer), encoding="utf-8")
    if layer is MIDDLE:
        (layer.out / "99_merge_duplicates.sql").write_text(merges_sql(), encoding="utf-8")
        paths.append(layer.out / "99_merge_duplicates.sql")
    o = load_overrides()
    for e in layer.entities:
        p = layer.out / script_name(layer, e)
        p.write_text(insert_sql(layer, e, o), encoding="utf-8")
        paths.append(p)
    return paths


# ── run / read ───────────────────────────────────────────────────────────────
def _connect(db: str = "master", server: str = SERVER):
    import pyodbc
    return pyodbc.connect(f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={db};Trusted_Connection=yes;",
                          autocommit=True)


def _batches(sql: str) -> list[str]:
    return [b.strip() for b in re.split(r"^\s*GO\s*$", sql, flags=re.M | re.I) if b.strip()]


def run(layer: Layer, only: str | None = None, create: bool = True) -> dict[str, int]:
    """Run a layer's scripts (all entities, or one); returns rows per entity."""
    cn = _connect()
    cur = cn.cursor()
    if create:
        for b in _batches(create_sql(layer)):
            cur.execute(b)
    o = load_overrides()
    counts = {}
    for e in layer.entities:
        if only and e.key != only:
            continue
        for b in _batches(insert_sql(layer, e, o)):
            cur.execute(b)
        counts[e.key] = cur.execute(f"SELECT COUNT(*) FROM {layer.db}.{layer.schema}.{q(e.table)}").fetchone()[0]
    if layer is MIDDLE:                                    # merges always run after the middle tier is (re)loaded
        for b in _batches(merges_sql()):
            cur.execute(b)
        for e in layer.entities:
            if e.key in counts:
                counts[e.key] = cur.execute(f"SELECT COUNT(*) FROM {layer.db}.{layer.schema}.{q(e.table)}").fetchone()[0]
    cn.close()
    return counts


def reconciliation(server: str = SERVER) -> list[dict]:
    """Row counts per entity: legacy source table(s) -> middle tier table -> target table(s) it loads."""
    cn = _connect("master", server)
    cur = cn.cursor()

    def count(db: str, schema: str, table: str) -> int | None:
        try:
            return cur.execute(f"SELECT COUNT(*) FROM {db}.{schema}.{q(table)}").fetchone()[0]
        except Exception:                                  # noqa: BLE001 — not loaded yet
            return None

    feeds: dict[str, list[str]] = {}
    for t in TARGET.entities:
        for ins in t.inserts:
            m = re.search(r"\{src\}\[?(\w+)", ins.source)
            if m and t.table not in feeds.setdefault(m.group(1), []):
                feeds[m.group(1)].append(t.table)
    out = []
    for e in MIDDLE.entities:
        sources = sorted({re.match(r"\{src\}(\w+)", i.source).group(1) for i in e.inserts})
        targets = feeds.get(e.table, [])
        out.append({
            "entity": e.label,
            "source": [{"table": s_, "rows": count(SOURCE_DB, "dbo", s_)} for s_ in sources],
            "middle": {"table": f"mid.{e.table}", "rows": count(STAGING_DB, "mid", e.table)},
            "target": [{"table": t_, "rows": count(TARGET_DB, "dbo", t_)} for t_ in targets],
        })
    cn.close()
    return out

def rejects(server: str = SERVER) -> list[dict]:
    """Rows the target load rejected or flagged, with the reason."""
    cn = _connect(TARGET_DB, server)
    cur = cn.cursor()
    cur.execute("SELECT target_table, source_key, action, reason FROM dbo.MigrationRejects ORDER BY action DESC, target_table, source_key")
    out = [{"table": r[0], "key": r[1], "action": r[2], "reason": r[3]} for r in cur.fetchall()]
    cn.close()
    return out


def read(layer: Layer, key: str) -> list[dict]:
    e = layer.entity(key)
    cn = _connect(layer.db)
    cur = cn.cursor()
    first = next(iter(e.inserts[0].columns))
    cur.execute(f"SELECT * FROM {layer.schema}.{q(e.table)} ORDER BY TRY_CAST({first} AS BIGINT), {first}")
    cols = [d[0] for d in cur.description]
    rows = []
    for r in cur.fetchall():
        rec = {}
        for c, v in zip(cols, r):
            if v is None:
                rec[c] = None
            elif isinstance(v, bool):
                rec[c] = "true" if v else "false"
            else:
                s = str(v)
                rec[c] = s[:-9] if s.endswith(" 00:00:00") else s
        rows.append(rec)
    cn.close()
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="execute both layers on SQL Server")
    args = ap.parse_args()
    for layer in (MIDDLE, TARGET):
        paths = write(layer)
        print(f"{layer.name}: {len(paths)} scripts in {layer.out.relative_to(ROOT)}")
        if args.run:
            for k, n in run(layer).items():
                print(f"  {layer.schema}.{layer.entity(k).table:<16} {n:>6} rows")


if __name__ == "__main__":
    main()
