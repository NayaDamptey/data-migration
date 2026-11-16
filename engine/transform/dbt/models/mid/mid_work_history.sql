-- generated: the middle tier for Work history, with the reviewer's duplicate merges applied
{{ config(alias='WorkHistory') }}
SELECT
    s.history_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    s.employer,
    s.job_title,
    s.start_date,
    s.end_date,
    s.deleted
FROM {{ ref('stg_work_history') }} s
