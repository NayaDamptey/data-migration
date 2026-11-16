-- generated: the middle tier for Notes, with the reviewer's duplicate merges applied
{{ config(alias='Notes') }}
SELECT
    s.note_id,
    s.entity_type,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = s.entity_type AND m.duplicate = s.entity_id), s.entity_id) AS entity_id,
    s.author_user_id,
    s.note_type,
    s.body,
    s.created_at
FROM {{ ref('stg_notes') }} s
