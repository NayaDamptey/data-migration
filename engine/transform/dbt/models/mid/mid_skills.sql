-- generated: the middle tier for Skills, with the reviewer's duplicate merges applied
{{ config(alias='Skills') }}
SELECT
    s.skill_id,
    s.name,
    s.category_id,
    s.deleted
FROM {{ ref('stg_skills') }} s
