-- generated from spec/target.yml: middle tier -> TaskItem
{{ config(alias='TaskItem') }}
SELECT
    TRY_CAST(TRY_CAST(a.activity_id AS INT) * 10 + 1 AS INTEGER) AS ID,
    TRY_CAST(TRY_CAST(a.activity_id AS INT) AS INTEGER) AS TaskID,
    TRY_CAST(a.candidate_id AS VARCHAR) AS ObjectID,
    TRY_CAST('Applicant' AS VARCHAR) AS ObjectType,
    TRY_CAST(a.occurred_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_activities') }} AS a
WHERE (NOT a.candidate_id IS NULL)
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = a.candidate_id))
UNION ALL
SELECT
    TRY_CAST(TRY_CAST(a.activity_id AS INT) * 10 + 2 AS INTEGER) AS ID,
    TRY_CAST(TRY_CAST(a.activity_id AS INT) AS INTEGER) AS TaskID,
    TRY_CAST(a.contact_id AS VARCHAR) AS ObjectID,
    TRY_CAST('Contact' AS VARCHAR) AS ObjectType,
    TRY_CAST(a.occurred_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_activities') }} AS a
WHERE (NOT a.contact_id IS NULL)
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = a.contact_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT
    TRY_CAST(TRY_CAST(a.activity_id AS INT) * 10 + 3 AS INTEGER) AS ID,
    TRY_CAST(TRY_CAST(a.activity_id AS INT) AS INTEGER) AS TaskID,
    TRY_CAST(a.job_id AS VARCHAR) AS ObjectID,
    TRY_CAST('Position' AS VARCHAR) AS ObjectType,
    TRY_CAST(a.occurred_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_activities') }} AS a
WHERE (NOT a.job_id IS NULL)
UNION ALL
SELECT
    TRY_CAST(1000000 + TRY_CAST(iv.interview_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(100000 + TRY_CAST(iv.interview_id AS INT) AS INTEGER) AS TaskID,
    TRY_CAST(iv.candidate_id AS VARCHAR) AS ObjectID,
    TRY_CAST('Applicant' AS VARCHAR) AS ObjectType,
    TRY_CAST(iv.created_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_interviews') }} AS iv
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = iv.candidate_id))
