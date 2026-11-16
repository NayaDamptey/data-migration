SELECT
    TRY_CAST(h.Req_HiredID AS VARCHAR) AS placement_id,
    TRY_CAST(h.Invoiced_PersonID AS VARCHAR) AS candidate_id,
    TRY_CAST(h.Req_ID AS VARCHAR) AS job_id,
    TRY_CAST(CAST(h.StartDate AS DATE) AS DATE) AS start_date,
    TRY_CAST(CAST(h.EndDate AS DATE) AS DATE) AS end_date,
    TRY_CAST(NULL AS DECIMAL(12,2)) AS salary,
    TRY_CAST(h.FeeValue AS DECIMAL(12,2)) AS fee,
    TRY_CAST(LOWER(h.Worktype) AS VARCHAR) AS placement_type,
    TRY_CAST(h.Owner_ID AS VARCHAR) AS owner_user_id
FROM {{ source('legacy', 'Req_Hired') }} AS h
WHERE (h.Pipeline_Stage = 'Placed')
