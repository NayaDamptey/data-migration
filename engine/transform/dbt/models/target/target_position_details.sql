-- generated from spec/target.yml: middle tier -> Position_Details
{{ config(alias='Position_Details') }}
SELECT
    TRY_CAST(TRY_CAST(j.job_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(TRY_CAST(j.job_id AS INT) AS INTEGER) AS PositionID,
    TRY_CAST(j.description AS VARCHAR) AS Requirement,
    TRY_CAST(j.location AS VARCHAR) AS Location,
    TRY_CAST(j.closed_at AS DATE) AS ClosingDate,
    TRY_CAST(CASE WHEN j.rate_unit = 'day' THEN 'Daily' WHEN NOT j.salary_min IS NULL THEN 'Annual' END AS VARCHAR) AS PayFrequency,
    TRY_CAST(j.owner_user_id AS VARCHAR) AS AddedBy
FROM {{ ref('mid_jobs') }} AS j
WHERE (NOT j.client_id IS NULL)
