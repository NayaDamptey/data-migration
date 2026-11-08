USE Migration_Staging;

TRUNCATE TABLE mid.Skills;

INSERT INTO mid.Skills (
    skill_id,
    name,
    category_id,
    deleted
)
SELECT
    sk.SkillID           AS skill_id,
    sk.SkillName         AS name,
    sk.Skill_CategoryID  AS category_id,
    sk.Deleted           AS deleted
FROM Cobaltdesk_Legacy.dbo.Skills sk;
