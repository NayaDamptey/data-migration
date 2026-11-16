{{ config(alias='Position') }}
SELECT
    TRY_CAST(TRY_CAST(j.job_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(LEFT(CAST(j.title AS TEXT), 50) AS VARCHAR) AS PositionName,
    TRY_CAST(j.client_id AS VARCHAR) AS CompanyID,
    TRY_CAST(j.contact_id AS VARCHAR) AS ContactID,
    TRY_CAST(j.status AS VARCHAR) AS Status,
    TRY_CAST(CASE WHEN j.status = 'filled' THEN 1 ELSE 0 END AS BOOLEAN) AS Filled,
    TRY_CAST(CASE WHEN j.status IN ('filled', 'cancelled') THEN 1 ELSE 0 END AS BOOLEAN) AS Closed,
    TRY_CAST(CASE WHEN j.status = 'deleted' THEN 1 ELSE 0 END AS BOOLEAN) AS Deleted,
    TRY_CAST(j.rate AS DOUBLE) AS PositionChargeRate,
    TRY_CAST(CAST(j.salary_min AS VARCHAR) AS VARCHAR) AS Salary,
    TRY_CAST('GBP' AS VARCHAR) AS Currency,
    TRY_CAST(j.opened_at AS DATE) AS DateBegins,
    TRY_CAST(j.closed_at AS DATE) AS DateEnds,
    TRY_CAST(j.owner_user_id AS VARCHAR) AS Addedby,
    TRY_CAST(j.owner_user_id AS VARCHAR) AS PositionOwnerID
FROM {{ ref('mid_jobs') }} AS j
WHERE (NOT j.client_id IS NULL AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = j.client_id))
