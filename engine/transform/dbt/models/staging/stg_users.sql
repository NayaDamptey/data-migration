-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(r.RecruiterID AS VARCHAR) AS user_id,
    TRY_CAST(LEFT(CAST(r.Fullname AS TEXT), STRPOS(r.Fullname || ' ', ' ') - 1) AS VARCHAR) AS first_name,
    TRY_CAST(NULLIF(LTRIM(SUBSTRING(r.Fullname, STRPOS(r.Fullname || ' ', ' ') + 1, 200)), '') AS VARCHAR) AS last_name,
    TRY_CAST(r.email AS VARCHAR) AS email,
    TRY_CAST(LOWER(ro.Description) AS VARCHAR) AS role,
    TRY_CAST(NULL AS VARCHAR) AS office,
    TRY_CAST(1 AS BOOLEAN) AS is_active
FROM {{ source('legacy', 'Recruiter') }} AS r
LEFT JOIN {{ source('legacy', 'Roles') }} AS ro ON ro.Role_ID = r.Role_ID
