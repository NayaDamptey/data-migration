-- generated from spec/target.yml: middle tier -> Placements
{{ config(alias='Placements') }}
SELECT
    TRY_CAST(TRY_CAST(pl.placement_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(pl.candidate_id AS VARCHAR) AS ApplicantID,
    TRY_CAST(TRY_CAST(pl.job_id AS INT) AS INTEGER) AS PositionID,
    TRY_CAST(j.client_id AS VARCHAR) AS CompanyID,
    TRY_CAST(pl.placement_type AS VARCHAR) AS EmploymentType,
    TRY_CAST(pl.start_date AS DATE) AS StartDate,
    TRY_CAST(pl.end_date AS DATE) AS EndDate,
    TRY_CAST(pl.fee AS DOUBLE) AS Fee,
    TRY_CAST('Placed' AS VARCHAR) AS Status,
    TRY_CAST(pl.owner_user_id AS VARCHAR) AS OwnerID
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
