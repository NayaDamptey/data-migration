USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Position_Applicant;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Position_Applicant';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Position_Applicant', CAST(TRY_CAST(a.application_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Applications a
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));

INSERT INTO dbo.Position_Applicant (
    ID,
    PositionID,
    ApplicantID,
    CompanyID,
    ApplicationDate,
    StatusTxt,
    AddedBy,
    AddedAt,
    Active
)
SELECT
    TRY_CAST(a.application_id AS INT)                                               AS ID,
    TRY_CAST(a.job_id AS INT)                                                       AS PositionID,
    a.candidate_id                                                                  AS ApplicantID,
    a.client_id                                                                     AS CompanyID,
    CAST(a.applied_at AS DATE)                                                      AS ApplicationDate,
    UPPER(LEFT(a.stage, 1)) + SUBSTRING(a.stage, 2, 50)                             AS StatusTxt,
    a.owner_user_id                                                                 AS AddedBy,
    a.applied_at                                                                    AS AddedAt,
    CASE WHEN a.stage IN ('placed', 'rejected') OR a.deleted = 1 THEN 0 ELSE 1 END  AS Active
FROM Migration_Staging.mid.Applications a
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));
