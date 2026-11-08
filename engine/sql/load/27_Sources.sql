USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Sources;

INSERT INTO dbo.Sources (
    ID,
    Name
)
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY s.source) AS NVARCHAR(50))  AS ID,
    UPPER(LEFT(s.source, 1)) + SUBSTRING(s.source, 2, 50)        AS Name
FROM (SELECT DISTINCT source FROM Migration_Staging.mid.Candidates WHERE source IS NOT NULL) s;
