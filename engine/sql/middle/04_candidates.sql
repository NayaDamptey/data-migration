USE Migration_Staging;

TRUNCATE TABLE mid.Candidates;

INSERT INTO mid.Candidates (
    candidate_id,
    first_name,
    last_name,
    email,
    mobile,
    phone,
    current_job_title,
    current_employer,
    address_line_1,
    address_line_2,
    city,
    postcode,
    country,
    source,
    status,
    linkedin_url,
    owner_user_id,
    created_at
)
SELECT
    p.Person_ID                   AS candidate_id,
    p.First_Name                  AS first_name,
    p.Last_Name                   AS last_name,
    ad.Email                      AS email,
    ad.Phone                      AS mobile,
    NULLIF(ad.OtherPhone, '')     AS phone,
    cj.Title                      AS current_job_title,
    cj.PlaceofWork                AS current_employer,
    ad.Address_line1              AS address_line_1,
    NULLIF(ad.Address_line2, '')  AS address_line_2,
    ad.City                       AS city,
    ad.ZipCode                    AS postcode,
    ad.Country                    AS country,
    LOWER(lh.Source)              AS source,
    LOWER(lh.Pipeline_Stage)      AS status,
    NULL                          AS linkedin_url,
    p.CreatedBy                   AS owner_user_id,
    p.CreatedAt                   AS created_at
FROM Cobaltdesk_Legacy.dbo.Person p
LEFT JOIN Cobaltdesk_Legacy.dbo.Addresses ad ON ad.AddressID = p.AddressID
OUTER APPLY (SELECT TOP 1 eh.Title, eh.PlaceofWork FROM Cobaltdesk_Legacy.dbo.EmpHist eh
             JOIN Cobaltdesk_Legacy.dbo.Emp_Profile ep ON ep.Emp_ProfileID = eh.Emp_ID
             WHERE ep.Person_ID = p.Person_ID ORDER BY eh.Started_At DESC) cj
OUTER APPLY (SELECT TOP 1 h.Source, h.Pipeline_Stage FROM Cobaltdesk_Legacy.dbo.Req_Hired h
             WHERE h.Invoiced_PersonID = p.Person_ID ORDER BY h.CreatedAt DESC, h.Req_HiredID DESC) lh
WHERE (NOT EXISTS (SELECT 1 FROM Cobaltdesk_Legacy.dbo.Associates s WHERE s.Person_ID = p.Person_ID));
