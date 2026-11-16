{{ config(alias='Skills') }}
SELECT
    TRY_CAST(sk.skill_id AS VARCHAR) AS ID,
    TRY_CAST(sk.name AS VARCHAR) AS SkillName,
    TRY_CAST(sk.category_id AS VARCHAR) AS SkillCategoryID,
    TRY_CAST(CASE WHEN sk.deleted = 1 THEN 'Inactive' ELSE 'Active' END AS VARCHAR) AS Status
FROM {{ ref('mid_skills') }} AS sk
