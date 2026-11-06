/* =============================================================================
   02_entity_trace.sql  —  follow ONE placement through every linked table
   Database: RecruitCRM_Legacy

   Example: placement Req_HiredID = 98 (contract placement, no planted defects)
       client account 6 · client contact = associate 122 · job 168 · contractor = person 354
   It touches 30+ tables: account, contact, job, rates, PO, timesheets, invoices,
   and the contractor's profile, history, education, references, CV, checks,
   interviews, hotlists, documents, consent, tags, notes and audit log.

   HOW TO USE (DBeaver)
     * Ctrl+Enter on any query, or Alt+X for all (one result tab per query).
     * Every query starts from the same anchor:  Req_HiredID = 98
       To trace another placement: Ctrl+F -> replace "Req_HiredID = 98" with e.g. "Req_HiredID = 197".
     * Columns named chk_* say whether that link is correct: N'✔' or N'✘ <reason>'.
       On this example every chk_* column should be ✔.
   ========================================================================== */


/* ── 0. THE PLACEMENT ───────────────────────────────────────────────────────── */

-- 0.1  Placement with every foreign key resolved to a readable name
SELECT h.Req_HiredID, h.Pipeline_Stage, h.Worktype, h.StartDate, h.EndDate, h.FeeValue, h.CurrencyCode,
       h.Account_ID,        a.Account_name,
       h.Associate_ID AS client_contact_associate, cp.First_Name + ' ' + cp.Last_Name AS client_contact,
       h.Req_ID,            r.Req_Title,
       h.Invoiced_PersonID AS contractor_person, p.First_Name + ' ' + p.Last_Name AS contractor,
       h.RateID,            ar.Chargerate, ar.Payrate AS account_payrate,
       h.Owner_ID,          o.Fullname AS owner, h.Second_OwnerID, o2.Fullname AS second_owner,
       h.CreatedBy,         cb.Fullname AS created_by
FROM dbo.Req_Hired h
LEFT JOIN dbo.Accounts a     ON a.Account_ID = h.Account_ID
LEFT JOIN dbo.Associates s   ON s.AssociateID = h.Associate_ID
LEFT JOIN dbo.Person cp      ON cp.Person_ID = s.Person_ID
LEFT JOIN dbo.Req r          ON r.ReqID = h.Req_ID
LEFT JOIN dbo.Person p       ON p.Person_ID = h.Invoiced_PersonID
LEFT JOIN dbo.AccountRate ar ON ar.Rate_ID = h.RateID
LEFT JOIN dbo.Recruiter o    ON o.RecruiterID = h.Owner_ID
LEFT JOIN dbo.Recruiter o2   ON o2.RecruiterID = h.Second_OwnerID
LEFT JOIN dbo.Recruiter cb   ON cb.RecruiterID = h.CreatedBy
WHERE h.Req_HiredID = 98;

-- 0.2  Link checks on the placement itself
SELECT h.Req_HiredID,
       CASE WHEN a.Account_ID IS NULL THEN N'✘ account missing' ELSE N'✔' END                          AS chk_account_exists,
       CASE WHEN r.AccountID = h.Account_ID THEN N'✔' ELSE N'✘ job is for another account' END          AS chk_job_same_account,
       -- NULL contact = the account has no contacts on file (allowed)
       CASE WHEN h.Associate_ID IS NULL OR EXISTS (SELECT 1 FROM dbo.AccountAssociates aa WHERE aa.AssociateID = h.Associate_ID AND aa.AccountID = h.Account_ID)
            THEN N'✔' ELSE N'✘ contact not at this account' END                                         AS chk_contact_at_account,
       -- the person placed must be a candidate; a contact is allowed only if also typed 'Candidate' (dual-role edge case)
       CASE WHEN NOT EXISTS (SELECT 1 FROM dbo.Associates x WHERE x.Person_ID = h.Invoiced_PersonID)
              OR EXISTS (SELECT 1 FROM dbo.Associates dx JOIN dbo.AssociateTypeRelation dr ON dr.AssociateID = dx.AssociateID JOIN dbo.AssociateTypes dt ON dt.Associate_TypeID = dr.TypeID WHERE dx.Person_ID = h.Invoiced_PersonID AND dt.TypeName = 'Candidate')
            THEN N'✔' ELSE N'✘ contractor is a client contact' END                                      AS chk_contractor_is_candidate,
       -- pipeline rows that never started (Applied, Screening...) have no dates
       CASE WHEN h.StartDate IS NULL OR h.EndDate IS NULL OR h.EndDate >= h.StartDate THEN N'✔' ELSE N'✘ ends before it starts' END AS chk_dates,
       CASE WHEN h.StartDate IS NULL OR CAST(h.StartDate AS date) >= CAST(r.CreatedAt AS date) THEN N'✔' ELSE N'✘ starts before job raised' END AS chk_after_job_raised,
       CASE WHEN ar.Account_ID = h.Account_ID OR h.RateID IS NULL THEN N'✔' ELSE N'✘ rate card of another account' END AS chk_rate_card
FROM dbo.Req_Hired h
LEFT JOIN dbo.Accounts a     ON a.Account_ID = h.Account_ID
LEFT JOIN dbo.Req r          ON r.ReqID = h.Req_ID
LEFT JOIN dbo.AccountRate ar ON ar.Rate_ID = h.RateID
WHERE h.Req_HiredID = 98;


/* ── A. CLIENT SIDE ─────────────────────────────────────────────────────────── */

-- A.1  Client account + its lookups and addresses
SELECT a.Account_ID, a.Account_name, a.Industry, a.Website, a.Terms, a.Deleted,
       a.AccountTypeID, ty.Description AS account_type, a.AccountStatusTypeID, st.Description AS account_status,
       a.DeptID, d.Name AS department, a.Division_ID, dv.Division_Name AS division,
       a.AddressID, ad.Address_line1 + ', ' + ad.City + ' ' + ad.ZipCode AS office, ad.Email AS office_email,
       a.InvoiceAddressID, a.ParentAccountID, a.RateID,
       CASE WHEN ad.Email LIKE '%@' + w.host OR a.Website IS NULL OR ISNULL(ad.Email, '') NOT LIKE '%@%'   -- no email on file
            THEN N'✔' ELSE N'✘ office email not on account domain' END AS chk_email_domain
FROM dbo.Req_Hired h
JOIN dbo.Accounts a            ON a.Account_ID = h.Account_ID
-- website host only: strip scheme, www. and any path (e.g. https://www.barclays.co.uk/innovation -> barclays.co.uk)
CROSS APPLY (SELECT REPLACE(REPLACE(REPLACE(ISNULL(a.Website, ''), 'https://', ''), 'http://', ''), 'www.', '') AS h1) w1
CROSS APPLY (SELECT LEFT(w1.h1, CHARINDEX('/', w1.h1 + '/') - 1) AS host) w
LEFT JOIN dbo.AccountType ty   ON ty.AccountTypeID = a.AccountTypeID
LEFT JOIN dbo.AccountStatus st ON st.Account_StatusID = a.AccountStatusTypeID
LEFT JOIN dbo.Departments d    ON d.DepartmentID = a.DeptID
LEFT JOIN dbo.Division dv      ON dv.DivisionID = a.Division_ID
LEFT JOIN dbo.Addresses ad     ON ad.AddressID = a.AddressID
WHERE h.Req_HiredID = 98;

-- A.2  Account rate cards (AccountRate.Account_ID -> Accounts)
SELECT ar.*, CASE WHEN ar.Account_ID = h.Account_ID THEN N'✔' ELSE N'✘' END AS chk_same_account
FROM dbo.Req_Hired h JOIN dbo.AccountRate ar ON ar.Account_ID = h.Account_ID
WHERE h.Req_HiredID = 98;

-- A.3  The client contact on the placement: Associates -> Person -> address, role, consent, type
SELECT s.AssociateID, s.AssociateTitle, p.First_Name, p.Last_Name, p.Person_ID, p.Associate AS flag_associate, p.Emp AS flag_emp,
       r.Description AS role, s.Associate_AddressID, ad.Address_line1 + ', ' + ad.City AS contact_address,
       g.GDPR_ConsentID, g.Email AS consent_email, g.Phone AS consent_phone,
       (SELECT STRING_AGG(t.TypeName, ', ') FROM dbo.AssociateTypeRelation tr JOIN dbo.AssociateTypes t ON t.Associate_TypeID = tr.TypeID
         WHERE tr.AssociateID = s.AssociateID) AS types,
       CASE WHEN s.Associate_AddressID = a.AddressID THEN N'✔' ELSE N'✘ not the account office' END AS chk_office_address,
       CASE WHEN g.GDPR_ConsentID IS NULL OR g.Person_ID = p.Person_ID THEN N'✔' ELSE N'✘ consent belongs to someone else' END AS chk_consent_owner,
       CASE WHEN p.Associate = 1 AND EXISTS (SELECT 1 FROM dbo.AssociateTypeRelation tr JOIN dbo.AssociateTypes t ON t.Associate_TypeID = tr.TypeID
                                           WHERE tr.AssociateID = s.AssociateID AND t.TypeName = 'Contact')
            THEN N'✔' ELSE N'✘ role flags/type' END AS chk_role
FROM dbo.Req_Hired h
JOIN dbo.Associates s ON s.AssociateID = h.Associate_ID
JOIN dbo.Person p     ON p.Person_ID = s.Person_ID
JOIN dbo.Accounts a   ON a.Account_ID = h.Account_ID
LEFT JOIN dbo.Roles r ON r.Role_ID = s.Associate_RoleID
LEFT JOIN dbo.Addresses ad   ON ad.AddressID = s.Associate_AddressID
LEFT JOIN dbo.GDPR_Consent g ON g.GDPR_ConsentID = p.GDPRConsent_ID
WHERE h.Req_HiredID = 98;

-- A.4  All contacts of the account (AccountAssociates)
SELECT aa.AccountAssociateID, aa.AssociateID, s.AssociateTitle, p.First_Name + ' ' + p.Last_Name AS contact, s.Active,
       CASE WHEN s.Associate_AddressID = a.AddressID THEN N'✔' ELSE N'✘' END AS chk_office_address
FROM dbo.Req_Hired h
JOIN dbo.Accounts a          ON a.Account_ID = h.Account_ID
JOIN dbo.AccountAssociates aa ON aa.AccountID = a.Account_ID
JOIN dbo.Associates s        ON s.AssociateID = aa.AssociateID
JOIN dbo.Person p            ON p.Person_ID = s.Person_ID
WHERE h.Req_HiredID = 98;

-- A.5  Leads for the account (lead contact must be one of the account's contacts)
SELECT l.Lead_ID, l.Lead_Name, l.Lead_Status, l.Associate_ID, l.Req_ID, l.Assigned_To, rc.Fullname AS assigned_to,
       CASE WHEN l.Associate_ID IS NULL OR EXISTS (SELECT 1 FROM dbo.AccountAssociates aa
            WHERE aa.AssociateID = l.Associate_ID AND aa.AccountID = l.Account_ID) THEN N'✔' ELSE N'✘' END AS chk_contact_at_account
FROM dbo.Req_Hired h
JOIN dbo.Leads l ON l.Account_ID = h.Account_ID
LEFT JOIN dbo.Recruiter rc ON rc.RecruiterID = l.Assigned_To
WHERE h.Req_HiredID = 98;

-- A.6  Tags, notes and documents on the account (polymorphic links: type + id)
SELECT 'Tag' AS kind, CAST(te.TagEntity_ID AS varchar(20)) AS id, tg.Tag_Name AS info
FROM dbo.Req_Hired h JOIN dbo.TagEntity te ON te.EntityType = 'Account' AND te.EntityID = h.Account_ID
LEFT JOIN dbo.Tags tg ON tg.ID = te.TagID WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'Note', CAST(n.Note_ID AS varchar(20)), LEFT(n.Notetext, 100)
FROM dbo.Req_Hired h JOIN dbo.Notes n ON n.ObjectType = 'Account' AND n.ObjectId = h.Account_ID WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'Document', CAST(d.Doc_ID AS varchar(20)), d.[Desc]
FROM dbo.Req_Hired h JOIN dbo.Documents d ON d.ObjectType = 'Account' AND d.Doc_AssocID = h.Account_ID WHERE h.Req_HiredID = 98;


/* ── B. THE JOB ─────────────────────────────────────────────────────────────── */

-- B.1  Job (Req) and its links
SELECT r.ReqID, r.Req_Title, r.Worktype, r.StatusText, r.StartDate, r.EndDate, r.CreatedAt, r.PONumber,
       r.AccountID, r.AssociateID AS hiring_manager, r.Req_RateID, r.Address_ID,
       CASE WHEN r.AccountID = h.Account_ID THEN N'✔' ELSE N'✘' END AS chk_same_account,
       CASE WHEN r.AssociateID IS NULL OR EXISTS (SELECT 1 FROM dbo.AccountAssociates aa
            WHERE aa.AssociateID = r.AssociateID AND aa.AccountID = r.AccountID) THEN N'✔' ELSE N'✘' END AS chk_manager_at_account,
       CASE WHEN r.Address_ID = a.AddressID THEN N'✔' ELSE N'✘ not the client office' END AS chk_job_address,
       CASE WHEN r.PONumber IS NULL OR EXISTS (SELECT 1 FROM dbo.PONo po WHERE po.PONo = r.PONumber AND po.ReqID = r.ReqID)
            THEN N'✔' ELSE N'✘ PO funds another job' END AS chk_po
FROM dbo.Req_Hired h
JOIN dbo.Req r      ON r.ReqID = h.Req_ID
JOIN dbo.Accounts a ON a.Account_ID = r.AccountID
WHERE h.Req_HiredID = 98;

-- B.2  Job rates — two-way link: Req.Req_RateID -> Req_Rates and Req_Rates.Req_ID -> Req
SELECT rr.Req_RateID, rr.Req_ID, rr.Payrate AS day_pay, rr.BillRate AS day_bill, rr.Salary, rr.Notes,
       CASE WHEN rr.Req_ID = r.ReqID AND r.Req_RateID = rr.Req_RateID THEN N'✔' ELSE N'✘' END AS chk_two_way,
       CASE WHEN rr.Payrate IS NULL AND rr.Salary > 0 THEN N'✔'                       -- permanent job: salary, no day rates
            WHEN rr.BillRate >= rr.Payrate AND rr.Payrate > 0 THEN N'✔' ELSE N'✘ margin' END AS chk_margin
FROM dbo.Req_Hired h
JOIN dbo.Req r        ON r.ReqID = h.Req_ID
JOIN dbo.Req_Rates rr ON rr.Req_RateID = r.Req_RateID
WHERE h.Req_HiredID = 98;

-- B.3  Purchase orders funding the job (PO client = job client)
SELECT po.PONo, po.VendorID, po.ReqID, po.POStatus, po.Issue_Date, po.DateDue, po.Amount, po.TaxAmount, po.ApprovedBy,
       CASE WHEN po.VendorID = r.AccountID THEN N'✔' ELSE N'✘ PO client <> job client' END AS chk_vendor
FROM dbo.Req_Hired h
JOIN dbo.Req r   ON r.ReqID = h.Req_ID
JOIN dbo.PONo po ON po.ReqID = r.ReqID
WHERE h.Req_HiredID = 98;

-- B.4  Everyone in this job's pipeline
SELECT x.Req_HiredID, x.Pipeline_Stage, x.Invoiced_PersonID, p.First_Name + ' ' + p.Last_Name AS candidate,
       CASE WHEN x.Req_HiredID = h.Req_HiredID THEN '<- this placement' ELSE '' END AS note
FROM dbo.Req_Hired h
JOIN dbo.Req_Hired x ON x.Req_ID = h.Req_ID
LEFT JOIN dbo.Person p ON p.Person_ID = x.Invoiced_PersonID
WHERE h.Req_HiredID = 98;

-- B.5  Job documents and notes
SELECT 'Req_Documents' AS kind, CAST(rd.ReqDocument_ID AS varchar(20)) AS id, d.[Desc] AS info
FROM dbo.Req_Hired h JOIN dbo.Req_Documents rd ON rd.Req_ID = h.Req_ID
LEFT JOIN dbo.Documents d ON d.Doc_ID = rd.Document_ID WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'Note', CAST(n.Note_ID AS varchar(20)), LEFT(n.Notetext, 100)
FROM dbo.Req_Hired h JOIN dbo.Notes n ON n.ObjectType = 'Req' AND n.ObjectId = h.Req_ID WHERE h.Req_HiredID = 98;


/* ── C. THE CONTRACTOR (candidate) ──────────────────────────────────────────── */

-- C.1  Person + flags + consent
SELECT p.Person_ID, p.First_Name, p.Middle_name, p.Last_Name, p.DOB, p.Associate AS flag_associate, p.Emp AS flag_emp, p.Deleted,
       g.GDPR_ConsentID, g.Email AS consent_email, g.Text AS consent_text, g.Phone AS consent_phone,
       -- a contractor is a candidate (no Associates row); Emp flag = has an employee profile (not every contractor has one)
       CASE WHEN (p.Associate = 0 OR EXISTS (SELECT 1 FROM dbo.Associates dx JOIN dbo.AssociateTypeRelation dr ON dr.AssociateID = dx.AssociateID JOIN dbo.AssociateTypes dt ON dt.Associate_TypeID = dr.TypeID WHERE dx.Person_ID = p.Person_ID AND dt.TypeName = 'Candidate'))
             AND p.Emp = CASE WHEN EXISTS (SELECT 1 FROM dbo.Emp_Profile e WHERE e.Person_ID = p.Person_ID) THEN 1 ELSE 0 END
            THEN N'✔' ELSE N'✘ role flags' END AS chk_flags,
       CASE WHEN g.GDPR_ConsentID IS NULL OR g.Person_ID = p.Person_ID THEN N'✔' ELSE N'✘ consent belongs to someone else' END AS chk_consent_owner
FROM dbo.Req_Hired h
JOIN dbo.Person p ON p.Person_ID = h.Invoiced_PersonID
LEFT JOIN dbo.GDPR_Consent g ON g.GDPR_ConsentID = p.GDPRConsent_ID
WHERE h.Req_HiredID = 98;

-- C.2  Employee profile (one per person; notes start with the person's own name)
SELECT e.Emp_ProfileID, e.Emp_No, e.Emp_TypeDescription, e.NI_number, e.SortCode, LEFT(e.Profile_Notes, 80) AS profile_notes,
       CASE WHEN e.Profile_Notes LIKE p.First_Name + ' ' + p.Last_Name + '%' THEN N'✔' ELSE N'✘ notes name another person' END AS chk_notes_name
FROM dbo.Req_Hired h
JOIN dbo.Person p       ON p.Person_ID = h.Invoiced_PersonID
JOIN dbo.Emp_Profile e  ON e.Person_ID = p.Person_ID
WHERE h.Req_HiredID = 98;

-- C.3  Work history (EmpHist.Emp_ID -> Emp_Profile.Emp_ProfileID)
SELECT eh.Hist_ID, eh.Emp_ID, eh.PlaceofWork, eh.Title, eh.Started_At, eh.Ended_At,
       CASE WHEN eh.Ended_At IS NULL OR eh.Ended_At >= eh.Started_At THEN N'✔' ELSE N'✘ ends before it starts' END AS chk_dates
FROM dbo.Req_Hired h
JOIN dbo.Emp_Profile e ON e.Person_ID = h.Invoiced_PersonID
JOIN dbo.EmpHist eh    ON eh.Emp_ID = e.Emp_ProfileID
WHERE h.Req_HiredID = 98
ORDER BY eh.Started_At;

-- C.4  Education (EmpEdu.Emp_ID -> Emp_Profile.Emp_ProfileID)
SELECT ed.Edu_ID, ed.Emp_ID, ed.Institution, ed.AwardTitle, ed.EducationLevel, ed.Grade, ed.StartDate, ed.EndDate, ed.IsHighestLevel
FROM dbo.Req_Hired h
JOIN dbo.Emp_Profile e ON e.Person_ID = h.Invoiced_PersonID
JOIN dbo.EmpEdu ed     ON ed.Emp_ID = e.Emp_ProfileID
WHERE h.Req_HiredID = 98;

-- C.5  References (EmpRef.EmpNo -> Emp_Profile.Emp_No ; EmpRef.Ref_ID -> Referees)
SELECT er.EmpRef_ID, er.EmpNo, er.Status, er.Relationship, rf.Referee_ID, rf.Fullname AS referee, rf.Company, rf.Job_Title, rf.email,
       LEFT(er.Reference, 80) AS reference_text
FROM dbo.Req_Hired h
JOIN dbo.Emp_Profile e ON e.Person_ID = h.Invoiced_PersonID
JOIN dbo.EmpRef er     ON er.EmpNo = e.Emp_No
LEFT JOIN dbo.Referees rf ON rf.Referee_ID = er.Ref_ID
WHERE h.Req_HiredID = 98;

-- C.6  Documents: employee documents, CV, background checks
SELECT 'Emp_Documents' AS kind, CAST(x.EmpDocument_ID AS varchar(20)) AS id, d.[Desc] AS info, dt.[Desc] AS doc_type,
       CASE WHEN x.Person_ID = h.Invoiced_PersonID THEN N'✔' ELSE N'✘ document filed under another person' END AS chk_owner
FROM dbo.Req_Hired h JOIN dbo.Emp_Profile e ON e.Person_ID = h.Invoiced_PersonID
JOIN dbo.Emp_Documents x ON x.Emp_ID = e.Emp_ProfileID
LEFT JOIN dbo.Documents d ON d.Doc_ID = x.Document_ID LEFT JOIN dbo.DocumentType dt ON dt.Doc_TypeID = d.Typeid
WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'CV_Docs', CAST(c.Doc_ID AS varchar(20)), c.[Desc] + ' (' + c.Path + ')', NULL, N'✔'
FROM dbo.Req_Hired h JOIN dbo.CV_Docs c ON c.CV_AssocID = h.Invoiced_PersonID WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'BackgroundChecks', CAST(b.Check_ID AS varchar(20)), b.Check_Type + ': ' + ISNULL(LEFT(b.Notes, 60), ''), dt.[Desc],
       CASE WHEN b.Doc_ID IS NULL OR d.Doc_ID IS NOT NULL THEN N'✔' ELSE N'✘ evidence document missing' END
FROM dbo.Req_Hired h JOIN dbo.BackgroundChecks b ON b.Person_ID = h.Invoiced_PersonID
LEFT JOIN dbo.Documents d ON d.Doc_ID = b.Doc_ID LEFT JOIN dbo.DocumentType dt ON dt.Doc_TypeID = d.Typeid
WHERE h.Req_HiredID = 98;

-- C.7  Interviews (interviewee = this contractor; interviewers must be client contacts)
SELECT f.Interview_FeedbackID, f.Interview_Date, f.Callback,
       f.Interviewer_ID, i1.First_Name + ' ' + i1.Last_Name AS interviewer,
       f.Second_InterviewerID, i2.First_Name + ' ' + i2.Last_Name AS second_interviewer,
       CASE WHEN EXISTS (SELECT 1 FROM dbo.Associates s WHERE s.Person_ID = f.Interviewer_ID) THEN N'✔' ELSE N'✘ interviewer not a contact' END AS chk_interviewer,
       LEFT(f.Notes, 80) AS feedback
FROM dbo.Req_Hired h
JOIN dbo.Interview_Feedback f ON f.Interviewee_ID = h.Invoiced_PersonID
LEFT JOIN dbo.Person i1 ON i1.Person_ID = f.Interviewer_ID
LEFT JOIN dbo.Person i2 ON i2.Person_ID = f.Second_InterviewerID
WHERE h.Req_HiredID = 98;

-- C.8  Meetings, hotlists, tags, notes for the contractor
SELECT 'Schedule' AS kind, CAST(sc.Schedule_ID AS varchar(20)) AS id, sc.ScheduleType + ' (' + sc.Person_Type + ') ' + CONVERT(varchar(16), sc.StartDate, 120) AS info,
       CASE WHEN sc.Person_Type = 'Candidate' OR EXISTS (SELECT 1 FROM dbo.Associates dx JOIN dbo.AssociateTypeRelation dr ON dr.AssociateID = dx.AssociateID JOIN dbo.AssociateTypes dt ON dt.Associate_TypeID = dr.TypeID WHERE dx.Person_ID = sc.Person_ID AND dt.TypeName = 'Candidate') THEN N'✔' ELSE N'✘ booked as a contact' END AS chk
FROM dbo.Req_Hired h JOIN dbo.Schedule sc ON sc.Person_ID = h.Invoiced_PersonID WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'Hotlist', CAST(oh.ObjHotlistID AS varchar(20)), hl.Name + ' - ' + ISNULL(hl.[Desc], ''), N'✔'
FROM dbo.Req_Hired h JOIN dbo.ObjectHotlist oh ON oh.Person_ID = h.Invoiced_PersonID
LEFT JOIN dbo.Hotlists hl ON hl.Hotlist_ID = oh.Hotlist_ID WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'Tag', CAST(te.TagEntity_ID AS varchar(20)), tg.Tag_Name, N'✔'
FROM dbo.Req_Hired h JOIN dbo.TagEntity te ON te.EntityType = 'Person' AND te.EntityID = h.Invoiced_PersonID
LEFT JOIN dbo.Tags tg ON tg.ID = te.TagID WHERE h.Req_HiredID = 98
UNION ALL
SELECT 'Note', CAST(n.Note_ID AS varchar(20)), LEFT(n.Notetext, 100), N'✔'
FROM dbo.Req_Hired h JOIN dbo.Notes n ON n.ObjectType = 'Person' AND n.ObjectId = h.Invoiced_PersonID WHERE h.Req_HiredID = 98;


/* ── D. TIME & MONEY ────────────────────────────────────────────────────────── */

-- D.1  Timesheets worked on this placement (week inside placement, rates from job day rate / 7.5)
SELECT t.ID AS timesheet_id, t.StartDate AS week_start, t.Enddate AS week_end, tt.[Desc] AS type, tt.Billable,
       t.Status, t.Approved_Date, ap.Fullname AS approved_by, t.PONo,
       t.Payrate AS hourly_pay, t.Billrate AS hourly_bill, rr.Payrate AS job_day_pay, rr.BillRate AS job_day_bill,
       CASE WHEN t.StartDate >= CAST(h.StartDate AS date) AND t.Enddate <= CAST(h.EndDate AS date)
            THEN N'✔' ELSE N'✘ week outside placement' END                                         AS chk_in_placement,
       CASE WHEN DATEDIFF(day, t.StartDate, t.Enddate) = 6 AND DATENAME(weekday, t.StartDate) = 'Monday'
            THEN N'✔' ELSE N'✘ not Mon-Sun' END                                                     AS chk_week,
       CASE WHEN ABS(t.Payrate - ROUND(rr.Payrate / 7.5 * CASE t.Timesheet_TypeID WHEN 2 THEN 1.5 WHEN 4 THEN 0 WHEN 5 THEN 0 ELSE 1 END, 2)) <= 0.01
            THEN N'✔' ELSE N'✘ pay rate' END                                                         AS chk_pay_rate,
       CASE WHEN t.PONo IS NULL OR EXISTS (SELECT 1 FROM dbo.PONo po WHERE po.PONo = t.PONo AND po.ReqID = h.Req_ID)
            THEN N'✔' ELSE N'✘ PO of another job' END                                               AS chk_po,
       CASE WHEN (t.Status = 'Approved' AND t.Approved_Date > t.Enddate AND t.Approved_By IS NOT NULL)
              OR (t.Status <> 'Approved' AND t.Approved_Date IS NULL) THEN N'✔' ELSE N'✘ approval' END AS chk_approval
FROM dbo.Req_Hired h
JOIN dbo.Req_Rates rr ON rr.Req_ID = h.Req_ID
JOIN dbo.TimeSheets t ON t.ID IN (SELECT i.Timesheet_ID FROM dbo.TimesheetItems i
                                  WHERE i.Req_ID = h.Req_ID AND i.Person_ID = h.Invoiced_PersonID)
LEFT JOIN dbo.TimesheetType tt ON tt.Timesheet_TypeID = t.Timesheet_TypeID
LEFT JOIN dbo.Recruiter ap     ON ap.RecruiterID = t.Approved_By
WHERE h.Req_HiredID = 98
ORDER BY t.StartDate;

-- D.2  Timesheet lines (day worked = CreatedAt date; hours = span minus 30-min break if >= 6h)
SELECT i.ItemID, i.Timesheet_ID, CAST(i.CreatedAt AS date) AS day_worked, DATENAME(weekday, i.CreatedAt) AS weekday,
       i.StartTime, i.EndTime, i.TotalHours,
       CASE WHEN ABS(i.TotalHours - (DATEDIFF(minute, i.StartTime, i.EndTime) / 60.0
                 - CASE WHEN DATEDIFF(minute, i.StartTime, i.EndTime) >= 360 THEN 0.5 ELSE 0 END)) <= 0.01
            THEN N'✔' ELSE N'✘ hours' END                                                     AS chk_hours,
       CASE WHEN CAST(i.CreatedAt AS date) BETWEEN t.StartDate AND t.Enddate THEN N'✔' ELSE N'✘ day outside week' END AS chk_day,
       CASE WHEN i.Timesheet_TypeID = t.Timesheet_TypeID THEN N'✔' ELSE N'✘ type' END        AS chk_type
FROM dbo.Req_Hired h
JOIN dbo.TimesheetItems i ON i.Req_ID = h.Req_ID AND i.Person_ID = h.Invoiced_PersonID
JOIN dbo.TimeSheets t     ON t.ID = i.Timesheet_ID
WHERE h.Req_HiredID = 98
ORDER BY t.StartDate, i.CreatedAt;

-- D.3  Invoice lines billed against this placement + their invoice
SELECT e.Invoice_EntryID, e.[Desc] AS line, e.Quantity, e.Unit_Price, e.Amount,
       inv.InvoiceID, inv.Invoice_No, inv.Status, inv.InvoiceDate, inv.Vendor_ID, inv.PONo, it.Type_Name AS invoice_type,
       CASE WHEN ABS(e.Amount - ROUND(e.Quantity * e.Unit_Price, 2)) <= 0.01 THEN N'✔' ELSE N'✘ qty x price' END AS chk_line_amount,
       CASE WHEN inv.Vendor_ID = h.Account_ID THEN N'✔' ELSE N'✘ invoiced to another client' END           AS chk_invoiced_client
FROM dbo.Req_Hired h
JOIN dbo.InvoiceEntries e ON e.Plac_ID = h.Req_HiredID
JOIN dbo.Invoice inv      ON inv.InvoiceID = e.Invoice_ID
LEFT JOIN dbo.InvoiceTypes it ON it.InvoiceType_ID = inv.InvoiceType_ID
WHERE h.Req_HiredID = 98;

-- D.4  Invoice header arithmetic for those invoices (net = sum of ALL its lines, gross = net + 20% VAT)
SELECT inv.InvoiceID, inv.Invoice_No, inv.Status, inv.NETAmount, l.sum_of_lines, inv.Amount AS gross, inv.Amount_Paid, inv.Balance_Due,
       CASE WHEN ABS(inv.NETAmount - l.sum_of_lines) <= 0.01 THEN N'✔' ELSE N'✘ net <> lines' END              AS chk_net,
       CASE WHEN ABS(inv.Amount - ROUND(inv.NETAmount * 1.2, 2)) <= 0.01 THEN N'✔' ELSE N'✘ VAT' END           AS chk_vat,
       CASE WHEN (inv.Status = 'Cancelled' AND inv.Balance_Due = 0 AND inv.Amount_Paid = 0)
              OR (inv.Status <> 'Cancelled' AND ABS(inv.Balance_Due - (inv.Amount - inv.Amount_Paid)) <= 0.01)
            THEN N'✔' ELSE N'✘ balance' END                                                                    AS chk_balance,
       CASE WHEN inv.PONo IS NULL OR EXISTS (SELECT 1 FROM dbo.PONo po WHERE po.PONo = inv.PONo AND po.VendorID = inv.Vendor_ID)
            THEN N'✔' ELSE N'✘ PO of another client' END                                                       AS chk_po
FROM dbo.Invoice inv
JOIN (SELECT Invoice_ID, SUM(Amount) AS sum_of_lines FROM dbo.InvoiceEntries GROUP BY Invoice_ID) l ON l.Invoice_ID = inv.InvoiceID
WHERE inv.InvoiceID IN (SELECT e.Invoice_ID FROM dbo.InvoiceEntries e JOIN dbo.Req_Hired h ON h.Req_HiredID = e.Plac_ID
                        WHERE h.Req_HiredID = 98);


/* ── E. AUDIT ───────────────────────────────────────────────────────────────── */

-- E.1  Audit-log entries for the account, job, contact and contractor (Log.Entity_Type + Entity_ID)
SELECT lg.LogID, lg.[Timestamp], lg.Entity_Type, lg.Entity_ID, lg.Action, lg.Level, u.Fullname AS user_name, LEFT(lg.message, 70) AS message
FROM dbo.Req_Hired h
JOIN dbo.Log lg ON (lg.Entity_Type = 'Account'   AND lg.Entity_ID = h.Account_ID)
                OR (lg.Entity_Type = 'Req'       AND lg.Entity_ID = h.Req_ID)
                OR (lg.Entity_Type = 'Associate' AND lg.Entity_ID = h.Associate_ID)
                OR (lg.Entity_Type = 'Person'    AND lg.Entity_ID = h.Invoiced_PersonID)
LEFT JOIN dbo.Recruiter u ON u.RecruiterID = lg.User_ID
WHERE h.Req_HiredID = 98
ORDER BY lg.[Timestamp];

-- E.2  SUMMARY — row counts per linked table for this placement (quick completeness view)
SELECT 'Accounts' AS linked_table, (SELECT COUNT(*) FROM dbo.Accounts a JOIN dbo.Req_Hired h ON h.Account_ID = a.Account_ID WHERE h.Req_HiredID = 98) AS rows_linked
UNION ALL SELECT 'AccountAssociates (contacts of account)', (SELECT COUNT(*) FROM dbo.AccountAssociates x JOIN dbo.Req_Hired h ON h.Account_ID = x.AccountID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'Req (job)',            (SELECT COUNT(*) FROM dbo.Req r JOIN dbo.Req_Hired h ON h.Req_ID = r.ReqID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'Req_Rates',            (SELECT COUNT(*) FROM dbo.Req_Rates r JOIN dbo.Req_Hired h ON h.Req_ID = r.Req_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'PONo',                 (SELECT COUNT(*) FROM dbo.PONo p JOIN dbo.Req_Hired h ON h.Req_ID = p.ReqID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'Emp_Profile',          (SELECT COUNT(*) FROM dbo.Emp_Profile e JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = e.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'EmpHist',              (SELECT COUNT(*) FROM dbo.EmpHist x JOIN dbo.Emp_Profile e ON e.Emp_ProfileID = x.Emp_ID JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = e.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'EmpEdu',               (SELECT COUNT(*) FROM dbo.EmpEdu x JOIN dbo.Emp_Profile e ON e.Emp_ProfileID = x.Emp_ID JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = e.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'EmpRef',               (SELECT COUNT(*) FROM dbo.EmpRef x JOIN dbo.Emp_Profile e ON e.Emp_No = x.EmpNo JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = e.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'Emp_Documents',        (SELECT COUNT(*) FROM dbo.Emp_Documents x JOIN dbo.Emp_Profile e ON e.Emp_ProfileID = x.Emp_ID JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = e.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'CV_Docs',              (SELECT COUNT(*) FROM dbo.CV_Docs x JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = x.CV_AssocID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'BackgroundChecks',     (SELECT COUNT(*) FROM dbo.BackgroundChecks x JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = x.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'Interview_Feedback',   (SELECT COUNT(*) FROM dbo.Interview_Feedback x JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = x.Interviewee_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'ObjectHotlist',        (SELECT COUNT(*) FROM dbo.ObjectHotlist x JOIN dbo.Req_Hired h ON h.Invoiced_PersonID = x.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'TimeSheets',           (SELECT COUNT(DISTINCT i.Timesheet_ID) FROM dbo.TimesheetItems i JOIN dbo.Req_Hired h ON h.Req_ID = i.Req_ID AND h.Invoiced_PersonID = i.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'TimesheetItems',       (SELECT COUNT(*) FROM dbo.TimesheetItems i JOIN dbo.Req_Hired h ON h.Req_ID = i.Req_ID AND h.Invoiced_PersonID = i.Person_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'InvoiceEntries',       (SELECT COUNT(*) FROM dbo.InvoiceEntries x WHERE x.Plac_ID IN (SELECT Req_HiredID FROM dbo.Req_Hired h WHERE h.Req_HiredID = 98))
UNION ALL SELECT 'Leads (account)',      (SELECT COUNT(*) FROM dbo.Leads x JOIN dbo.Req_Hired h ON h.Account_ID = x.Account_ID WHERE h.Req_HiredID = 98)
UNION ALL SELECT 'Log entries',          (SELECT COUNT(*) FROM dbo.Log lg JOIN dbo.Req_Hired h ON (lg.Entity_Type = 'Account' AND lg.Entity_ID = h.Account_ID) OR (lg.Entity_Type = 'Req' AND lg.Entity_ID = h.Req_ID) OR (lg.Entity_Type = 'Associate' AND lg.Entity_ID = h.Associate_ID) OR (lg.Entity_Type = 'Person' AND lg.Entity_ID = h.Invoiced_PersonID) WHERE h.Req_HiredID = 98);
