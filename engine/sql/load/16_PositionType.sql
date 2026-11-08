USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.PositionType;

INSERT INTO dbo.PositionType (
    ID,
    Type
)
SELECT
    ROW_NUMBER() OVER (ORDER BY j.employment_type)                           AS ID,
    UPPER(LEFT(j.employment_type, 1)) + SUBSTRING(j.employment_type, 2, 50)  AS Type
FROM (SELECT DISTINCT employment_type FROM Migration_Staging.mid.Jobs WHERE employment_type IS NOT NULL) j;
