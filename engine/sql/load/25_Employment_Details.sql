USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Employment_Details;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Employment_Details';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Employment_Details', CAST(TRY_CAST(cp.profile_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.CandidateProfiles cp
LEFT JOIN Migration_Staging.mid.Consents c ON c.person_id = cp.candidate_id
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = cp.candidate_id));

INSERT INTO dbo.Employment_Details (
    ID,
    Employment_Type,
    ApplicantID,
    MarketingEmail,
    MarketingPhone,
    MarketingText,
    Bank,
    SortCode,
    Notes,
    AddedBy,
    AddedAt,
    UpdatedAt
)
SELECT
    TRY_CAST(cp.profile_id AS INT)  AS ID,
    cp.employment_type              AS Employment_Type,
    cp.candidate_id                 AS ApplicantID,
    c.email_ok                      AS MarketingEmail,
    c.phone_ok                      AS MarketingPhone,
    c.text_ok                       AS MarketingText,
    LEFT(cp.bank, 50)               AS Bank,
    cp.sort_code                    AS SortCode,
    cp.notes                        AS Notes,
    cp.added_by                     AS AddedBy,
    cp.created_at                   AS AddedAt,
    cp.updated_at                   AS UpdatedAt
FROM Migration_Staging.mid.CandidateProfiles cp
LEFT JOIN Migration_Staging.mid.Consents c ON c.person_id = cp.candidate_id
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = cp.candidate_id));
