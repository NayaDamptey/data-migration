-- generated: the middle tier for Skill categories, with the reviewer's duplicate merges applied
{{ config(alias='SkillCategories') }}
SELECT
    s.category_id,
    s.name,
    s.deleted
FROM {{ ref('stg_skill_categories') }} s
