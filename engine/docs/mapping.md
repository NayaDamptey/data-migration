# Field Mapping Reference

> **Source:** Legacy Recruitment CRM  
> **Target:** Modern Recruitment Platform  
> **Version:** 1.0

> Confidence scores: 1.0 = exact match, 0.9+ = high confidence, 0.7-0.9 = review recommended, <0.7 = manual verification required

---

## Contents

- [Clients](#clients)
- [Contacts](#contacts)
- [Candidates](#candidates)
- [Users](#users)
- [Jobs](#jobs)
- [Placements](#placements)
- [Compliance](#compliance)
- [Documents](#documents)
- [Timesheets](#timesheets)
- [Finance](#finance)
- [Leads](#leads)

---

## Clients

### `Accounts` → `Company`

_Client organisations_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Account_ID` | `ID` | `cast_to_nvarchar` | 🟢 0.95 | Type change INT to NVARCHAR |
| `Account_name` | `CompanyName` | `direct` | 🟢 0.97 |  |
| `Industry` | `Industry` | `direct` | 🟢 1.00 |  |
| `Website` | `Website` | `direct` | 🟢 1.00 |  |
| `About` | `Background` | `direct` | 🟢 0.92 | Column renamed |
| `AddressID` | `LocationID` | `cast_to_nvarchar` | 🟡 0.88 | FK target table differs â€” map via Addresses |
| `CreatedAt` | `AddedDate` | `direct` | 🟢 1.00 |  |
| `UpdatedAt` | `UpdatedDate` | `direct` | 🟢 1.00 |  |
| `Deleted` | `Isdeleted` | `direct` | 🟢 1.00 |  |

---

## Contacts

### `Associates` → `Contact`

_Associates map to Contact. Where Associate is also a candidate, a parallel Applicant record is created via Person._

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `AssociateID` | `ID` | `direct` | 🟢 0.90 |  |
| `AssociateTitle` | `PositionTitle` | `direct` | 🟡 0.88 |  |
| `Associate_StatusID` | `IsDeleted` | `status_to_bool` | 🟡 0.75 | Status lookup required |
| `Associate_AddressID` | `LocationID` | `cast_to_nvarchar` | 🟡 0.88 |  |
| `DivisionID` | `DepartmentID` | `cast_to_nvarchar` | 🟡 0.82 | Division maps to Department |
| `Active` | `IsDeleted` | `invert_bool` | 🟡 0.85 | Active=false becomes IsDeleted=true |
| `CreatedAt` | `AddedAt` | `direct` | 🟢 1.00 |  |
| `UpdatedAt` | `ModifiedAt` | `direct` | 🟢 1.00 |  |
| `CreatedBy` | `AddedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |
| `UpdatedBy` | `ModifiedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |

---

## Candidates

### `Person` → `Applicant`

_Person records flagged as candidates (Emp=0) map to Applicant_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Person_ID` | `ApplicantID` | `cast_to_nvarchar` | 🟢 0.95 | Type change INT to NVARCHAR |
| `First_Name` | `FirstName` | `direct` | 🟢 1.00 |  |
| `Middle_name` | `MiddleName` | `direct` | 🟢 1.00 |  |
| `Last_Name` | `LastName` | `direct` | 🟢 1.00 |  |
| `DOB` | `DateOfBirth` | `direct` | 🟢 1.00 |  |
| `Deleted` | `Deleted` | `direct` | 🟢 1.00 |  |
| `IsArchived` | `Deleted` | `coalesce_or` | 🟡 0.80 | Coalesce with Deleted â€” either flag marks record as inactive |
| `CreatedAt` | `AddedAt` | `direct` | 🟢 1.00 |  |
| `UpdatedAt` | `UpdatedAt` | `direct` | 🟢 1.00 |  |
| `CreatedBy` | `AddedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |
| `UpdatedBy` | `UpdatedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |

### `EmpHist` → `Work_History`

_Employment history records_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Hist_ID` | `ID` | `direct` | 🟢 0.95 |  |
| `Emp_ID` | `ApplicationID` | `cast_to_nvarchar` | 🟡 0.85 | Links via Emp_Profile to Person |
| `PlaceofWork` | `CompanyName` | `direct` | 🟢 0.95 |  |
| `Title` | `PositionTitle` | `direct` | 🟢 1.00 |  |
| `Started_At` | `StartDate` | `cast_to_date` | 🟢 1.00 |  |
| `Ended_At` | `EndDate` | `cast_to_date` | 🟢 1.00 |  |

### `Referees` → `References`

_Referee records_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Referee_ID` | `ID` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `Fullname` | `Fullname` | `direct` | 🟢 1.00 |  |
| `email` | `Email` | `direct` | 🟢 1.00 |  |
| `Telephone` | `PhoneContact` | `direct` | 🟢 0.95 | Column renamed |
| `Company` | `CompanyName` | `direct` | 🟢 1.00 |  |
| `Job_Title` | `PositionTitle` | `direct` | 🟢 0.95 |  |

---

## Users

### `Recruiter` → `User`

_System users â€” recruiters become Users in the target_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `RecruiterID` | `UserID` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `Username` | `Loginname` | `direct` | 🟢 1.00 |  |
| `Fullname` | `FullName` | `direct` | 🟢 1.00 |  |
| `email` | `Email` | `direct` | 🟢 1.00 |  |
| `ReportsTo` | `ManagerId` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `Role_ID` | `Role` | `lookup_roles_table` | 🟡 0.88 | Join Roles table to get description |
| `CreatedAt` | `EnteredDateTime` | `direct` | 🟢 1.00 |  |
| `UpdatedAt` | `UpdatedDateTime` | `direct` | 🟢 1.00 |  |

---

## Jobs

### `Req` → `Position`

_Job requisitions split across Position and Position_Details in target_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `ReqID` | `ID` | `direct` | 🟢 0.95 |  |
| `Req_Title` | `PositionName` | `direct` | 🟢 1.00 |  |
| `AccountID` | `CompanyID` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `AssociateID` | `ContactID` | `direct` | 🟢 0.90 |  |
| `Req_Description` | `PositionDesc` | `direct` | 🟢 1.00 |  |
| `StartDate` | `DateBegins` | `cast_to_date` | 🟢 1.00 |  |
| `EndDate` | `DateEnds` | `cast_to_date` | 🟢 1.00 |  |
| `ExpiryDate` | `DatePublished` | `direct` | 🟡 0.80 | Closest semantic match â€” verify with business |
| `CurrencyCode` | `Currency` | `direct` | 🟢 1.00 |  |
| `Address_ID` | `PositionLocationID` | `cast_to_nvarchar` | 🟡 0.88 |  |
| `Deleted` | `Deleted` | `direct` | 🟢 1.00 |  |
| `CreatedBy` | `Addedby` | `cast_to_nvarchar` | 🟢 1.00 |  |
| `CreatedAt` | `Addedat` | `direct` | 🟢 1.00 |  |
| `UpdatedBy` | `UpdatedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |
| `UpdatedAt` | `UpdatedAt` | `direct` | 🟢 1.00 |  |

### `Req_Rates` → `Position`

_Rate data from Req_Rates is folded into the Position table_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Payrate` | `PositionPayRate` | `direct` | 🟢 0.95 |  |
| `BillRate` | `PositionChargeRate` | `direct` | 🟢 0.95 |  |
| `Salary` | `Salary` | `cast_to_nvarchar` | 🟡 0.88 | DECIMAL to NVARCHAR |

---

## Placements

### `Req_Hired` → `Placements`

_Hired records with Hired_Status=1 become confirmed Placements_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Req_HiredID` | `ID` | `direct` | 🟢 0.95 |  |
| `Associate_ID` | `ApplicantID` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `Req_ID` | `PositionID` | `direct` | 🟢 0.95 |  |
| `Account_ID` | `CompanyID` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `StartDate` | `StartDate` | `cast_to_date` | 🟢 1.00 |  |
| `EndDate` | `EndDate` | `cast_to_date` | 🟢 1.00 |  |
| `FeeValue` | `Fee` | `cast_to_float` | 🟢 0.95 |  |
| `CurrencyCode` | `EmploymentType` | `lookup` | 🔴 0.65 | Low confidence â€” values may not align. Verify with business. |
| `Hired_Status` | `Status` | `bit_to_status_text` | 🟡 0.85 | 1=Placed, 0=Pipeline |
| `Owner_ID` | `OwnerID` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `CreatedBy` | `AddedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |
| `CreatedAt` | `AddedAt` | `direct` | 🟢 1.00 |  |
| `UpdatedBy` | `UpdatedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |

---

## Compliance

### `GDPR_Consent` → `Marketing`

_GDPR consent flags map directly to Marketing preferences_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Person_ID` | `ApplicantID` | `cast_to_nvarchar` | 🟢 0.95 |  |
| `Email` | `MarketingEmail` | `direct` | 🟢 1.00 |  |
| `Phone` | `MarketingPhone` | `direct` | 🟢 1.00 |  |
| `Text` | `MarketingText` | `direct` | 🟢 1.00 |  |
| `Email` | `GDPRConsent` | `coalesce_any_true` | 🟡 0.88 | GDPRConsent=true if any channel is opted in |

---

## Documents

### `CV_Docs` → `Attachments`

_CV_Docs and Documents both merge into unified Attachments table. Junction tables handle ownership._

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Doc_ID` | `AttachmentID` | `direct` | 🟢 0.95 |  |
| `Path` | `FilePath` | `direct` | 🟢 1.00 |  |
| `Desc` | `Description` | `direct` | 🟢 1.00 |  |
| `CV_AssocID` | `ApplicantID` | `cast_to_nvarchar` | 🟢 0.90 | Written to ApplicantAttachment junction table |
| `AgencyCV` | `AttachmentType` | `bit_to_type_text` | 🟡 0.85 | 1=Agency CV, 0=Candidate CV |
| `Deleted` | `IsDeleted` | `direct` | 🟢 1.00 |  |

---

## Timesheets

### `TimeSheets` → `Timesheets`

_Direct structural equivalent_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `ID` | `ID` | `direct` | 🟢 1.00 |  |
| `StartDate` | `StartDate` | `direct` | 🟢 1.00 |  |
| `Enddate` | `EndDate` | `direct` | 🟢 1.00 |  |
| `Payrate` | `Payrate` | `direct` | 🟢 1.00 |  |
| `Billrate` | `ChargeRate` | `direct` | 🟢 1.00 | Column renamed |
| `Status` | `Status` | `direct` | 🟢 1.00 |  |

### `TimesheetItems` → `TimesheetActivity`

_Timesheet line items_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `ItemID` | `ActivityID` | `direct` | 🟢 0.90 |  |
| `Timesheet_ID` | `TimesheetID` | `direct` | 🟢 1.00 |  |
| `TotalHours` | `HoursWorked` | `direct` | 🟢 1.00 |  |
| `Person_ID` | `AssocID` | `direct` | 🟡 0.88 |  |
| `CreatedBy` | `AddedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |
| `CreatedAt` | `AddedAt` | `direct` | 🟢 1.00 |  |

---

## Finance

### `PONo` → `PurchaseOrder`

_Purchase orders map directly. Line items go to PurchaseOrderItems._

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `PONo` | `PONo` | `direct` | 🟢 1.00 |  |
| `VendorID` | `CompanyID` | `cast_to_nvarchar` | 🟢 0.95 | VendorID references Accounts/Client |
| `POStatus` | `Status` | `direct` | 🟢 1.00 |  |
| `Amount` | `POAmount` | `cast_to_decimal` | 🟢 0.95 |  |
| `Issue_Date` | `PODate` | `cast_to_date` | 🟢 1.00 |  |
| `CreatedAt` | `AddedAt` | `direct` | 🟢 1.00 |  |
| `CreatedBy` | `AddedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |

### `Invoice` → `Invoice`

_Invoice records â€” largely direct equivalent_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `InvoiceID` | `ID` | `direct` | 🟢 1.00 |  |
| `Invoice_No` | `InvoiceNo` | `direct` | 🟢 1.00 |  |
| `Amount` | `Amount` | `cast_to_decimal` | 🟢 1.00 |  |
| `InvoiceDate` | `InvoiceDate` | `direct` | 🟢 1.00 |  |
| `DateDue` | `DueDate` | `direct` | 🟢 1.00 |  |
| `Status` | `Status` | `direct` | 🟢 1.00 |  |
| `Currency` | `Currency` | `direct` | 🟢 1.00 |  |
| `CreatedBy` | `AddedBy` | `cast_to_nvarchar` | 🟢 1.00 |  |

---

## Leads

### `Leads` → `Leads`

_Lead records â€” mostly direct but status values may differ_

| Source Column | Target Column | Transform | Confidence | Notes |
|---|---|---|---|---|
| `Lead_ID` | `ID` | `direct` | 🟢 0.95 |  |
| `Lead_Status` | `PipelineStage` | `lookup` | 🟡 0.80 | Status values likely differ â€” mapping table required |
| `Lead_Source` | `Source` | `direct` | 🟢 0.92 |  |
| `Email` | `CommID` | `insert_to_comms` | 🟡 0.88 | Target uses polymorphic Comms table â€” insert row, store ID |
| `Phone` | `CommID` | `insert_to_comms` | 🟡 0.88 | As above for phone |
| `Note` | `Notes` | `direct` | 🟢 1.00 |  |
| `Lead_Score` | `PipelineStage` | `score_to_stage` | 🟡 0.72 | Score 1-5 mapped to pipeline stage text â€” verify mapping with business |

---
