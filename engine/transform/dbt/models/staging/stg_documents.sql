-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST('D' || CAST(d.Doc_ID AS VARCHAR) AS VARCHAR) AS document_id,
    TRY_CAST(CASE d.ObjectType WHEN 'Person' THEN CASE WHEN NOT pc.AssociateID IS NULL THEN 'contact' ELSE 'candidate' END WHEN 'Associate' THEN 'contact' WHEN 'Req' THEN 'job' WHEN 'Account' THEN 'client' END AS VARCHAR) AS entity_type,
    TRY_CAST(CASE WHEN d.ObjectType = 'Person' AND NOT pc.AssociateID IS NULL THEN CAST(pc.AssociateID AS VARCHAR) ELSE CAST(d.Doc_AssocID AS VARCHAR) END AS VARCHAR) AS entity_id,
    TRY_CAST(RIGHT(CAST(d.Path AS TEXT), STRPOS(REVERSE(d.Path), '/') - 1) AS VARCHAR) AS file_name,
    TRY_CAST(LOWER(RIGHT(CAST(d.Path AS TEXT), STRPOS(REVERSE(d.Path), '.') - 1)) AS VARCHAR) AS file_type,
    TRY_CAST(d.Path AS VARCHAR) AS storage_path,
    TRY_CAST(d.CreatedAt AS TIMESTAMP) AS uploaded_at
FROM {{ source('legacy', 'Documents') }} AS d
LEFT JOIN LATERAL (SELECT MIN(s.AssociateID) AS AssociateID FROM {{ source('legacy', 'Associates') }} AS s WHERE d.ObjectType = 'Person' AND s.Person_ID = d.Doc_AssocID) AS pc ON TRUE
UNION ALL
SELECT
    TRY_CAST('CV' || CAST(c.Doc_ID AS VARCHAR) AS VARCHAR) AS document_id,
    TRY_CAST('candidate' AS VARCHAR) AS entity_type,
    TRY_CAST(c.CV_AssocID AS VARCHAR) AS entity_id,
    TRY_CAST(RIGHT(CAST(c.Path AS TEXT), STRPOS(REVERSE(c.Path), '/') - 1) AS VARCHAR) AS file_name,
    TRY_CAST(LOWER(RIGHT(CAST(c.Path AS TEXT), STRPOS(REVERSE(c.Path), '.') - 1)) AS VARCHAR) AS file_type,
    TRY_CAST(c.Path AS VARCHAR) AS storage_path,
    TRY_CAST(c.CreatedAt AS TIMESTAMP) AS uploaded_at
FROM {{ source('legacy', 'CV_Docs') }} AS c
