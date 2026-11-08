USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Applicant;

INSERT INTO dbo.Applicant (
    ApplicantID,
    FirstName,
    LastName,
    ApplicantCommsID,
    Status,
    JobTitle,
    Source,
    Active,
    ApplicantOwner,
    AddedBy,
    AddedAt,
    Deleted
)
SELECT
    ca.candidate_id                                                                    AS ApplicantID,
    ca.first_name                                                                      AS FirstName,
    ca.last_name                                                                       AS LastName,
    CASE WHEN ca.email IS NOT NULL THEN TRY_CAST(ca.candidate_id AS INT) * 10 + 1 END  AS ApplicantCommsID,
    ca.status                                                                          AS Status,
    LEFT(ca.current_job_title, 50)                                                     AS JobTitle,
    ca.source                                                                          AS Source,
    1                                                                                  AS Active,
    ca.owner_user_id                                                                   AS ApplicantOwner,
    ca.owner_user_id                                                                   AS AddedBy,
    ca.created_at                                                                      AS AddedAt,
    0                                                                                  AS Deleted
FROM Migration_Staging.mid.Candidates ca;
