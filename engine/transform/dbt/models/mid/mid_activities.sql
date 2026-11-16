{{ config(alias='Activities') }}
SELECT
    s.activity_id,
    s.activity_type,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'contact' AND m.duplicate = s.contact_id), s.contact_id) AS contact_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'job' AND m.duplicate = s.job_id), s.job_id) AS job_id,
    s.user_id,
    s.occurred_at,
    s.outcome,
    s.subject
FROM {{ ref('stg_activities') }} s
