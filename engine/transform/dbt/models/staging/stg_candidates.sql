SELECT
    TRY_CAST(p.Person_ID AS VARCHAR) AS candidate_id,
    TRY_CAST(p.First_Name AS VARCHAR) AS first_name,
    TRY_CAST(p.Last_Name AS VARCHAR) AS last_name,
    TRY_CAST(ad.Email AS VARCHAR) AS email,
    TRY_CAST(ad.Phone AS VARCHAR) AS mobile,
    TRY_CAST(NULLIF(ad.OtherPhone, '') AS VARCHAR) AS phone,
    TRY_CAST(cj.Title AS VARCHAR) AS current_job_title,
    TRY_CAST(cj.PlaceofWork AS VARCHAR) AS current_employer,
    TRY_CAST(ad.Address_line1 AS VARCHAR) AS address_line_1,
    TRY_CAST(NULLIF(ad.Address_line2, '') AS VARCHAR) AS address_line_2,
    TRY_CAST(ad.City AS VARCHAR) AS city,
    TRY_CAST(ad.ZipCode AS VARCHAR) AS postcode,
    TRY_CAST(ad.Country AS VARCHAR) AS country,
    TRY_CAST(LOWER(lh.Source) AS VARCHAR) AS source,
    TRY_CAST(LOWER(lh.Pipeline_Stage) AS VARCHAR) AS status,
    TRY_CAST(NULL AS VARCHAR) AS linkedin_url,
    TRY_CAST(p.CreatedBy AS VARCHAR) AS owner_user_id,
    TRY_CAST(p.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'Person') }} AS p
LEFT JOIN {{ source('legacy', 'Addresses') }} AS ad ON ad.AddressID = p.AddressID
LEFT JOIN LATERAL (SELECT eh.Title, eh.PlaceofWork FROM {{ source('legacy', 'EmpHist') }} AS eh JOIN {{ source('legacy', 'Emp_Profile') }} AS ep ON ep.Emp_ProfileID = eh.Emp_ID WHERE ep.Person_ID = p.Person_ID ORDER BY eh.Started_At DESC LIMIT 1) AS cj ON TRUE
LEFT JOIN LATERAL (SELECT h.Source, h.Pipeline_Stage FROM {{ source('legacy', 'Req_Hired') }} AS h WHERE h.Invoiced_PersonID = p.Person_ID ORDER BY h.CreatedAt DESC, h.Req_HiredID DESC LIMIT 1) AS lh ON TRUE
WHERE (NOT EXISTS(SELECT 1 FROM {{ source('legacy', 'Associates') }} AS s WHERE s.Person_ID = p.Person_ID))
