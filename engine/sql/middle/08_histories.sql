USE Migration_Staging;

TRUNCATE TABLE mid.Histories;

INSERT INTO mid.Histories (
    history_id,
    entity_type,
    entity_id,
    field_changed,
    old_value,
    new_value,
    changed_by,
    changed_at
)
SELECT
    l.LogID               AS history_id,
    LOWER(l.Entity_Type)  AS entity_type,
    l.Entity_ID           AS entity_id,
    l.Action              AS field_changed,
    NULL                  AS old_value,
    NULL                  AS new_value,
    l.User_ID             AS changed_by,
    l.Timestamp           AS changed_at
FROM Cobaltdesk_Legacy.dbo.Log l;
