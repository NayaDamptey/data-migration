USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Company;

INSERT INTO dbo.Company (
    ID,
    CompanyName,
    Industry,
    Website,
    Telephone,
    LocationID,
    Type,
    Company_OwnerID,
    AddedBy,
    AddedDate,
    Isdeleted,
    IsArchive
)
SELECT
    c.client_id                                                  AS ID,
    LEFT(c.company_name, 50)                                     AS CompanyName,
    c.industry                                                   AS Industry,
    LEFT(c.website, 50)                                          AS Website,
    c.phone                                                      AS Telephone,
    CASE WHEN c.address_line_1 IS NOT NULL THEN c.client_id END  AS LocationID,
    'Client'                                                     AS Type,
    c.owner_user_id                                              AS Company_OwnerID,
    c.owner_user_id                                              AS AddedBy,
    c.created_at                                                 AS AddedDate,
    CASE WHEN c.status = 'deleted' THEN 1 ELSE 0 END             AS Isdeleted,
    0                                                            AS IsArchive
FROM Migration_Staging.mid.Clients c;
