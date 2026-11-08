USE Migration_Staging;

TRUNCATE TABLE mid.Clients;

INSERT INTO mid.Clients (
    client_id,
    company_name,
    industry,
    website,
    phone,
    address_line_1,
    address_line_2,
    city,
    postcode,
    country,
    status,
    owner_user_id,
    created_at
)
SELECT
    a.Account_ID                                                           AS client_id,
    a.Account_name                                                         AS company_name,
    a.Industry                                                             AS industry,
    a.Website                                                              AS website,
    COALESCE(ad.WorkPhone, ad.Phone)                                       AS phone,
    ad.Address_line1                                                       AS address_line_1,
    ad.Address_line2                                                       AS address_line_2,
    ad.City                                                                AS city,
    ad.ZipCode                                                             AS postcode,
    ad.Country                                                             AS country,
    CASE WHEN a.Deleted = 1 THEN 'deleted' ELSE LOWER(st.Description) END  AS status,
    a.CreatedBy                                                            AS owner_user_id,
    a.CreatedAt                                                            AS created_at
FROM Cobaltdesk_Legacy.dbo.Accounts a
LEFT JOIN Cobaltdesk_Legacy.dbo.Addresses ad ON ad.AddressID = a.AddressID
LEFT JOIN Cobaltdesk_Legacy.dbo.AccountStatus st ON st.Account_StatusID = a.AccountStatusTypeID;
