SELECT
    TRY_CAST(n.Note_ID AS VARCHAR) AS note_id,
    TRY_CAST(CASE n.ObjectType WHEN 'Person' THEN CASE WHEN NOT pc.AssociateID IS NULL THEN 'contact' ELSE 'candidate' END WHEN 'Associate' THEN 'contact' WHEN 'Req' THEN 'job' WHEN 'Account' THEN 'client' END AS VARCHAR) AS entity_type,
    TRY_CAST(CASE WHEN n.ObjectType = 'Person' AND NOT pc.AssociateID IS NULL THEN CAST(pc.AssociateID AS VARCHAR) ELSE CAST(n.ObjectId AS VARCHAR) END AS VARCHAR) AS entity_id,
    TRY_CAST(n.CreatedBy AS VARCHAR) AS author_user_id,
    TRY_CAST(NULL AS VARCHAR) AS note_type,
    TRY_CAST(n.Notetext AS VARCHAR) AS body,
    TRY_CAST(n.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'Notes') }} AS n
LEFT JOIN LATERAL (SELECT MIN(s.AssociateID) AS AssociateID FROM {{ source('legacy', 'Associates') }} AS s WHERE n.ObjectType = 'Person' AND s.Person_ID = n.ObjectId) AS pc ON TRUE
