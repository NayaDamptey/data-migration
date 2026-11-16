-- generated from spec/target.yml: middle tier -> PositionAttachment
{{ config(alias='PositionAttachment') }}
SELECT
    TRY_CAST(CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END AS INTEGER) AS ID,
    TRY_CAST(CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END AS INTEGER) AS AttachmentID,
    TRY_CAST(TRY_CAST(d.entity_id AS INT) AS INTEGER) AS PositionID,
    TRY_CAST(d.uploaded_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_documents') }} AS d
WHERE (d.entity_type = 'job')
  AND ((d.entity_type = 'candidate' AND EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = d.entity_id)) OR (d.entity_type = 'contact' AND EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'job' AND EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'client' AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = d.entity_id)))
