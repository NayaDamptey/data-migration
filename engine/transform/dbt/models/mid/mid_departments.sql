-- generated: the middle tier for Departments, with the reviewer's duplicate merges applied
{{ config(alias='Departments') }}
SELECT
    s.department_id,
    s.name,
    s.deleted,
    s.created_at,
    s.updated_at
FROM {{ ref('stg_departments') }} s
