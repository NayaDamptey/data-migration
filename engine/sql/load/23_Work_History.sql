USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Work_History;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Work_History';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Work_History', CAST(TRY_CAST(w.history_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.WorkHistory w
WHERE (w.deleted = 0)
  AND NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = w.candidate_id));

INSERT INTO dbo.Work_History (
    ID,
    ApplicationID,
    CompanyName,
    PositionTitle,
    StartDate,
    EndDate
)
SELECT
    TRY_CAST(w.history_id AS INT)  AS ID,
    w.candidate_id                 AS ApplicationID,
    LEFT(w.employer, 50)           AS CompanyName,
    LEFT(w.job_title, 50)          AS PositionTitle,
    w.start_date                   AS StartDate,
    w.end_date                     AS EndDate
FROM Migration_Staging.mid.WorkHistory w
WHERE (w.deleted = 0)
  AND (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = w.candidate_id));
