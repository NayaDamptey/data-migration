USE Migration_Staging;

TRUNCATE TABLE mid.Notes;

INSERT INTO mid.Notes (
    note_id,
    entity_type,
    entity_id,
    author_user_id,
    note_type,
    body,
    created_at
)
SELECT
    n.Note_ID                                                                                                                                                                                             AS note_id,
    CASE n.ObjectType WHEN 'Person' THEN CASE WHEN pc.AssociateID IS NOT NULL THEN 'contact' ELSE 'candidate' END WHEN 'Associate' THEN 'contact' WHEN 'Req' THEN 'job' WHEN 'Account' THEN 'client' END  AS entity_type,
    CASE WHEN n.ObjectType = 'Person' AND pc.AssociateID IS NOT NULL THEN CAST(pc.AssociateID AS NVARCHAR(50)) ELSE CAST(n.ObjectId AS NVARCHAR(50)) END                                                  AS entity_id,
    n.CreatedBy                                                                                                                                                                                           AS author_user_id,
    NULL                                                                                                                                                                                                  AS note_type,
    n.Notetext                                                                                                                                                                                            AS body,
    n.CreatedAt                                                                                                                                                                                           AS created_at
FROM Cobaltdesk_Legacy.dbo.Notes n
OUTER APPLY (SELECT MIN(s.AssociateID) AS AssociateID FROM Cobaltdesk_Legacy.dbo.Associates s WHERE n.ObjectType = 'Person' AND s.Person_ID = n.ObjectId) pc;
