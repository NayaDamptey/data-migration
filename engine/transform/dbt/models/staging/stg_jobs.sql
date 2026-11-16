SELECT
    TRY_CAST(r.ReqID AS VARCHAR) AS job_id,
    TRY_CAST(r.AccountID AS VARCHAR) AS client_id,
    TRY_CAST(r.AssociateID AS VARCHAR) AS contact_id,
    TRY_CAST(r.Req_Title AS VARCHAR) AS title,
    TRY_CAST(LOWER(r.Worktype) AS VARCHAR) AS employment_type,
    TRY_CAST(rt.Salary AS DECIMAL(12,2)) AS salary_min,
    TRY_CAST(NULL AS DECIMAL(12,2)) AS salary_max,
    TRY_CAST(rt.BillRate AS DECIMAL(12,2)) AS rate,
    TRY_CAST(CASE WHEN NOT rt.BillRate IS NULL THEN 'day' END AS VARCHAR) AS rate_unit,
    TRY_CAST(ad.City AS VARCHAR) AS location,
    TRY_CAST(CASE WHEN r.Deleted = 1 THEN 'deleted' ELSE LOWER(r.StatusText) END AS VARCHAR) AS status,
    TRY_CAST(r.CreatedBy AS VARCHAR) AS owner_user_id,
    TRY_CAST(CAST(r.StartDate AS DATE) AS DATE) AS opened_at,
    TRY_CAST(CAST(r.EndDate AS DATE) AS DATE) AS closed_at,
    TRY_CAST(r.Req_Description AS VARCHAR) AS description
FROM {{ source('legacy', 'Req') }} AS r
LEFT JOIN LATERAL (SELECT rr.BillRate, rr.Salary FROM {{ source('legacy', 'Req_Rates') }} AS rr WHERE rr.Req_ID = r.ReqID ORDER BY rr.Req_RateID NULLS FIRST LIMIT 1) AS rt ON TRUE
LEFT JOIN {{ source('legacy', 'Addresses') }} AS ad ON ad.AddressID = r.Address_ID
