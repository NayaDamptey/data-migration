{{ config(alias='TimesheetLines') }}
SELECT
    s.line_id,
    s.timesheet_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'job' AND m.duplicate = s.job_id), s.job_id) AS job_id,
    s.line_type,
    s.start_time,
    s.end_time,
    s.hours,
    s.added_by,
    s.created_at
FROM {{ ref('stg_timesheet_lines') }} s
WHERE s.line_id NOT IN (SELECT duplicate FROM {{ ref('merges') }} WHERE kind = 'timesheet_line')
