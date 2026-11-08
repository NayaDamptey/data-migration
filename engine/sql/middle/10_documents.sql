USE Migration_Staging;

TRUNCATE TABLE mid.Documents;

INSERT INTO mid.Documents (
    document_id,
    entity_type,
    entity_id,
    file_name,
    file_type,
    storage_path,
    uploaded_at
)
SELECT
    'D' + CAST(d.Doc_ID AS NVARCHAR(20))                                                                                                                                                                  AS document_id,
    CASE d.ObjectType WHEN 'Person' THEN CASE WHEN pc.AssociateID IS NOT NULL THEN 'contact' ELSE 'candidate' END WHEN 'Associate' THEN 'contact' WHEN 'Req' THEN 'job' WHEN 'Account' THEN 'client' END  AS entity_type,
    CASE WHEN d.ObjectType = 'Person' AND pc.AssociateID IS NOT NULL THEN CAST(pc.AssociateID AS NVARCHAR(50)) ELSE CAST(d.Doc_AssocID AS NVARCHAR(50)) END                                               AS entity_id,
    RIGHT(d.Path, CHARINDEX('/', REVERSE(d.Path)) - 1)                                                                                                                                                    AS file_name,
    LOWER(RIGHT(d.Path, CHARINDEX('.', REVERSE(d.Path)) - 1))                                                                                                                                             AS file_type,
    d.Path                                                                                                                                                                                                AS storage_path,
    d.CreatedAt                                                                                                                                                                                           AS uploaded_at
FROM Cobaltdesk_Legacy.dbo.Documents d
OUTER APPLY (SELECT MIN(s.AssociateID) AS AssociateID FROM Cobaltdesk_Legacy.dbo.Associates s WHERE d.ObjectType = 'Person' AND s.Person_ID = d.Doc_AssocID) pc;

INSERT INTO mid.Documents (
    document_id,
    entity_type,
    entity_id,
    file_name,
    file_type,
    storage_path,
    uploaded_at
)
SELECT
    'CV' + CAST(c.Doc_ID AS NVARCHAR(20))                      AS document_id,
    'candidate'                                                AS entity_type,
    c.CV_AssocID                                               AS entity_id,
    RIGHT(c.Path, CHARINDEX('/', REVERSE(c.Path)) - 1)         AS file_name,
    LOWER(RIGHT(c.Path, CHARINDEX('.', REVERSE(c.Path)) - 1))  AS file_type,
    c.Path                                                     AS storage_path,
    c.CreatedAt                                                AS uploaded_at
FROM Cobaltdesk_Legacy.dbo.CV_Docs c;
