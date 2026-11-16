{{ config(alias='Histories') }}
SELECT
    s.history_id,
    s.entity_type,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = s.entity_type AND m.duplicate = s.entity_id), s.entity_id) AS entity_id,
    s.field_changed,
    s.old_value,
    s.new_value,
    s.changed_by,
    s.changed_at
FROM {{ ref('stg_histories') }} s
