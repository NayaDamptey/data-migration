-- generated: the middle tier for Leads, with the reviewer's duplicate merges applied
{{ config(alias='Leads') }}
SELECT
    s.lead_id,
    s.full_name,
    s.title,
    s.status,
    s.source,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'client' AND m.duplicate = s.client_id), s.client_id) AS client_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'contact' AND m.duplicate = s.contact_id), s.contact_id) AS contact_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'job' AND m.duplicate = s.job_id), s.job_id) AS job_id,
    s.email,
    s.phone,
    s.note,
    s.assigned_to,
    s.sourced_at
FROM {{ ref('stg_leads') }} s
