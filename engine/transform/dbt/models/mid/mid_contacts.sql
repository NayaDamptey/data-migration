{{ config(alias='Contacts') }}
SELECT
    s.contact_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'client' AND m.duplicate = s.client_id), s.client_id) AS client_id,
    s.first_name,
    s.last_name,
    s.job_title,
    s.email,
    s.phone,
    s.mobile,
    s.status,
    s.owner_user_id,
    s.created_at
FROM {{ ref('stg_contacts') }} s
WHERE s.contact_id NOT IN (SELECT duplicate FROM {{ ref('merges') }} WHERE kind = 'contact')
