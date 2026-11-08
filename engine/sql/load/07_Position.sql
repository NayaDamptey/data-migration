USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Position;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Position';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Position', CAST(TRY_CAST(j.job_id AS INT) AS NVARCHAR(200)), N'flagged', N'open job on a deleted company'
FROM Migration_Staging.mid.Jobs j
WHERE NOT (j.status NOT IN ('open', 'interviewing', 'offer made') OR NOT EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = j.client_id AND x.status = 'deleted'));

INSERT INTO dbo.Position (
    ID,
    PositionName,
    CompanyID,
    ContactID,
    Status,
    Filled,
    Closed,
    Deleted,
    PositionChargeRate,
    Salary,
    Currency,
    DateBegins,
    DateEnds,
    Addedby,
    PositionOwnerID
)
SELECT
    TRY_CAST(j.job_id AS INT)                                        AS ID,
    LEFT(j.title, 50)                                                AS PositionName,
    j.client_id                                                      AS CompanyID,
    j.contact_id                                                     AS ContactID,
    j.status                                                         AS Status,
    CASE WHEN j.status = 'filled' THEN 1 ELSE 0 END                  AS Filled,
    CASE WHEN j.status IN ('filled', 'cancelled') THEN 1 ELSE 0 END  AS Closed,
    CASE WHEN j.status = 'deleted' THEN 1 ELSE 0 END                 AS Deleted,
    j.rate                                                           AS PositionChargeRate,
    CAST(j.salary_min AS NVARCHAR(50))                               AS Salary,
    'GBP'                                                            AS Currency,
    j.opened_at                                                      AS DateBegins,
    j.closed_at                                                      AS DateEnds,
    j.owner_user_id                                                  AS Addedby,
    j.owner_user_id                                                  AS PositionOwnerID
FROM Migration_Staging.mid.Jobs j;
