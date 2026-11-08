USE Migration_Staging;

TRUNCATE TABLE mid.Leads;

INSERT INTO mid.Leads (
    lead_id,
    full_name,
    title,
    status,
    source,
    client_id,
    contact_id,
    job_id,
    email,
    phone,
    note,
    assigned_to,
    sourced_at
)
SELECT
    ld.Lead_ID       AS lead_id,
    ld.Name          AS full_name,
    ld.Lead_Name     AS title,
    ld.Lead_Status   AS status,
    ld.Lead_Source   AS source,
    ld.Account_ID    AS client_id,
    ld.Associate_ID  AS contact_id,
    ld.Req_ID        AS job_id,
    ld.Email         AS email,
    ld.Phone         AS phone,
    ld.Note          AS note,
    ld.Assigned_To   AS assigned_to,
    ld.Sourced_Date  AS sourced_at
FROM Cobaltdesk_Legacy.dbo.Leads ld;
