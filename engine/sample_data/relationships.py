"""
sample_data/relationships.py

Foreign-key model of the legacy source database.

`Source Schema.csv` flags FK columns but never says what they point at, and
leaves several obvious ones unflagged, so the relationships are declared here
explicitly. Each entry: (child_table, child_column, parent_table, parent_column).

Note: EmpHist/EmpEdu/Emp_Documents.Emp_ID hold Emp_ProfileID values (1-150), despite
the schema comment "Links to Emp Number"; EmpRef.EmpNo holds Emp_No values (1001+).

Not modelled as FKs (by design, documented for the mapping/profiling stages):
  * polymorphic links: Notes.ObjectId, Documents.Doc_AssocID, TagEntity.EntityID,
    Sectors.ObjectID, ComplianceItems.Comp_AssocID, Log.Entity_ID - the parent
    table depends on an ObjectType column
  * codes with no lookup table: Associates.Associate_StatusID, Emp_Profile.Emp_TypeID,
    Req.StatusID/WorktypeID/ReqSource, Req_Hired.CurrencyID/Reason_ID, CV_Docs.CV_ID,
    Log.request_Id
"""

# non-PK columns that are FK targets -> need a UNIQUE constraint
UNIQUE_KEYS = [("Emp_Profile", "Emp_No")]

# Source Schema.csv types overridden so FKs can be declared (FK and PK types must match).
# All existing values are integers, so nothing is lost.
TYPE_OVERRIDES = {
    ("Associates", "AssociateID"): "INT",   # declared NVARCHAR(50), referenced by 5 INT columns
    ("EmpRef", "EmpNo"): "INT",             # declared NVARCHAR(255), references Emp_Profile.Emp_No (INT)
}

AUDIT_COLUMNS = ("CreatedBy", "UpdatedBy", "Uploaded_Id", "Updated_Id")   # -> Recruiter.RecruiterID

FOREIGN_KEYS = [
    # accounts / clients
    ("Accounts", "AccountTypeID", "AccountType", "AccountTypeID"),
    ("Accounts", "AccountStatusTypeID", "AccountStatus", "Account_StatusID"),
    ("Accounts", "DeptID", "Departments", "DepartmentID"),
    ("Accounts", "AddressID", "Addresses", "AddressID"),
    ("Accounts", "Division_ID", "Division", "DivisionID"),
    ("Accounts", "ParentAccountID", "Accounts", "Account_ID"),
    ("Accounts", "InvoiceAddressID", "Addresses", "AddressID"),
    ("Accounts", "RateID", "AccountRate", "Rate_ID"),
    ("AccountRate", "Account_ID", "Accounts", "Account_ID"),
    # contacts / people
    ("Associates", "Person_ID", "Person", "Person_ID"),
    ("Associates", "DeptID", "Departments", "DepartmentID"),
    ("Associates", "Associate_AddressID", "Addresses", "AddressID"),
    ("Associates", "Associate_RoleID", "Roles", "Role_ID"),
    ("Associates", "DivisionID", "Division", "DivisionID"),
    ("AccountAssociates", "AssociateID", "Associates", "AssociateID"),
    ("AccountAssociates", "AccountID", "Accounts", "Account_ID"),
    ("AssociateTypes", "DivisionID", "Division", "DivisionID"),
    ("AssociateTypes", "DepartmentID", "Departments", "DepartmentID"),
    ("AssociateTypeRelation", "AssociateID", "Associates", "AssociateID"),
    ("AssociateTypeRelation", "TypeID", "AssociateTypes", "Associate_TypeID"),
    ("Person", "GDPRConsent_ID", "GDPR_Consent", "GDPR_ConsentID"),
    ("Person", "DeptID", "Departments", "DepartmentID"),
    ("Person", "Role_ID", "Roles", "Role_ID"),
    ("GDPR_Consent", "Person_ID", "Person", "Person_ID"),
    ("Recruiter", "Role_ID", "Roles", "Role_ID"),
    ("Recruiter", "ReportsTo", "Recruiter", "RecruiterID"),
    ("Leads", "Associate_ID", "Associates", "AssociateID"),
    ("Leads", "Account_ID", "Accounts", "Account_ID"),
    ("Leads", "Req_ID", "Req", "ReqID"),
    ("Leads", "Document_ID", "Documents", "Doc_ID"),
    ("Leads", "Assigned_To", "Recruiter", "RecruiterID"),
    # jobs / placements
    ("Req", "AssociateID", "Associates", "AssociateID"),
    ("Req", "AccountID", "Accounts", "Account_ID"),
    ("Req", "Req_RateID", "Req_Rates", "Req_RateID"),
    ("Req", "Address_ID", "Addresses", "AddressID"),
    ("Req", "PONumber", "PONo", "PONo"),
    ("Req_Rates", "Req_ID", "Req", "ReqID"),
    ("Req_Hired", "Account_ID", "Accounts", "Account_ID"),
    ("Req_Hired", "Associate_ID", "Associates", "AssociateID"),
    ("Req_Hired", "Req_ID", "Req", "ReqID"),
    ("Req_Hired", "Invoiced_PersonID", "Person", "Person_ID"),
    ("Req_Hired", "RateID", "AccountRate", "Rate_ID"),
    ("Req_Hired", "Owner_ID", "Recruiter", "RecruiterID"),
    ("Req_Hired", "Second_OwnerID", "Recruiter", "RecruiterID"),
    ("Req_Documents", "Req_ID", "Req", "ReqID"),
    ("Req_Documents", "Document_ID", "Documents", "Doc_ID"),
    ("Schedule", "AssignSchedule_ID", "Schedule", "Schedule_ID"),
    ("Schedule", "Account_ID", "Accounts", "Account_ID"),
    ("Schedule", "Req_ID", "Req", "ReqID"),
    ("Schedule", "Person_ID", "Person", "Person_ID"),
    ("Interview_Feedback", "Interviewer_ID", "Person", "Person_ID"),
    ("Interview_Feedback", "Interviewee_ID", "Person", "Person_ID"),
    ("Interview_Feedback", "Second_InterviewerID", "Person", "Person_ID"),
    ("Interview_Feedback", "Other_InterviewerID", "Person", "Person_ID"),
    # employees / candidates
    ("Emp_Profile", "Person_ID", "Person", "Person_ID"),
    ("EmpHist", "Emp_ID", "Emp_Profile", "Emp_ProfileID"),
    ("EmpEdu", "Emp_ID", "Emp_Profile", "Emp_ProfileID"),
    ("EmpRef", "EmpNo", "Emp_Profile", "Emp_No"),
    ("EmpRef", "Ref_ID", "Referees", "Referee_ID"),
    ("Emp_Documents", "Emp_ID", "Emp_Profile", "Emp_ProfileID"),
    ("Emp_Documents", "Document_ID", "Documents", "Doc_ID"),
    ("Emp_Documents", "Person_ID", "Person", "Person_ID"),
    ("CV_Docs", "CV_AssocID", "Person", "Person_ID"),
    ("BackgroundChecks", "Person_ID", "Person", "Person_ID"),
    ("BackgroundChecks", "Doc_ID", "Documents", "Doc_ID"),
    ("ObjectHotlist", "Hotlist_ID", "Hotlists", "Hotlist_ID"),
    ("ObjectHotlist", "Person_ID", "Person", "Person_ID"),
    ("ObjectSKills", "SkillID", "Skills", "SkillID"),
    ("Skills", "Skill_CategoryID", "SkillCategory", "CategoryID"),
    # documents / compliance
    ("Documents", "Typeid", "DocumentType", "Doc_TypeID"),
    ("RecruiterDocuments", "Recruiter_ID", "Recruiter", "RecruiterID"),
    ("RecruiterDocuments", "Document_ID", "Documents", "Doc_ID"),
    ("ComplianceItems", "Comp_ID", "Compliance", "Compliance_ID"),
    ("ComplianceItems", "Comp_DocID", "ComplianceDocuments", "Comp_DocId"),
    ("ComplianceItems", "CompType_ID", "ComplianceTypes", "Compliance_typeID"),
    # finance / time
    ("PONo", "VendorID", "Accounts", "Account_ID"),
    ("PONo", "ReqID", "Req", "ReqID"),
    ("PONo", "DepartmentID", "Departments", "DepartmentID"),
    ("PONo", "ApprovedBy", "Recruiter", "RecruiterID"),
    ("TimeSheets", "Timesheet_TypeID", "TimesheetType", "Timesheet_TypeID"),
    ("TimeSheets", "PONo", "PONo", "PONo"),
    ("TimeSheets", "Approved_By", "Recruiter", "RecruiterID"),
    ("TimesheetItems", "Timesheet_ID", "TimeSheets", "ID"),
    ("TimesheetItems", "Timesheet_TypeID", "TimesheetType", "Timesheet_TypeID"),
    ("TimesheetItems", "Person_ID", "Person", "Person_ID"),
    ("TimesheetItems", "Req_ID", "Req", "ReqID"),
    ("Invoice", "PONo", "PONo", "PONo"),
    ("Invoice", "Vendor_ID", "Accounts", "Account_ID"),
    ("Invoice", "Document_ID", "Documents", "Doc_ID"),
    ("Invoice", "Approved_By", "Recruiter", "RecruiterID"),
    ("Invoice", "InvoiceType_ID", "InvoiceTypes", "InvoiceType_ID"),
    ("InvoiceEntries", "Invoice_ID", "Invoice", "InvoiceID"),
    ("InvoiceEntries", "Plac_ID", "Req_Hired", "Req_HiredID"),
    # tags / system
    ("Tags", "CategoryID", "Categories", "Category_ID"),
    ("TagEntity", "TagID", "Tags", "ID"),
    ("APIsession", "User_ID", "Recruiter", "RecruiterID"),
    ("Log", "User_ID", "Recruiter", "RecruiterID"),
]


def all_foreign_keys(schema: dict) -> list[tuple]:
    """Explicit FKs + audit columns (CreatedBy/UpdatedBy/...) -> Recruiter, for every table that has them."""
    fks = list(FOREIGN_KEYS)
    for table, cols in schema.items():
        for c in cols:
            if c["col"] in AUDIT_COLUMNS:
                fks.append((table, c["col"], "Recruiter", "RecruiterID"))
    return fks
