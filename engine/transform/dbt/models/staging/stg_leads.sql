SELECT
    TRY_CAST(ld.Lead_ID AS VARCHAR) AS lead_id,
    TRY_CAST(ld.Name AS VARCHAR) AS full_name,
    TRY_CAST(ld.Lead_Name AS VARCHAR) AS title,
    TRY_CAST(ld.Lead_Status AS VARCHAR) AS status,
    TRY_CAST(ld.Lead_Source AS VARCHAR) AS source,
    TRY_CAST(ld.Account_ID AS VARCHAR) AS client_id,
    TRY_CAST(ld.Associate_ID AS VARCHAR) AS contact_id,
    TRY_CAST(ld.Req_ID AS VARCHAR) AS job_id,
    TRY_CAST(ld.Email AS VARCHAR) AS email,
    TRY_CAST(ld.Phone AS VARCHAR) AS phone,
    TRY_CAST(ld.Note AS VARCHAR) AS note,
    TRY_CAST(ld.Assigned_To AS VARCHAR) AS assigned_to,
    TRY_CAST(ld.Sourced_Date AS TIMESTAMP) AS sourced_at
FROM {{ source('legacy', 'Leads') }} AS ld
