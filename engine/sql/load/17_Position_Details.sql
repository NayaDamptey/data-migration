USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Position_Details;

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
FROM Migration_Staging.mid.Jobs j;
