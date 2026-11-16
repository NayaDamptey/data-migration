{{ config(alias='Departments') }}
SELECT
    s.department_id,
    s.name,
    s.deleted,
    s.created_at,
    s.updated_at
FROM {{ ref('stg_departments') }} s
