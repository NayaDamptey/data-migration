{{ config(alias='Comms') }}
SELECT
    TRY_CAST(TRY_CAST(ca.candidate_id AS INT) * 10 + 1 AS INTEGER) AS ID,
    TRY_CAST(ca.candidate_id AS VARCHAR) AS ObjectID,
    TRY_CAST('Applicant' AS VARCHAR) AS ObjectType,
    TRY_CAST(ca.email AS VARCHAR) AS Value,
    TRY_CAST('Email' AS VARCHAR) AS Type,
    TRY_CAST(0 AS BOOLEAN) AS Deleted,
    TRY_CAST(ca.owner_user_id AS VARCHAR) AS AddedBy
FROM {{ ref('mid_candidates') }} AS ca
WHERE (NOT ca.email IS NULL)
UNION ALL
SELECT
    TRY_CAST(TRY_CAST(ca.candidate_id AS INT) * 10 + 2 AS INTEGER) AS ID,
    TRY_CAST(ca.candidate_id AS VARCHAR) AS ObjectID,
    TRY_CAST('Applicant' AS VARCHAR) AS ObjectType,
    TRY_CAST(ca.mobile AS VARCHAR) AS Value,
    TRY_CAST('Mobile' AS VARCHAR) AS Type,
    TRY_CAST(0 AS BOOLEAN) AS Deleted,
    TRY_CAST(ca.owner_user_id AS VARCHAR) AS AddedBy
FROM {{ ref('mid_candidates') }} AS ca
WHERE (NOT ca.mobile IS NULL)
