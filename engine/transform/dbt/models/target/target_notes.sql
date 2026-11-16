-- generated from spec/target.yml: middle tier -> Notes
{{ config(alias='Notes') }}
SELECT
    TRY_CAST(TRY_CAST(n.note_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(n.body AS VARCHAR) AS Text,
    TRY_CAST(CASE WHEN n.entity_type = 'candidate' THEN n.entity_id END AS VARCHAR) AS ApplicantID,
    TRY_CAST(CASE WHEN n.entity_type = 'client' THEN n.entity_id END AS VARCHAR) AS CompanyID,
    TRY_CAST(CASE WHEN n.entity_type = 'job' THEN TRY_CAST(n.entity_id AS INT) END AS INTEGER) AS PositionID,
    TRY_CAST(CASE WHEN n.entity_type = 'contact' THEN n.entity_id END AS VARCHAR) AS ContactID,
    TRY_CAST(0 AS BOOLEAN) AS Deleted,
    TRY_CAST(n.created_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(n.author_user_id AS VARCHAR) AS UserID
FROM {{ ref('mid_notes') }} AS n
WHERE ((n.entity_type = 'candidate' AND EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = n.entity_id)) OR (n.entity_type = 'contact' AND EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = n.entity_id AND NOT x.client_id IS NULL)) OR (n.entity_type = 'job' AND EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = n.entity_id AND NOT x.client_id IS NULL)) OR (n.entity_type = 'client' AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = n.entity_id)))
