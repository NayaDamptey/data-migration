{{ config(alias='Applications') }}
SELECT
    s.application_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'job' AND m.duplicate = s.job_id), s.job_id) AS job_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'client' AND m.duplicate = s.client_id), s.client_id) AS client_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'contact' AND m.duplicate = s.contact_id), s.contact_id) AS contact_id,
    s.stage,
    s.employment_type,
    s.start_date,
    s.end_date,
    s.fee,
    s.source,
    s.owner_user_id,
    s.deleted,
    s.applied_at
FROM {{ ref('stg_applications') }} s
