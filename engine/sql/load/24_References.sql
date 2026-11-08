USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.[References];

DELETE FROM dbo.MigrationRejects WHERE target_table = N'References';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'References', CAST(r.reference_id AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.[References] r
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = r.candidate_id));

INSERT INTO dbo.[References] (
    ID,
    ApplicantID,
    Fullname,
    PositionTitle,
    CompanyName,
    Relationship,
    Email,
    PhoneContact,
    ReferenceType,
    Notes,
    VerifiedAt,
    AddedAt,
    UpdatedAt
)
SELECT
    r.reference_id                                         AS ID,
    r.candidate_id                                         AS ApplicantID,
    r.full_name                                            AS Fullname,
    LEFT(r.job_title, 50)                                  AS PositionTitle,
    LEFT(r.company, 50)                                    AS CompanyName,
    r.relationship                                         AS Relationship,
    LEFT(r.email, 50)                                      AS Email,
    r.phone                                                AS PhoneContact,
    'Employment'                                           AS ReferenceType,
    LEFT(r.status, 50)                                     AS Notes,
    CASE WHEN r.status = 'Received' THEN r.updated_at END  AS VerifiedAt,
    r.created_at                                           AS AddedAt,
    r.updated_at                                           AS UpdatedAt
FROM Migration_Staging.mid.[References] r
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = r.candidate_id));
