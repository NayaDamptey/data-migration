USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Attachments;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Attachments';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Attachments', CAST(CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END AS NVARCHAR(200)), N'rejected', N'linked to no migrated record (orphan)'
FROM Migration_Staging.mid.Documents d
WHERE NOT ((d.entity_type = 'candidate' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = d.entity_id)) OR (d.entity_type = 'contact' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Contacts x WHERE x.contact_id = d.entity_id AND x.client_id IS NOT NULL)) OR (d.entity_type = 'job' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Jobs x WHERE x.job_id = d.entity_id)) OR (d.entity_type = 'client' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = d.entity_id)));

INSERT INTO dbo.Attachments (
    AttachmentID,
    AttachmentType,
    AttachmentName,
    FilePath,
    FileType,
    UploadedAt,
    IsPrimary,
    IsArchived,
    IsDeleted
)
SELECT
    CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END  AS AttachmentID,
    d.entity_type                                                                                                                                                AS AttachmentType,
    LEFT(d.file_name, 50)                                                                                                                                        AS AttachmentName,
    LEFT(d.storage_path, 50)                                                                                                                                     AS FilePath,
    d.file_type                                                                                                                                                  AS FileType,
    d.uploaded_at                                                                                                                                                AS UploadedAt,
    0                                                                                                                                                            AS IsPrimary,
    0                                                                                                                                                            AS IsArchived,
    0                                                                                                                                                            AS IsDeleted
FROM Migration_Staging.mid.Documents d
WHERE ((d.entity_type = 'candidate' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = d.entity_id)) OR (d.entity_type = 'contact' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Contacts x WHERE x.contact_id = d.entity_id AND x.client_id IS NOT NULL)) OR (d.entity_type = 'job' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Jobs x WHERE x.job_id = d.entity_id)) OR (d.entity_type = 'client' AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = d.entity_id)));
