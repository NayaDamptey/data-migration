SELECT
    TRY_CAST(h.Req_HiredID AS VARCHAR) AS application_id,
    TRY_CAST(h.Invoiced_PersonID AS VARCHAR) AS candidate_id,
    TRY_CAST(h.Req_ID AS VARCHAR) AS job_id,
    TRY_CAST(h.Account_ID AS VARCHAR) AS client_id,
    TRY_CAST(h.Associate_ID AS VARCHAR) AS contact_id,
    TRY_CAST(LOWER(h.Pipeline_Stage) AS VARCHAR) AS stage,
    TRY_CAST(LOWER(h.Worktype) AS VARCHAR) AS employment_type,
    TRY_CAST(CAST(h.StartDate AS DATE) AS DATE) AS start_date,
    TRY_CAST(CAST(h.EndDate AS DATE) AS DATE) AS end_date,
    TRY_CAST(h.FeeValue AS DECIMAL(12,2)) AS fee,
    TRY_CAST(LOWER(h.Source) AS VARCHAR) AS source,
    TRY_CAST(h.Owner_ID AS VARCHAR) AS owner_user_id,
    TRY_CAST(h.Deleted AS BOOLEAN) AS deleted,
    TRY_CAST(h.CreatedAt AS TIMESTAMP) AS applied_at
FROM {{ source('legacy', 'Req_Hired') }} AS h
