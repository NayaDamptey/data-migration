-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(s.AssociateID AS VARCHAR) AS contact_id,
    TRY_CAST(co.AccountID AS VARCHAR) AS client_id,
    TRY_CAST(p.First_Name AS VARCHAR) AS first_name,
    TRY_CAST(p.Last_Name AS VARCHAR) AS last_name,
    TRY_CAST(s.Associate_Tag AS VARCHAR) AS job_title,
    TRY_CAST(ad.Email AS VARCHAR) AS email,
    TRY_CAST(ad.WorkPhone AS VARCHAR) AS phone,
    TRY_CAST(ad.Phone AS VARCHAR) AS mobile,
    TRY_CAST(CASE WHEN s.Active = 1 THEN 'active' ELSE 'inactive' END AS VARCHAR) AS status,
    TRY_CAST(s.CreatedBy AS VARCHAR) AS owner_user_id,
    TRY_CAST(s.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'Associates') }} AS s
LEFT JOIN {{ source('legacy', 'Person') }} AS p ON p.Person_ID = s.Person_ID
LEFT JOIN {{ source('legacy', 'Addresses') }} AS ad ON ad.AddressID = s.Associate_AddressID
LEFT JOIN LATERAL (SELECT MIN(aa.AccountID) AS AccountID FROM {{ source('legacy', 'AccountAssociates') }} AS aa WHERE aa.AssociateID = s.AssociateID) AS co ON TRUE
