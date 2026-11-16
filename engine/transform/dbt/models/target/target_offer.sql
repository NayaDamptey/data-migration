-- generated from spec/target.yml: middle tier -> Offer
{{ config(alias='Offer') }}
SELECT
    TRY_CAST(TRY_CAST(a.application_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(CASE WHEN a.stage = 'placed' THEN TRY_CAST(a.application_id AS INT) END AS INTEGER) AS PlacementID,
    TRY_CAST(CASE WHEN a.stage = 'placed' THEN 1 ELSE 0 END AS BOOLEAN) AS Accepted,
    TRY_CAST(a.employment_type AS VARCHAR) AS Terms,
    TRY_CAST(a.owner_user_id AS VARCHAR) AS RecruiterID
FROM {{ ref('mid_applications') }} AS a
WHERE (a.stage IN ('offer', 'placed'))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = a.job_id AND NOT x.client_id IS NULL))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = a.candidate_id))
