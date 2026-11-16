{{ config(alias='Department') }}
SELECT
    TRY_CAST(TRY_CAST(d.department_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(d.name AS VARCHAR) AS Name,
    TRY_CAST(d.created_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(d.updated_at AS TIMESTAMP) AS UpdatedAt
FROM {{ ref('mid_departments') }} AS d
