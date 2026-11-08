USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.CompanyLocation;

INSERT INTO dbo.CompanyLocation (
    ID,
    CompanyID,
    AddressLine1,
    AddressLine2,
    City,
    PostCode,
    Country,
    AddedAt
)
SELECT
    c.client_id       AS ID,
    c.client_id       AS CompanyID,
    c.address_line_1  AS AddressLine1,
    c.address_line_2  AS AddressLine2,
    c.city            AS City,
    c.postcode        AS PostCode,
    c.country         AS Country,
    c.created_at      AS AddedAt
FROM Migration_Staging.mid.Clients c
WHERE (c.address_line_1 IS NOT NULL);
