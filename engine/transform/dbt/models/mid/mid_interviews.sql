-- generated: the middle tier for Interviews, with the reviewer's duplicate merges applied
{{ config(alias='Interviews') }}
SELECT
    s.interview_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    s.interviewer_person_id,
    s.interview_date,
    s.feedback,
    s.callback,
    s.created_at
FROM {{ ref('stg_interviews') }} s
