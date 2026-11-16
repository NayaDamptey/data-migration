{{ config(alias='Deal_Stage') }}
SELECT
    TRY_CAST(TRY_CAST(pl.placement_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(TRY_CAST(pl.placement_id AS INT) AS INTEGER) AS DealID,
    TRY_CAST('Won' AS VARCHAR) AS Stage
FROM {{ ref('mid_placements') }} AS pl
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
