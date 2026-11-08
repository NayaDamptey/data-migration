USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Skills;

INSERT INTO dbo.Skills (
    ID,
    SkillName,
    SkillCategoryID,
    Status
)
SELECT
    sk.skill_id                                                 AS ID,
    sk.name                                                     AS SkillName,
    sk.category_id                                              AS SkillCategoryID,
    CASE WHEN sk.deleted = 1 THEN 'Inactive' ELSE 'Active' END  AS Status
FROM Migration_Staging.mid.Skills sk;
