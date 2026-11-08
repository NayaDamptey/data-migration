USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.SkillCategory;

INSERT INTO dbo.SkillCategory (
    ID,
    CategoryName,
    Deleted
)
SELECT
    sc.category_id  AS ID,
    sc.name         AS CategoryName,
    sc.deleted      AS Deleted
FROM Migration_Staging.mid.SkillCategories sc;
