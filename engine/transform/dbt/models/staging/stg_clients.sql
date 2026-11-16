-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(a.Account_ID AS VARCHAR) AS client_id,
    TRY_CAST(a.Account_name AS VARCHAR) AS company_name,
    TRY_CAST(a.Industry AS VARCHAR) AS industry,
    TRY_CAST(a.Website AS VARCHAR) AS website,
    TRY_CAST(COALESCE(ad.WorkPhone, ad.Phone) AS VARCHAR) AS phone,
    TRY_CAST(ad.Address_line1 AS VARCHAR) AS address_line_1,
    TRY_CAST(ad.Address_line2 AS VARCHAR) AS address_line_2,
    TRY_CAST(ad.City AS VARCHAR) AS city,
    TRY_CAST(ad.ZipCode AS VARCHAR) AS postcode,
    TRY_CAST(ad.Country AS VARCHAR) AS country,
    TRY_CAST(CASE WHEN a.Deleted = 1 THEN 'deleted' ELSE LOWER(st.Description) END AS VARCHAR) AS status,
    TRY_CAST(a.CreatedBy AS VARCHAR) AS owner_user_id,
    TRY_CAST(a.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'Accounts') }} AS a
LEFT JOIN {{ source('legacy', 'Addresses') }} AS ad ON ad.AddressID = a.AddressID
LEFT JOIN {{ source('legacy', 'AccountStatus') }} AS st ON st.Account_StatusID = a.AccountStatusTypeID
