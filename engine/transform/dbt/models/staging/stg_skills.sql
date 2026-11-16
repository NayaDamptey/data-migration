-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(sk.SkillID AS VARCHAR) AS skill_id,
    TRY_CAST(sk.SkillName AS VARCHAR) AS name,
    TRY_CAST(sk.Skill_CategoryID AS VARCHAR) AS category_id,
    TRY_CAST(sk.Deleted AS BOOLEAN) AS deleted
FROM {{ source('legacy', 'Skills') }} AS sk
