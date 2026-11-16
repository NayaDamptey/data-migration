-- generated: the middle tier for Documents, with the reviewer's duplicate merges applied
{{ config(alias='Documents') }}
SELECT
    s.document_id,
    s.entity_type,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = s.entity_type AND m.duplicate = s.entity_id), s.entity_id) AS entity_id,
    s.file_name,
    s.file_type,
    s.storage_path,
    s.uploaded_at
FROM {{ ref('stg_documents') }} s
