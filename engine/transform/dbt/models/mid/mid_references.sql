-- generated: the middle tier for References, with the reviewer's duplicate merges applied
{{ config(alias='References') }}
SELECT
    s.reference_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    s.full_name,
    s.job_title,
    s.company,
    s.relationship,
    s.email,
    s.phone,
    s.status,
    s.reference_text,
    s.created_at,
    s.updated_at
FROM {{ ref('stg_references') }} s
