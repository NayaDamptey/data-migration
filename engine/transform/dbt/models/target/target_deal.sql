-- generated from spec/target.yml: middle tier -> Deal
{{ config(alias='Deal') }}
SELECT
    TRY_CAST(TRY_CAST(pl.placement_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(TRY_CAST(pl.placement_id AS INT) AS INTEGER) AS PlacementID,
    TRY_CAST(pl.owner_user_id AS VARCHAR) AS RecruiterID,
    TRY_CAST(j.client_id AS VARCHAR) AS CompanyID,
    TRY_CAST(pl.start_date AS DATE) AS DealDate,
    TRY_CAST(pl.placement_type AS VARCHAR) AS DealType,
    TRY_CAST(pl.fee AS DECIMAL(8,2)) AS DealValue
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
