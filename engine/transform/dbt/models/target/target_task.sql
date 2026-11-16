{{ config(alias='Task') }}
SELECT
    TRY_CAST(TRY_CAST(a.activity_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(a.activity_type AS VARCHAR) AS TaskType,
    TRY_CAST(a.user_id AS VARCHAR) AS OwnerUserID,
    TRY_CAST(LEFT(CAST(a.subject AS TEXT), 50) AS VARCHAR) AS Subject,
    TRY_CAST(a.subject AS VARCHAR) AS Note,
    TRY_CAST('Completed' AS VARCHAR) AS Status,
    TRY_CAST(CAST(a.occurred_at AS DATE) AS DATE) AS StartDate,
    TRY_CAST(1 AS BOOLEAN) AS Completed,
    TRY_CAST(a.occurred_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_activities') }} AS a
UNION ALL
SELECT
    TRY_CAST(100000 + TRY_CAST(iv.interview_id AS INT) AS INTEGER) AS ID,
    TRY_CAST('Interview' AS VARCHAR) AS TaskType,
    TRY_CAST(NULL AS VARCHAR) AS OwnerUserID,
    TRY_CAST('Interview feedback' AS VARCHAR) AS Subject,
    TRY_CAST(iv.feedback AS VARCHAR) AS Note,
    TRY_CAST('Completed' AS VARCHAR) AS Status,
    TRY_CAST(CAST(iv.interview_date AS DATE) AS DATE) AS StartDate,
    TRY_CAST(1 AS BOOLEAN) AS Completed,
    TRY_CAST(iv.created_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_interviews') }} AS iv
