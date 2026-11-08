USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Notes;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Notes';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Notes', CAST(TRY_CAST(n.note_id AS INT) AS NVARCHAR(200)), N'rejected', N'linked to no migrated record (orphan)'
FROM Migration_Staging.mid.Notes n
WHERE NOT ((n.entity_type = 'candidate' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = n.entity_id)) OR (n.entity_type = 'contact' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Contacts x WHERE x.contact_id = n.entity_id AND x.client_id IS NOT NULL)) OR (n.entity_type = 'job' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Jobs x WHERE x.job_id = n.entity_id)) OR (n.entity_type = 'client' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = n.entity_id)));

INSERT INTO dbo.Notes (
    ID,
    Text,
    ApplicantID,
    CompanyID,
    PositionID,
    ContactID,
    Deleted,
    AddedAt,
    UserID
)
SELECT
    TRY_CAST(n.note_id AS INT)                                             AS ID,
    n.body                                                                 AS Text,
    CASE WHEN n.entity_type = 'candidate' THEN n.entity_id END             AS ApplicantID,
    CASE WHEN n.entity_type = 'client' THEN n.entity_id END                AS CompanyID,
    CASE WHEN n.entity_type = 'job' THEN TRY_CAST(n.entity_id AS INT) END  AS PositionID,
    CASE WHEN n.entity_type = 'contact' THEN n.entity_id END               AS ContactID,
    0                                                                      AS Deleted,
    n.created_at                                                           AS AddedAt,
    n.author_user_id                                                       AS UserID
FROM Migration_Staging.mid.Notes n
WHERE ((n.entity_type = 'candidate' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = n.entity_id)) OR (n.entity_type = 'contact' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Contacts x WHERE x.contact_id = n.entity_id AND x.client_id IS NOT NULL)) OR (n.entity_type = 'job' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Jobs x WHERE x.job_id = n.entity_id)) OR (n.entity_type = 'client' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = n.entity_id)));
