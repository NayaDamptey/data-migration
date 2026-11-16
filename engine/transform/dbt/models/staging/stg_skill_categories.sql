SELECT
    TRY_CAST(sc.CategoryID AS VARCHAR) AS category_id,
    TRY_CAST(sc.Name AS VARCHAR) AS name,
    TRY_CAST(sc.Deleted AS BOOLEAN) AS deleted
FROM {{ source('legacy', 'SkillCategory') }} AS sc
