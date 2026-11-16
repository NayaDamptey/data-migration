{{ config(alias='Users') }}
SELECT
    s.user_id,
    s.first_name,
    s.last_name,
    s.email,
    s.role,
    s.office,
    s.is_active
FROM {{ ref('stg_users') }} s
