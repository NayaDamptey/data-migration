USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Shortlist;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Shortlist';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Shortlist', CAST(TRY_CAST(a.application_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Applications a
WHERE (a.stage IN ('screening', 'interview', 'offer'))
  AND NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));

INSERT INTO dbo.Shortlist (
    ID,
    PositionID,
    ApplicantID,
    ShortlistedDate,
    Status,
    AddedBy,
    AddedAt
)
SELECT
    TRY_CAST(a.application_id AS INT)                    AS ID,
    TRY_CAST(a.job_id AS INT)                            AS PositionID,
    a.candidate_id                                       AS ApplicantID,
    CAST(a.applied_at AS DATE)                           AS ShortlistedDate,
    UPPER(LEFT(a.stage, 1)) + SUBSTRING(a.stage, 2, 50)  AS Status,
    a.owner_user_id                                      AS AddedBy,
    a.applied_at                                         AS AddedAt
FROM Migration_Staging.mid.Applications a
WHERE (a.stage IN ('screening', 'interview', 'offer'))
  AND (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));
