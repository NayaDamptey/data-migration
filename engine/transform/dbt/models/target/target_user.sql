-- generated from spec/target.yml: middle tier -> User
{{ config(alias='User') }}
SELECT
    TRY_CAST(u.user_id AS VARCHAR) AS UserID,
    TRY_CAST(LEFT(CAST(u.email AS TEXT), STRPOS(u.email || '@', '@') - 1) AS VARCHAR) AS Loginname,
    TRY_CAST(CONCAT_WS(' ', u.first_name, u.last_name) AS VARCHAR) AS FullName,
    TRY_CAST(u.email AS VARCHAR) AS Email,
    TRY_CAST(u.role AS VARCHAR) AS Role,
    TRY_CAST(CASE WHEN u.is_active = 1 THEN 'Active' ELSE 'Inactive' END AS VARCHAR) AS Status,
    TRY_CAST(0 AS BOOLEAN) AS IsDeleted,
    TRY_CAST(0 AS BOOLEAN) AS IsArchived
FROM {{ ref('mid_users') }} AS u
