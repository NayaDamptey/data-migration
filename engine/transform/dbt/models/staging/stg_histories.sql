SELECT
    TRY_CAST(l.LogID AS VARCHAR) AS history_id,
    TRY_CAST(LOWER(l.Entity_Type) AS VARCHAR) AS entity_type,
    TRY_CAST(l.Entity_ID AS VARCHAR) AS entity_id,
    TRY_CAST(l.Action AS VARCHAR) AS field_changed,
    TRY_CAST(NULL AS VARCHAR) AS old_value,
    TRY_CAST(NULL AS VARCHAR) AS new_value,
    TRY_CAST(l.User_ID AS VARCHAR) AS changed_by,
    TRY_CAST(l.Timestamp AS TIMESTAMP) AS changed_at
FROM {{ source('legacy', 'Log') }} AS l
