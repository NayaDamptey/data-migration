USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Contact;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Contact';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Contact', CAST(ct.contact_id AS NVARCHAR(200)), N'rejected', N'contact linked to no company (orphan)'
FROM Migration_Staging.mid.Contacts ct
WHERE NOT (ct.client_id IS NOT NULL AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = ct.client_id));

INSERT INTO dbo.Contact (
    ID,
    FirstName,
    LastName,
    CompanyID,
    Email,
    Phone,
    PositionTitle,
    Contacttype,
    ContactOwnerID,
    IsDeleted,
    IsArchived,
    AddedBy,
    AddedAt
)
SELECT
    ct.contact_id                                       AS ID,
    ct.first_name                                       AS FirstName,
    ct.last_name                                        AS LastName,
    ct.client_id                                        AS CompanyID,
    ct.email                                            AS Email,
    COALESCE(ct.phone, ct.mobile)                       AS Phone,
    LEFT(ct.job_title, 50)                              AS PositionTitle,
    'Client contact'                                    AS Contacttype,
    ct.owner_user_id                                    AS ContactOwnerID,
    0                                                   AS IsDeleted,
    CASE WHEN ct.status = 'inactive' THEN 1 ELSE 0 END  AS IsArchived,
    ct.owner_user_id                                    AS AddedBy,
    ct.created_at                                       AS AddedAt
FROM Migration_Staging.mid.Contacts ct
WHERE (ct.client_id IS NOT NULL AND EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = ct.client_id));
