-- generated: the middle tier for Jobs, with the reviewer's duplicate merges applied
{{ config(alias='Jobs') }}
SELECT
    s.job_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'client' AND m.duplicate = s.client_id), s.client_id) AS client_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'contact' AND m.duplicate = s.contact_id), s.contact_id) AS contact_id,
    s.title,
    s.employment_type,
    s.salary_min,
    s.salary_max,
    s.rate,
    s.rate_unit,
    s.location,
    s.status,
    s.owner_user_id,
    s.opened_at,
    s.closed_at,
    s.description
FROM {{ ref('stg_jobs') }} s
WHERE s.job_id NOT IN (SELECT duplicate FROM {{ ref('merges') }} WHERE kind = 'job')
