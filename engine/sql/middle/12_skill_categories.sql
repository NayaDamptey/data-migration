USE Migration_Staging;

TRUNCATE TABLE mid.SkillCategories;

INSERT INTO mid.SkillCategories (
    category_id,
    name,
    deleted
)
SELECT
    sc.CategoryID  AS category_id,
    sc.Name        AS name,
    sc.Deleted     AS deleted
FROM Cobaltdesk_Legacy.dbo.SkillCategory sc;
