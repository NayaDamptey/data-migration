USE Migration_Staging;

TRUNCATE TABLE mid.Contacts;

INSERT INTO mid.Contacts (
    contact_id,
    client_id,
    first_name,
    last_name,
    job_title,
    email,
    phone,
    mobile,
    status,
    owner_user_id,
    created_at
)
SELECT
    s.AssociateID                                             AS contact_id,
    co.AccountID                                              AS client_id,
    p.First_Name                                              AS first_name,
    p.Last_Name                                               AS last_name,
    s.Associate_Tag                                           AS job_title,
    ad.Email                                                  AS email,
    ad.WorkPhone                                              AS phone,
    ad.Phone                                                  AS mobile,
    CASE WHEN s.Active = 1 THEN 'active' ELSE 'inactive' END  AS status,
    s.CreatedBy                                               AS owner_user_id,
    s.CreatedAt                                               AS created_at
FROM Cobaltdesk_Legacy.dbo.Associates s
LEFT JOIN Cobaltdesk_Legacy.dbo.Person p ON p.Person_ID = s.Person_ID
LEFT JOIN Cobaltdesk_Legacy.dbo.Addresses ad ON ad.AddressID = s.Associate_AddressID
OUTER APPLY (SELECT MIN(aa.AccountID) AS AccountID FROM Cobaltdesk_Legacy.dbo.AccountAssociates aa WHERE aa.AssociateID = s.AssociateID) co;
