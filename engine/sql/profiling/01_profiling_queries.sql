/* =============================================================================
   01_profiling_queries.sql  —  data discovery & profiling of the legacy source
   Database: Cobaltdesk_Legacy  (SQL Server 2017+)

   HOW TO USE IN DBEAVER
     * Connect to localhost\SQLEXPRESS, database Cobaltdesk_Legacy.
     * Put the cursor inside any query and press Ctrl+Enter to run just that one,
       or Alt+X to run the whole file (each result opens in its own tab).
     * Every check is ONE statement, so DBeaver's ';' splitting is safe.
     * Requires 00_install_profiling.sql (the dq.* procedures) for sections 2-3.

   Each check returns the offending rows (or a summary). An empty result = clean.
   Answer key for planted defects: sql/source/defect_manifest.csv
   ========================================================================== */


/* ─────────────────────────────────────────────────────────────────────────────
   1. INVENTORY
   ───────────────────────────────────────────────────────────────────────────── */

-- 1.1  Tables, row counts, column counts, FK in/out
SELECT  t.name                                   AS table_name,
        SUM(p.rows)                              AS row_count,
        (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id = t.object_id) AS column_count,
        (SELECT COUNT(*) FROM sys.foreign_keys f WHERE f.parent_object_id = t.object_id)     AS fks_out,
        (SELECT COUNT(*) FROM sys.foreign_keys f WHERE f.referenced_object_id = t.object_id) AS fks_in
FROM sys.tables t
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
WHERE SCHEMA_NAME(t.schema_id) = 'dbo'
GROUP BY t.name, t.object_id
ORDER BY row_count DESC;

-- 1.2  Constraint health: FKs that are disabled or not trusted (someone switched them off)
SELECT  fk.name AS fk_name,
        OBJECT_NAME(fk.parent_object_id)     AS child_table,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id)          AS child_column,
        OBJECT_NAME(fk.referenced_object_id) AS parent_table,
        fk.is_disabled, fk.is_not_trusted
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
WHERE fk.is_disabled = 1 OR fk.is_not_trusted = 1
ORDER BY child_table;


/* ─────────────────────────────────────────────────────────────────────────────
   2. COLUMN PROFILE  (completeness, cardinality, lengths, min/max)
   ───────────────────────────────────────────────────────────────────────────── */

-- 2.1  Every column of every table (≈540 rows) — sort/filter the grid in DBeaver
EXEC dq.usp_ColumnProfile;

-- 2.2  One table at a time
EXEC dq.usp_ColumnProfile @Table = N'Person';


/* ─────────────────────────────────────────────────────────────────────────────
   3. REFERENTIAL INTEGRITY — ORPHANS
   ───────────────────────────────────────────────────────────────────────────── */

-- 3.1  Orphan rows per FK (only FKs with problems; pass 0 to see all 156)
EXEC dq.usp_OrphanCheck @OnlyProblems = 1;

-- 3.2  Polymorphic link with no FK: Notes.ObjectId resolved via ObjectType
SELECT n.Note_ID, n.ObjectType, n.ObjectId
FROM dbo.Notes n
WHERE n.ObjectId IS NOT NULL
  AND NOT ( (n.ObjectType = 'Associate' AND EXISTS (SELECT 1 FROM dbo.Associates a WHERE a.AssociateID = n.ObjectId))
         OR (n.ObjectType = 'Req'       AND EXISTS (SELECT 1 FROM dbo.Req r        WHERE r.ReqID       = n.ObjectId))
         OR (n.ObjectType = 'Account'   AND EXISTS (SELECT 1 FROM dbo.Accounts ac  WHERE ac.Account_ID = n.ObjectId))
         OR (n.ObjectType IN ('Person', 'Candidate', 'Contact')
                                        AND EXISTS (SELECT 1 FROM dbo.Person p     WHERE p.Person_ID   = n.ObjectId)) );

-- 3.3  Value distribution of Notes.ObjectType (what does the polymorphic link point at?)
SELECT ObjectType, COUNT(*) AS n, SUM(CASE WHEN ObjectId IS NULL THEN 1 ELSE 0 END) AS no_object_id
FROM dbo.Notes GROUP BY ObjectType ORDER BY n DESC;


/* ─────────────────────────────────────────────────────────────────────────────
   4. MISSING BUSINESS-MANDATORY VALUES
   ───────────────────────────────────────────────────────────────────────────── */

-- 4.1  NULL / empty / whitespace-only in fields the target will require
SELECT 'Person' AS table_name, 'First_Name' AS column_name, CAST(Person_ID AS varchar(20)) AS pk_value FROM dbo.Person    WHERE NULLIF(LTRIM(RTRIM(First_Name)), '')   IS NULL
UNION ALL SELECT 'Person',    'Last_Name',     CAST(Person_ID  AS varchar(20)) FROM dbo.Person    WHERE NULLIF(LTRIM(RTRIM(Last_Name)), '')     IS NULL
UNION ALL SELECT 'Accounts',  'Account_name',  CAST(Account_ID AS varchar(20)) FROM dbo.Accounts  WHERE NULLIF(LTRIM(RTRIM(Account_name)), '')  IS NULL
UNION ALL SELECT 'Req',       'Req_Title',     CAST(ReqID      AS varchar(20)) FROM dbo.Req       WHERE NULLIF(LTRIM(RTRIM(Req_Title)), '')     IS NULL
UNION ALL SELECT 'Addresses', 'Address_line1', CAST(AddressID  AS varchar(20)) FROM dbo.Addresses WHERE NULLIF(LTRIM(RTRIM(Address_line1)), '') IS NULL
UNION ALL SELECT 'Addresses', 'City',          CAST(AddressID  AS varchar(20)) FROM dbo.Addresses WHERE NULLIF(LTRIM(RTRIM(City)), '')          IS NULL
UNION ALL SELECT 'Person',    'DOB',           CAST(Person_ID  AS varchar(20)) FROM dbo.Person    WHERE DOB IS NULL
ORDER BY table_name, column_name;


/* ─────────────────────────────────────────────────────────────────────────────
   5. FORMAT VALIDITY
   ───────────────────────────────────────────────────────────────────────────── */

-- 5.1  Email addresses (all tables that hold one)
SELECT src.table_name, src.pk_value, src.email,
       CASE WHEN src.email LIKE '% %'                              THEN 'contains space'
            WHEN src.email LIKE '%,%' OR src.email LIKE '%;%'      THEN 'multiple addresses'
            WHEN src.email NOT LIKE '%@%'                          THEN 'no @'
            WHEN src.email LIKE '%@%@%'                            THEN 'more than one @'
            WHEN src.email LIKE '%.'                               THEN 'trailing dot'
            WHEN SUBSTRING(src.email, CHARINDEX('@', src.email) + 1, 255) NOT LIKE '_%._%' THEN 'domain has no TLD'
            ELSE 'other' END AS problem
FROM (SELECT 'Addresses' AS table_name, CAST(AddressID AS varchar(20)) AS pk_value, Email AS email FROM dbo.Addresses
      UNION ALL SELECT 'Recruiter', CAST(RecruiterID AS varchar(20)), email FROM dbo.Recruiter
      UNION ALL SELECT 'Referees',  CAST(Referee_ID  AS varchar(20)), email FROM dbo.Referees
      UNION ALL SELECT 'Leads',     CAST(Lead_ID     AS varchar(20)), Email FROM dbo.Leads) src
WHERE src.email IS NOT NULL
  AND (   src.email LIKE '% %' OR src.email LIKE '%,%' OR src.email LIKE '%;%'
       OR src.email NOT LIKE '_%@_%._%' OR src.email LIKE '%@%@%' OR src.email LIKE '%.'
       OR SUBSTRING(src.email, CHARINDEX('@', src.email) + 1, 255) NOT LIKE '_%._%')
ORDER BY src.table_name, src.pk_value;

-- 5.2  UK postcodes (A9 9AA, A99 9AA, AA9 9AA, AA99 9AA, A9A 9AA, AA9A 9AA — upper case, one space)
SELECT AddressID, City, '[' + ZipCode + ']' AS zipcode_bracketed
FROM dbo.Addresses
WHERE ZipCode IS NOT NULL
  AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][0-9] [0-9][A-Z][A-Z]'
  AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][0-9][0-9] [0-9][A-Z][A-Z]'
  AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][A-Z][0-9] [0-9][A-Z][A-Z]'
  AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][A-Z][0-9][0-9] [0-9][A-Z][A-Z]'
  AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][0-9][A-Z] [0-9][A-Z][A-Z]'
  AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][A-Z][0-9][A-Z] [0-9][A-Z][A-Z]'
ORDER BY AddressID;

-- 5.3  Phone numbers: after removing + ( ) - and spaces, must be 10-13 digits, not all zeros,
--      and no "+44 (0)" (the trunk 0 must be dropped in international format)
SELECT src.table_name, src.pk_value, src.phone, LEN(d.digits) AS digit_count,
       CASE WHEN d.digits LIKE '%[^0-9]%'         THEN 'contains text'
            WHEN d.digits NOT LIKE '%[1-9]%'      THEN 'dummy (all zeros)'
            WHEN src.phone LIKE '%(0)%'           THEN '+44 (0) mixed format'
            WHEN LEN(d.digits) < 10               THEN 'too short'
            ELSE 'too long' END AS problem
FROM (SELECT 'Addresses' AS table_name, CAST(AddressID AS varchar(20)) AS pk_value, Phone AS phone FROM dbo.Addresses
      UNION ALL SELECT 'Addresses.OtherPhone', CAST(AddressID AS varchar(20)), OtherPhone FROM dbo.Addresses
      UNION ALL SELECT 'Addresses.WorkPhone',  CAST(AddressID AS varchar(20)), WorkPhone  FROM dbo.Addresses
      UNION ALL SELECT 'Referees', CAST(Referee_ID AS varchar(20)), Telephone FROM dbo.Referees
      UNION ALL SELECT 'Leads',    CAST(Lead_ID    AS varchar(20)), Phone     FROM dbo.Leads) src
CROSS APPLY (SELECT REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(src.phone, ' ', ''), '+', ''), '(', ''), ')', ''), '-', '') AS digits) d
WHERE src.phone IS NOT NULL AND src.phone <> ''
  AND (d.digits LIKE '%[^0-9]%' OR LEN(d.digits) NOT BETWEEN 10 AND 13 OR d.digits NOT LIKE '%[1-9]%'
       OR src.phone LIKE '%(0)%')
ORDER BY src.table_name, src.pk_value;

-- 5.4  National Insurance numbers: AA999999A, no spaces, valid prefix letters, suffix A-D
SELECT Emp_ProfileID, Person_ID, '[' + NI_number + ']' AS ni_bracketed
FROM dbo.Emp_Profile
WHERE NI_number IS NOT NULL
  AND (   NI_number COLLATE Latin1_General_BIN NOT LIKE '[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z][0-9][0-9][0-9][0-9][0-9][0-9][A-D]'
       OR LEFT(NI_number, 2) IN ('BG', 'GB', 'NK', 'KN', 'TN', 'NT', 'ZZ'))
ORDER BY Emp_ProfileID;

-- 5.5  Bank sort codes: NN-NN-NN
SELECT Emp_ProfileID, Person_ID, '[' + SortCode + ']' AS sortcode_bracketed
FROM dbo.Emp_Profile
WHERE SortCode IS NOT NULL AND SortCode NOT LIKE '[0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
ORDER BY Emp_ProfileID;


/* ─────────────────────────────────────────────────────────────────────────────
   6. CODED VALUES / DOMAINS  (case-sensitive so 'Placed' and 'placed ' show separately)
   ───────────────────────────────────────────────────────────────────────────── */

-- 6.1  Every distinct value of the free-text "code" columns, with counts
SELECT column_name, '[' + value + ']' AS value_bracketed, COUNT(*) AS n
FROM (SELECT 'Req_Hired.Pipeline_Stage' AS column_name, Pipeline_Stage COLLATE Latin1_General_BIN AS value FROM dbo.Req_Hired
      UNION ALL SELECT 'Req_Hired.Worktype',  Worktype     COLLATE Latin1_General_BIN FROM dbo.Req_Hired
      UNION ALL SELECT 'Req_Hired.CurrencyCode', CurrencyCode COLLATE Latin1_General_BIN FROM dbo.Req_Hired
      UNION ALL SELECT 'Req.Worktype',        Worktype     COLLATE Latin1_General_BIN FROM dbo.Req
      UNION ALL SELECT 'Req.CurrencyCode',    CurrencyCode COLLATE Latin1_General_BIN FROM dbo.Req
      UNION ALL SELECT 'Req.StatusText',      StatusText   COLLATE Latin1_General_BIN FROM dbo.Req
      UNION ALL SELECT 'Req.ReqStat',         ReqStat      COLLATE Latin1_General_BIN FROM dbo.Req
      UNION ALL SELECT 'Invoice.Currency',    Currency     COLLATE Latin1_General_BIN FROM dbo.Invoice
      UNION ALL SELECT 'Invoice.VAT',         VAT          COLLATE Latin1_General_BIN FROM dbo.Invoice
      UNION ALL SELECT 'Invoice.Status',      Status       COLLATE Latin1_General_BIN FROM dbo.Invoice
      UNION ALL SELECT 'Leads.Lead_Source',   Lead_Source  COLLATE Latin1_General_BIN FROM dbo.Leads
      UNION ALL SELECT 'Leads.Lead_Status',   Lead_Status  COLLATE Latin1_General_BIN FROM dbo.Leads
      UNION ALL SELECT 'Associates.AssociateTitle', AssociateTitle COLLATE Latin1_General_BIN FROM dbo.Associates
      UNION ALL SELECT 'Addresses.Country',   Country      COLLATE Latin1_General_BIN FROM dbo.Addresses
      UNION ALL SELECT 'Addresses.City',      City         COLLATE Latin1_General_BIN FROM dbo.Addresses) v
GROUP BY column_name, value
ORDER BY column_name, n DESC;

-- 6.2  Worktype consistency between a placement and its job
SELECT h.Req_HiredID, h.Req_ID, h.Worktype AS placement_worktype, r.Worktype AS job_worktype
FROM dbo.Req_Hired h
JOIN dbo.Req r ON r.ReqID = h.Req_ID
WHERE h.Worktype COLLATE Latin1_General_BIN <> r.Worktype COLLATE Latin1_General_BIN;


/* ─────────────────────────────────────────────────────────────────────────────
   7. WHITESPACE & CASING
   ───────────────────────────────────────────────────────────────────────────── */

-- 7.1  Leading/trailing/double spaces, tabs, ALL CAPS or all lower case in names
SELECT src.table_name, src.column_name, src.pk_value, '[' + src.value + ']' AS value_bracketed,
       CASE WHEN src.value LIKE '%' + CHAR(9) + '%'                     THEN 'tab character'
            WHEN DATALENGTH(src.value) <> DATALENGTH(LTRIM(RTRIM(src.value))) THEN 'leading/trailing space'
            WHEN src.value LIKE '%  %'                                  THEN 'double space'
            WHEN src.value COLLATE Latin1_General_BIN = UPPER(src.value) THEN 'ALL CAPS'
            ELSE 'all lower case' END AS problem
FROM (SELECT 'Accounts' AS table_name, 'Account_name' AS column_name, CAST(Account_ID AS varchar(20)) AS pk_value, Account_name AS value FROM dbo.Accounts
      UNION ALL SELECT 'Person', 'First_Name', CAST(Person_ID AS varchar(20)), First_Name FROM dbo.Person
      UNION ALL SELECT 'Person', 'Last_Name',  CAST(Person_ID AS varchar(20)), Last_Name  FROM dbo.Person
      UNION ALL SELECT 'Addresses', 'City',    CAST(AddressID AS varchar(20)), City       FROM dbo.Addresses
      UNION ALL SELECT 'Addresses', 'ZipCode', CAST(AddressID AS varchar(20)), ZipCode    FROM dbo.Addresses) src
WHERE src.value IS NOT NULL AND LTRIM(RTRIM(src.value)) <> ''
  AND (   src.value LIKE '%' + CHAR(9) + '%'
       OR DATALENGTH(src.value) <> DATALENGTH(LTRIM(RTRIM(src.value)))
       OR src.value LIKE '%  %'
       OR (src.column_name <> 'ZipCode' AND LEN(src.value) > 3 AND src.value COLLATE Latin1_General_BIN = UPPER(src.value) AND src.value LIKE '%[A-Za-z]%[a-zA-Z]%' )
       OR (src.column_name <> 'ZipCode' AND src.value COLLATE Latin1_General_BIN = LOWER(src.value)))
ORDER BY src.table_name, src.column_name;


/* ─────────────────────────────────────────────────────────────────────────────
   8. DATES
   ───────────────────────────────────────────────────────────────────────────── */

-- 8.1  Placeholder / impossible dates
SELECT 'Person.DOB' AS check_name, CAST(Person_ID AS varchar(20)) AS pk_value, CAST(DOB AS varchar(30)) AS value,
       CASE WHEN DOB < '1920-01-01' THEN 'placeholder / too old'
            WHEN DOB > GETDATE()    THEN 'in the future'
            ELSE 'under 16' END AS problem
FROM dbo.Person
WHERE DOB < '1920-01-01' OR DOB > DATEADD(YEAR, -16, GETDATE())
UNION ALL
SELECT 'Req.StartDate', CAST(ReqID AS varchar(20)), CONVERT(varchar(30), StartDate, 120), 'placeholder date'
FROM dbo.Req WHERE StartDate < '1990-01-01'
UNION ALL
SELECT src.check_name, src.pk_value, CONVERT(varchar(30), src.dt, 120), 'audit date in the future'
FROM (SELECT 'Req.CreatedAt' AS check_name, CAST(ReqID AS varchar(20)) AS pk_value, CreatedAt AS dt FROM dbo.Req
      UNION ALL SELECT 'Accounts.CreatedAt', CAST(Account_ID AS varchar(20)), CreatedAt FROM dbo.Accounts
      UNION ALL SELECT 'Person.CreatedAt',   CAST(Person_ID  AS varchar(20)), CreatedAt FROM dbo.Person
      UNION ALL SELECT 'Req_Hired.CreatedAt', CAST(Req_HiredID AS varchar(20)), CreatedAt FROM dbo.Req_Hired) src
WHERE src.dt > GETDATE()
ORDER BY check_name;

-- 8.2  Date logic: end before start, due before issued, updated before created
SELECT 'Req_Hired End < Start' AS check_name, CAST(Req_HiredID AS varchar(20)) AS pk_value,
       CONVERT(varchar(10), StartDate, 120) AS first_date, CONVERT(varchar(10), EndDate, 120) AS second_date
FROM dbo.Req_Hired WHERE EndDate < StartDate
UNION ALL SELECT 'Req End < Start', CAST(ReqID AS varchar(20)), CONVERT(varchar(10), StartDate, 120), CONVERT(varchar(10), EndDate, 120)
FROM dbo.Req WHERE EndDate < StartDate
UNION ALL SELECT 'Invoice Due < InvoiceDate', CAST(InvoiceID AS varchar(20)), CONVERT(varchar(10), InvoiceDate, 120), CONVERT(varchar(10), DateDue, 120)
FROM dbo.Invoice WHERE DateDue < InvoiceDate
UNION ALL SELECT 'Req UpdatedAt < CreatedAt', CAST(ReqID AS varchar(20)), CONVERT(varchar(10), CreatedAt, 120), CONVERT(varchar(10), UpdatedAt, 120)
FROM dbo.Req WHERE UpdatedAt < CreatedAt
UNION ALL SELECT 'Accounts UpdatedAt < CreatedAt', CAST(Account_ID AS varchar(20)), CONVERT(varchar(10), CreatedAt, 120), CONVERT(varchar(10), UpdatedAt, 120)
FROM dbo.Accounts WHERE UpdatedAt < CreatedAt
ORDER BY check_name;


/* ─────────────────────────────────────────────────────────────────────────────
   9. NUMERIC RANGES & FINANCIAL CONSISTENCY
   ───────────────────────────────────────────────────────────────────────────── */

-- 9.1  Out-of-range values
SELECT 'Req_Rates.Payrate <= 0' AS check_name, CAST(Req_RateID AS varchar(20)) AS pk_value, CAST(Payrate AS varchar(30)) AS value
FROM dbo.Req_Rates WHERE Payrate <= 0
UNION ALL SELECT 'Req_Rates.BillRate < Payrate (negative margin)', CAST(Req_RateID AS varchar(20)), CONCAT(BillRate, ' < ', Payrate)
FROM dbo.Req_Rates WHERE BillRate < Payrate
UNION ALL SELECT 'Leads.Lead_Score not 1-5', CAST(Lead_ID AS varchar(20)), CAST(Lead_Score AS varchar(30))
FROM dbo.Leads WHERE Lead_Score NOT BETWEEN 1 AND 5
UNION ALL SELECT 'TimesheetItems.TotalHours not (0,24]', CAST(ItemID AS varchar(20)), CAST(TotalHours AS varchar(30))
FROM dbo.TimesheetItems WHERE TotalHours <= 0 OR TotalHours > 24
UNION ALL SELECT 'Addresses lat/long outside UK', CAST(AddressID AS varchar(20)), CONCAT(Latitude, ', ', Longitude)
FROM dbo.Addresses WHERE Latitude NOT BETWEEN 49.8 AND 60.9 OR Longitude NOT BETWEEN -8.7 AND 1.8
ORDER BY check_name;

-- 9.2  Invoice arithmetic (pre-existing issue in the generated data — expect many)
SELECT InvoiceID, Invoice_No, Status, Amount, NETAmount, Amount_Paid, Balance_Due,
       CASE WHEN Amount_Paid > Amount THEN 'paid more than invoiced'
            WHEN ABS(Amount - Amount_Paid - Balance_Due) > 0.01 THEN 'Amount - Paid <> Balance'
            ELSE 'NET > gross' END AS problem
FROM dbo.Invoice
WHERE Amount_Paid > Amount OR ABS(Amount - Amount_Paid - Balance_Due) > 0.01 OR NETAmount > Amount
ORDER BY InvoiceID;


/* ─────────────────────────────────────────────────────────────────────────────
   10. ENCODING
   ───────────────────────────────────────────────────────────────────────────── */

-- 10.1  Mojibake in any text column
EXEC dq.usp_EncodingCheck;


/* ─────────────────────────────────────────────────────────────────────────────
   11. DUPLICATES  (input for entity resolution — no shared keys between copies)
   ───────────────────────────────────────────────────────────────────────────── */

-- 11.1  Accounts: same normalised name (case, punctuation, Ltd/Limited/PLC/LLP/Group/The, & vs and)
WITH n AS (
    SELECT Account_ID, Account_name, Website, CreatedAt,
           REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
               ' ' + LOWER(LTRIM(RTRIM(Account_name))) + ' ',
               '.', ''), ',', ''), '&', ' and '), ' the ', ' '), ' limited ', ' '), ' ltd ', ' '), ' plc ', ' '),
               ' llp ', ' '), ' group ', ' '), ' (uk) ', ' '), ' ', '') AS name_key
    FROM dbo.Accounts
    WHERE NULLIF(LTRIM(RTRIM(Account_name)), '') IS NOT NULL)
SELECT a.Account_ID AS id_1, a.Account_name AS name_1, b.Account_ID AS id_2, b.Account_name AS name_2,
       CASE WHEN a.name_key = b.name_key THEN 'same normalised name' ELSE 'same website' END AS matched_on
FROM n a
JOIN n b ON a.Account_ID < b.Account_ID
        AND (a.name_key = b.name_key OR (a.Website = b.Website AND a.Website IS NOT NULL))
ORDER BY a.Account_ID;

-- 11.2  Accounts: fuzzy — same office address, or same first word of the name (ignoring "The",
--       case and spacing) in the same industry, or a one-typo first word (e.g. "tLd" / "Hawrorth")
WITH w AS (
    SELECT Account_ID, Account_name, Industry, AddressID,
           LOWER(LEFT(nm, CHARINDEX(' ', nm + ' ') - 1)) AS first_word
    FROM dbo.Accounts
    CROSS APPLY (SELECT LTRIM(RTRIM(CASE WHEN LTRIM(Account_name) LIKE 'The %'
                                         THEN SUBSTRING(LTRIM(Account_name), 5, 255)
                                         ELSE Account_name END)) AS nm) x
    WHERE NULLIF(LTRIM(RTRIM(Account_name)), '') IS NOT NULL)
SELECT a.Account_ID AS id_1, a.Account_name AS name_1, b.Account_ID AS id_2, b.Account_name AS name_2,
       CASE WHEN a.AddressID = b.AddressID THEN 'same office address'
            WHEN a.first_word = b.first_word THEN 'same first word + industry'
            ELSE 'first word sounds alike + industry' END AS matched_on
FROM w a
JOIN w b ON a.Account_ID < b.Account_ID
WHERE a.AddressID = b.AddressID
   OR (a.Industry = b.Industry
       AND (a.first_word = b.first_word
            OR (DIFFERENCE(a.first_word, b.first_word) = 4 AND LEN(a.first_word) = LEN(b.first_word)
                AND LEFT(a.first_word, 2) = LEFT(b.first_word, 2))))
ORDER BY a.Account_ID;

-- 11.3  People: candidate duplicate pairs (nickname, typo, swapped DOB, missing DOB)
SELECT p1.Person_ID AS id_1, p1.First_Name AS first_1, p1.Last_Name AS last_1, p1.DOB AS dob_1,
       p2.Person_ID AS id_2, p2.First_Name AS first_2, p2.Last_Name AS last_2, p2.DOB AS dob_2,
       CASE WHEN p1.First_Name = p2.First_Name AND p1.Last_Name = p2.Last_Name AND p1.DOB = p2.DOB THEN 'exact name + DOB'
            WHEN p1.Last_Name = p2.Last_Name AND p1.DOB = p2.DOB                                  THEN 'same surname + DOB, first name sounds alike'
            WHEN p1.First_Name = p2.First_Name AND p1.DOB = p2.DOB                                THEN 'same first name + DOB, surname sounds alike'
            WHEN p1.First_Name = p2.First_Name AND p1.Last_Name = p2.Last_Name
                 AND DAY(p1.DOB) = MONTH(p2.DOB) AND MONTH(p1.DOB) = DAY(p2.DOB)                 THEN 'same name, day/month swapped'
            ELSE 'same name, one DOB missing' END AS match_rule
FROM dbo.Person p1
JOIN dbo.Person p2 ON p1.Person_ID < p2.Person_ID
WHERE (p1.Last_Name = p2.Last_Name AND p1.DOB = p2.DOB AND DIFFERENCE(p1.First_Name, p2.First_Name) >= 3)
   OR (p1.First_Name = p2.First_Name AND p1.DOB = p2.DOB AND DIFFERENCE(p1.Last_Name, p2.Last_Name) >= 3)
   OR (p1.First_Name = p2.First_Name AND p1.Last_Name = p2.Last_Name
       AND (p1.DOB IS NULL OR p2.DOB IS NULL
            OR (DAY(p1.DOB) = MONTH(p2.DOB) AND MONTH(p1.DOB) = DAY(p2.DOB))))
ORDER BY p1.Person_ID;

-- 11.4  Contacts (Associates) whose people are candidate duplicates
SELECT a1.AssociateID AS associate_1, a2.AssociateID AS associate_2,
       p1.First_Name + ' ' + ISNULL(p1.Last_Name, '') AS person_1,
       p2.First_Name + ' ' + ISNULL(p2.Last_Name, '') AS person_2
FROM dbo.Associates a1
JOIN dbo.Person p1 ON p1.Person_ID = a1.Person_ID
JOIN dbo.Person p2 ON p2.Person_ID <> p1.Person_ID
                  AND p2.Last_Name = p1.Last_Name
                  AND (p2.DOB = p1.DOB OR p2.DOB IS NULL OR p1.DOB IS NULL)
                  AND DIFFERENCE(p1.First_Name, p2.First_Name) >= 3
JOIN dbo.Associates a2 ON a2.Person_ID = p2.Person_ID AND a2.AssociateID > a1.AssociateID;

-- 11.5  Transactions entered twice (identical except the ID)
SELECT Timesheet_ID, Person_ID, Req_ID, StartTime, EndTime, TotalHours, CreatedAt,
       COUNT(*) AS copies, STRING_AGG(CAST(ItemID AS varchar(20)), ', ') AS item_ids
FROM dbo.TimesheetItems
GROUP BY Timesheet_ID, Timesheet_TypeID, Person_ID, Req_ID, StartTime, EndTime, TotalHours, CreatedAt
HAVING COUNT(*) > 1
ORDER BY copies DESC;

-- 11.6  Jobs split across duplicate accounts: same title raised by two accounts with the same normalised name
SELECT r.ReqID, r.Req_Title, r.AccountID, a.Account_name
FROM dbo.Req r
JOIN dbo.Accounts a ON a.Account_ID = r.AccountID
WHERE EXISTS (SELECT 1 FROM dbo.Accounts b
              WHERE b.Account_ID <> a.Account_ID
                AND (b.Website = a.Website OR b.AddressID = a.AddressID))
ORDER BY a.Website, r.AccountID;


/* ─────────────────────────────────────────────────────────────────────────────
   12. SOFT-DELETE CONSISTENCY
   ───────────────────────────────────────────────────────────────────────────── */

-- 12.1  Deleted parents that still have live children
SELECT 'Account deleted, has open jobs' AS problem, a.Account_ID AS pk_value, a.Account_name AS label,
       COUNT(r.ReqID) AS live_children
FROM dbo.Accounts a
JOIN dbo.Req r ON r.AccountID = a.Account_ID AND r.Deleted = 0 AND r.StatusText IN ('Open', 'Interviewing', 'Offer Made')
WHERE a.Deleted = 1
GROUP BY a.Account_ID, a.Account_name
UNION ALL
SELECT 'Job deleted, has placements', r.ReqID, r.Req_Title, COUNT(h.Req_HiredID)
FROM dbo.Req r
JOIN dbo.Req_Hired h ON h.Req_ID = r.ReqID AND h.Deleted = 0
WHERE r.Deleted = 1
GROUP BY r.ReqID, r.Req_Title
UNION ALL
SELECT 'Person deleted, is an active contact', p.Person_ID, p.First_Name + ' ' + ISNULL(p.Last_Name, ''), COUNT(s.AssociateID)
FROM dbo.Person p
JOIN dbo.Associates s ON s.Person_ID = p.Person_ID AND s.Active = 1
WHERE p.Deleted = 1
GROUP BY p.Person_ID, p.First_Name, p.Last_Name
ORDER BY problem;


/* ─────────────────────────────────────────────────────────────────────────────
   13. SCORECARD — one row per check, for the data quality report
   ───────────────────────────────────────────────────────────────────────────── */
SELECT check_name, failing_rows FROM (
    SELECT 'Disabled / untrusted FKs' AS check_name, (SELECT COUNT(*) FROM sys.foreign_keys WHERE is_disabled = 1 OR is_not_trusted = 1) AS failing_rows, 1 AS ord
    UNION ALL SELECT 'Mandatory field missing (Person last name)', (SELECT COUNT(*) FROM dbo.Person WHERE NULLIF(LTRIM(RTRIM(Last_Name)), '') IS NULL), 2
    UNION ALL SELECT 'Mandatory field missing (Account name)', (SELECT COUNT(*) FROM dbo.Accounts WHERE NULLIF(LTRIM(RTRIM(Account_name)), '') IS NULL), 3
    UNION ALL SELECT 'Person without DOB', (SELECT COUNT(*) FROM dbo.Person WHERE DOB IS NULL), 4
    UNION ALL SELECT 'Invalid postcode', (SELECT COUNT(*) FROM dbo.Addresses WHERE ZipCode IS NOT NULL
        AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][0-9] [0-9][A-Z][A-Z]'
        AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][0-9][0-9] [0-9][A-Z][A-Z]'
        AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][A-Z][0-9] [0-9][A-Z][A-Z]'
        AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][A-Z][0-9][0-9] [0-9][A-Z][A-Z]'
        AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][0-9][A-Z] [0-9][A-Z][A-Z]'
        AND ZipCode COLLATE Latin1_General_BIN NOT LIKE '[A-Z][A-Z][0-9][A-Z] [0-9][A-Z][A-Z]'), 5
    UNION ALL SELECT 'Invalid sort code', (SELECT COUNT(*) FROM dbo.Emp_Profile WHERE SortCode NOT LIKE '[0-9][0-9]-[0-9][0-9]-[0-9][0-9]'), 6
    UNION ALL SELECT 'Placement End < Start', (SELECT COUNT(*) FROM dbo.Req_Hired WHERE EndDate < StartDate), 7
    UNION ALL SELECT 'Negative margin rates', (SELECT COUNT(*) FROM dbo.Req_Rates WHERE BillRate < Payrate OR Payrate <= 0), 8
    UNION ALL SELECT 'Impossible timesheet hours', (SELECT COUNT(*) FROM dbo.TimesheetItems WHERE TotalHours <= 0 OR TotalHours > 24), 9
    UNION ALL SELECT 'Duplicate timesheet lines', (SELECT ISNULL(SUM(c - 1), 0) FROM (SELECT COUNT(*) c FROM dbo.TimesheetItems GROUP BY Timesheet_ID, Timesheet_TypeID, Person_ID, Req_ID, StartTime, EndTime, TotalHours, CreatedAt HAVING COUNT(*) > 1) d), 10
    UNION ALL SELECT 'Placeholder DOB (< 1920)', (SELECT COUNT(*) FROM dbo.Person WHERE DOB < '1920-01-01'), 11
) s ORDER BY ord;
