-- generated from spec/target.yml: middle tier -> SkillCategory
{{ config(alias='SkillCategory') }}
SELECT
    TRY_CAST(sc.category_id AS VARCHAR) AS ID,
    TRY_CAST(sc.name AS VARCHAR) AS CategoryName,
    TRY_CAST(sc.deleted AS BOOLEAN) AS Deleted
FROM {{ ref('mid_skill_categories') }} AS sc
