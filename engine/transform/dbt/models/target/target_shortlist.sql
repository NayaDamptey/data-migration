{{ config(alias='Shortlist') }}
SELECT
    TRY_CAST(TRY_CAST(a.application_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(TRY_CAST(a.job_id AS INT) AS INTEGER) AS PositionID,
    TRY_CAST(a.candidate_id AS VARCHAR) AS ApplicantID,
    TRY_CAST(CAST(a.applied_at AS DATE) AS DATE) AS ShortlistedDate,
    TRY_CAST(UPPER(LEFT(CAST(a.stage AS TEXT), 1)) || SUBSTRING(a.stage, 2, 50) AS VARCHAR) AS Status,
    TRY_CAST(a.owner_user_id AS VARCHAR) AS AddedBy,
    TRY_CAST(a.applied_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_applications') }} AS a
WHERE (a.stage IN ('screening', 'interview', 'offer'))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = a.job_id AND NOT x.client_id IS NULL))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = a.candidate_id))
