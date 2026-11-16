{{ config(alias='Placements') }}
SELECT
    s.placement_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'job' AND m.duplicate = s.job_id), s.job_id) AS job_id,
    s.start_date,
    s.end_date,
    s.salary,
    s.fee,
    s.placement_type,
    s.owner_user_id
FROM {{ ref('stg_placements') }} s
