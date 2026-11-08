USE master;
GO
IF DB_ID(N'Migration_Staging') IS NULL CREATE DATABASE Migration_Staging;
GO
ALTER DATABASE Migration_Staging SET AUTO_CLOSE OFF;
GO
USE Migration_Staging;
GO
IF SCHEMA_ID(N'mid') IS NULL EXEC (N'CREATE SCHEMA mid');
GO
IF OBJECT_ID(N'mid.Users') IS NOT NULL DROP TABLE mid.Users;
CREATE TABLE mid.Users (
    user_id NVARCHAR(50),
    first_name NVARCHAR(200),
    last_name NVARCHAR(200),
    email NVARCHAR(200),
    role NVARCHAR(200),
    office NVARCHAR(200),
    is_active BIT
);
GO
IF OBJECT_ID(N'mid.Clients') IS NOT NULL DROP TABLE mid.Clients;
CREATE TABLE mid.Clients (
    client_id NVARCHAR(50),
    company_name NVARCHAR(200),
    industry NVARCHAR(200),
    website NVARCHAR(200),
    phone NVARCHAR(200),
    address_line_1 NVARCHAR(200),
    address_line_2 NVARCHAR(200),
    city NVARCHAR(200),
    postcode NVARCHAR(200),
    country NVARCHAR(200),
    status NVARCHAR(200),
    owner_user_id NVARCHAR(50),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Contacts') IS NOT NULL DROP TABLE mid.Contacts;
CREATE TABLE mid.Contacts (
    contact_id NVARCHAR(50),
    client_id NVARCHAR(50),
    first_name NVARCHAR(200),
    last_name NVARCHAR(200),
    job_title NVARCHAR(200),
    email NVARCHAR(200),
    phone NVARCHAR(200),
    mobile NVARCHAR(200),
    status NVARCHAR(200),
    owner_user_id NVARCHAR(50),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Candidates') IS NOT NULL DROP TABLE mid.Candidates;
CREATE TABLE mid.Candidates (
    candidate_id NVARCHAR(50),
    first_name NVARCHAR(200),
    last_name NVARCHAR(200),
    email NVARCHAR(200),
    mobile NVARCHAR(200),
    phone NVARCHAR(200),
    current_job_title NVARCHAR(200),
    current_employer NVARCHAR(200),
    address_line_1 NVARCHAR(200),
    address_line_2 NVARCHAR(200),
    city NVARCHAR(200),
    postcode NVARCHAR(200),
    country NVARCHAR(200),
    source NVARCHAR(200),
    status NVARCHAR(200),
    linkedin_url NVARCHAR(200),
    owner_user_id NVARCHAR(50),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Jobs') IS NOT NULL DROP TABLE mid.Jobs;
CREATE TABLE mid.Jobs (
    job_id NVARCHAR(50),
    client_id NVARCHAR(50),
    contact_id NVARCHAR(50),
    title NVARCHAR(200),
    employment_type NVARCHAR(200),
    salary_min DECIMAL(12,2),
    salary_max DECIMAL(12,2),
    rate DECIMAL(12,2),
    rate_unit NVARCHAR(200),
    location NVARCHAR(200),
    status NVARCHAR(200),
    owner_user_id NVARCHAR(50),
    opened_at DATE,
    closed_at DATE,
    description NVARCHAR(MAX)
);
GO
IF OBJECT_ID(N'mid.Placements') IS NOT NULL DROP TABLE mid.Placements;
CREATE TABLE mid.Placements (
    placement_id NVARCHAR(50),
    candidate_id NVARCHAR(50),
    job_id NVARCHAR(50),
    start_date DATE,
    end_date DATE,
    salary DECIMAL(12,2),
    fee DECIMAL(12,2),
    placement_type NVARCHAR(200),
    owner_user_id NVARCHAR(50)
);
GO
IF OBJECT_ID(N'mid.Notes') IS NOT NULL DROP TABLE mid.Notes;
CREATE TABLE mid.Notes (
    note_id NVARCHAR(50),
    entity_type NVARCHAR(200),
    entity_id NVARCHAR(50),
    author_user_id NVARCHAR(50),
    note_type NVARCHAR(200),
    body NVARCHAR(MAX),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Histories') IS NOT NULL DROP TABLE mid.Histories;
CREATE TABLE mid.Histories (
    history_id NVARCHAR(50),
    entity_type NVARCHAR(200),
    entity_id NVARCHAR(50),
    field_changed NVARCHAR(200),
    old_value NVARCHAR(MAX),
    new_value NVARCHAR(MAX),
    changed_by NVARCHAR(50),
    changed_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Activities') IS NOT NULL DROP TABLE mid.Activities;
CREATE TABLE mid.Activities (
    activity_id NVARCHAR(50),
    activity_type NVARCHAR(200),
    candidate_id NVARCHAR(50),
    contact_id NVARCHAR(50),
    job_id NVARCHAR(50),
    user_id NVARCHAR(50),
    occurred_at DATETIME2(0),
    outcome NVARCHAR(200),
    subject NVARCHAR(MAX)
);
GO
IF OBJECT_ID(N'mid.Documents') IS NOT NULL DROP TABLE mid.Documents;
CREATE TABLE mid.Documents (
    document_id NVARCHAR(50),
    entity_type NVARCHAR(200),
    entity_id NVARCHAR(50),
    file_name NVARCHAR(200),
    file_type NVARCHAR(200),
    storage_path NVARCHAR(200),
    uploaded_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Departments') IS NOT NULL DROP TABLE mid.Departments;
CREATE TABLE mid.Departments (
    department_id NVARCHAR(50),
    name NVARCHAR(200),
    deleted BIT,
    created_at DATETIME2(0),
    updated_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.SkillCategories') IS NOT NULL DROP TABLE mid.SkillCategories;
CREATE TABLE mid.SkillCategories (
    category_id NVARCHAR(50),
    name NVARCHAR(200),
    deleted BIT
);
GO
IF OBJECT_ID(N'mid.Skills') IS NOT NULL DROP TABLE mid.Skills;
CREATE TABLE mid.Skills (
    skill_id NVARCHAR(50),
    name NVARCHAR(200),
    category_id NVARCHAR(50),
    deleted BIT
);
GO
IF OBJECT_ID(N'mid.Applications') IS NOT NULL DROP TABLE mid.Applications;
CREATE TABLE mid.Applications (
    application_id NVARCHAR(50),
    candidate_id NVARCHAR(50),
    job_id NVARCHAR(50),
    client_id NVARCHAR(50),
    contact_id NVARCHAR(50),
    stage NVARCHAR(200),
    employment_type NVARCHAR(200),
    start_date DATE,
    end_date DATE,
    fee DECIMAL(12,2),
    source NVARCHAR(200),
    owner_user_id NVARCHAR(50),
    deleted BIT,
    applied_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Interviews') IS NOT NULL DROP TABLE mid.Interviews;
CREATE TABLE mid.Interviews (
    interview_id NVARCHAR(50),
    candidate_id NVARCHAR(50),
    interviewer_person_id NVARCHAR(50),
    interview_date DATETIME2(0),
    feedback NVARCHAR(MAX),
    callback NVARCHAR(200),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.WorkHistory') IS NOT NULL DROP TABLE mid.WorkHistory;
CREATE TABLE mid.WorkHistory (
    history_id NVARCHAR(50),
    candidate_id NVARCHAR(50),
    employer NVARCHAR(200),
    job_title NVARCHAR(200),
    start_date DATE,
    end_date DATE,
    deleted BIT
);
GO
IF OBJECT_ID(N'mid.References') IS NOT NULL DROP TABLE mid.[References];
CREATE TABLE mid.[References] (
    reference_id NVARCHAR(50),
    candidate_id NVARCHAR(50),
    full_name NVARCHAR(200),
    job_title NVARCHAR(200),
    company NVARCHAR(200),
    relationship NVARCHAR(200),
    email NVARCHAR(200),
    phone NVARCHAR(200),
    status NVARCHAR(200),
    reference_text NVARCHAR(MAX),
    created_at DATETIME2(0),
    updated_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.CandidateProfiles') IS NOT NULL DROP TABLE mid.CandidateProfiles;
CREATE TABLE mid.CandidateProfiles (
    profile_id NVARCHAR(50),
    candidate_id NVARCHAR(50),
    employment_type NVARCHAR(200),
    notes NVARCHAR(MAX),
    bank NVARCHAR(200),
    sort_code NVARCHAR(200),
    added_by NVARCHAR(50),
    created_at DATETIME2(0),
    updated_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Consents') IS NOT NULL DROP TABLE mid.Consents;
CREATE TABLE mid.Consents (
    consent_id NVARCHAR(50),
    person_id NVARCHAR(50),
    email_ok BIT,
    phone_ok BIT,
    text_ok BIT,
    added_by NVARCHAR(50),
    created_at DATETIME2(0),
    updated_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Timesheets') IS NOT NULL DROP TABLE mid.Timesheets;
CREATE TABLE mid.Timesheets (
    timesheet_id NVARCHAR(50),
    po_no NVARCHAR(50),
    timesheet_type NVARCHAR(200),
    pay_rate DECIMAL(12,2),
    charge_rate DECIMAL(12,2),
    start_date DATE,
    end_date DATE,
    status NVARCHAR(200),
    approved_by NVARCHAR(50),
    approved_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.TimesheetLines') IS NOT NULL DROP TABLE mid.TimesheetLines;
CREATE TABLE mid.TimesheetLines (
    line_id NVARCHAR(50),
    timesheet_id NVARCHAR(50),
    candidate_id NVARCHAR(50),
    job_id NVARCHAR(50),
    line_type NVARCHAR(200),
    start_time NVARCHAR(200),
    end_time NVARCHAR(200),
    hours DECIMAL(12,2),
    added_by NVARCHAR(50),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.PurchaseOrders') IS NOT NULL DROP TABLE mid.PurchaseOrders;
CREATE TABLE mid.PurchaseOrders (
    po_no NVARCHAR(50),
    client_id NVARCHAR(50),
    job_id NVARCHAR(50),
    department_id NVARCHAR(50),
    status NVARCHAR(200),
    issue_date DATE,
    due_date DATE,
    currency NVARCHAR(200),
    amount DECIMAL(12,2),
    tax_amount DECIMAL(12,2),
    description NVARCHAR(200),
    added_by NVARCHAR(50),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Invoices') IS NOT NULL DROP TABLE mid.Invoices;
CREATE TABLE mid.Invoices (
    invoice_id NVARCHAR(50),
    invoice_no NVARCHAR(200),
    po_no NVARCHAR(50),
    client_id NVARCHAR(50),
    invoice_type NVARCHAR(200),
    status NVARCHAR(200),
    currency NVARCHAR(200),
    net_amount DECIMAL(12,2),
    vat_amount DECIMAL(12,2),
    gross_amount DECIMAL(12,2),
    invoice_date DATE,
    due_date DATE,
    description NVARCHAR(200),
    added_by NVARCHAR(50)
);
GO
IF OBJECT_ID(N'mid.InvoiceLines') IS NOT NULL DROP TABLE mid.InvoiceLines;
CREATE TABLE mid.InvoiceLines (
    line_id NVARCHAR(50),
    invoice_id NVARCHAR(50),
    placement_id NVARCHAR(50),
    description NVARCHAR(200),
    quantity DECIMAL(12,2),
    unit_price DECIMAL(12,2),
    amount DECIMAL(12,2),
    created_at DATETIME2(0)
);
GO
IF OBJECT_ID(N'mid.Leads') IS NOT NULL DROP TABLE mid.Leads;
CREATE TABLE mid.Leads (
    lead_id NVARCHAR(50),
    full_name NVARCHAR(200),
    title NVARCHAR(200),
    status NVARCHAR(200),
    source NVARCHAR(200),
    client_id NVARCHAR(50),
    contact_id NVARCHAR(50),
    job_id NVARCHAR(50),
    email NVARCHAR(200),
    phone NVARCHAR(200),
    note NVARCHAR(MAX),
    assigned_to NVARCHAR(50),
    sourced_at DATETIME2(0)
);
GO
