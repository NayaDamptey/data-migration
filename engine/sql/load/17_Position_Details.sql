USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Position_Details;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Position_Details';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Position_Details', CAST(TRY_CAST(j.job_id AS INT) AS NVARCHAR(200)), N'rejected', N'job linked to no company'
FROM Migration_Staging.mid.Jobs j
WHERE NOT (j.client_id IS NOT NULL);

INSERT INTO dbo.Position_Details (
    ID,
    PositionID,
    Requirement,
    Location,
    ClosingDate,
    PayFrequency,
    AddedBy
)
SELECT
    TRY_CAST(j.job_id AS INT)                                                                   AS ID,
    TRY_CAST(j.job_id AS INT)                                                                   AS PositionID,
    j.description                                                                               AS Requirement,
    j.location                                                                                  AS Location,
    j.closed_at                                                                                 AS ClosingDate,
    CASE WHEN j.rate_unit = 'day' THEN 'Daily' WHEN j.salary_min IS NOT NULL THEN 'Annual' END  AS PayFrequency,
    j.owner_user_id                                                                             AS AddedBy
FROM Migration_Staging.mid.Jobs j
WHERE (j.client_id IS NOT NULL);
