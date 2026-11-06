# Target SQL generation report

Generated 2026-11-06 15:49 from `mapping/migration_mapping.json`.

* Generated: **12** table mappings
* Blocked: **9**

## Blocked mappings (fix in the mapping UI, then regenerate)

### Accounts->Company
* D05 Website: 1 value(s) of Accounts.Website are longer than 50 characters and would be truncated

### Associates->Contact
* C06 DepartmentID: Contact.DepartmentID references Department, but Department has no mapping
* C04 IsDeleted: Unknown transform 'status_to_bool'

### GDPR_Consent->Marketing
* C04 GDPRConsent: Unknown transform 'coalesce_any_true'
* M04 ID: Primary key Marketing.ID is not mapped

### Leads->Leads
* parent Company is not migrated (blocked or unmapped) — CompanyID

### PONo->PurchaseOrder
* parent Company is not migrated (blocked or unmapped) — CompanyID

### Person->Applicant
* C04 Deleted: Unknown transform 'coalesce_or'

### Req->Position
* parent Company is not migrated (blocked or unmapped) — CompanyID

### Req_Hired->Placements
* C06 ApplicantID: s.Associate_ID references Associates, but Applicant is loaded from Person
* C04 Status: Unknown transform 'bit_to_status_text'

### Req_Rates->Position
* M04 ID: Primary key Position.ID is not mapped

## Generated with warnings

* `Documents->Attachments` AttachmentType: Low confidence (0.85) and not reviewed
* `Documents->Attachments` FileType: Low confidence (0.72) and not reviewed
* `CV_Docs->Attachments` UploadedBy: Legacy ID CV_Docs.Uploaded_Id copied into plain column Attachments.UploadedBy
* `Documents->Attachments` UploadedBy: Legacy ID Documents.Uploaded_Id copied into plain column Attachments.UploadedBy
* `Invoice->Invoice` Type: Low confidence (0.88) and not reviewed
* `Schedule->Task` TaskType: Low confidence (0.88) and not reviewed
* `TimesheetItems->TimesheetActivity` AssocID: Legacy ID TimesheetItems.Person_ID copied into plain column TimesheetActivity.AssocID
* `TimesheetItems->TimesheetActivity` AssocID: Low confidence (0.88) and not reviewed
* `TimesheetItems->TimesheetActivity` TimesheetID: 5 row(s) reference a TimeSheets that is not loaded into Timesheets — they will be rejected
* `TimeSheets->Timesheets` TimesheetType: Low confidence (0.85) and not reviewed
* `Recruiter->User` Role: Low confidence (0.88) and not reviewed
