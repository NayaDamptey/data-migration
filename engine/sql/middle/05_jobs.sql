USE Migration_Staging;

TRUNCATE TABLE mid.Jobs;

INSERT INTO mid.Jobs (
    job_id,
    client_id,
    contact_id,
    title,
    employment_type,
    salary_min,
    salary_max,
    rate,
    rate_unit,
    location,
    status,
    owner_user_id,
    opened_at,
    closed_at,
    description
)
SELECT
    r.ReqID                                                              AS job_id,
    r.AccountID                                                          AS client_id,
    r.AssociateID                                                        AS contact_id,
    r.Req_Title                                                          AS title,
    LOWER(r.Worktype)                                                    AS employment_type,
    rt.Salary                                                            AS salary_min,
    NULL                                                                 AS salary_max,
    rt.BillRate                                                          AS rate,
    CASE WHEN rt.BillRate IS NOT NULL THEN 'day' END                     AS rate_unit,
    ad.City                                                              AS location,
    CASE WHEN r.Deleted = 1 THEN 'deleted' ELSE LOWER(r.StatusText) END  AS status,
    r.CreatedBy                                                          AS owner_user_id,
    CAST(r.StartDate AS DATE)                                            AS opened_at,
    CAST(r.EndDate AS DATE)                                              AS closed_at,
    r.Req_Description                                                    AS description
FROM Cobaltdesk_Legacy.dbo.Req r
OUTER APPLY (SELECT TOP 1 rr.BillRate, rr.Salary FROM Cobaltdesk_Legacy.dbo.Req_Rates rr WHERE rr.Req_ID = r.ReqID ORDER BY rr.Req_RateID) rt
LEFT JOIN Cobaltdesk_Legacy.dbo.Addresses ad ON ad.AddressID = r.Address_ID;
