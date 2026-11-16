-- generated from spec/target.yml: middle tier -> TimesheetActivity
{{ config(alias='TimesheetActivity') }}
SELECT
    TRY_CAST(TRY_CAST(l.line_id AS INT) AS INTEGER) AS ActivityID,
    TRY_CAST(TRY_CAST(l.timesheet_id AS INT) AS INTEGER) AS TimesheetID,
    TRY_CAST(TRY_CAST(l.candidate_id AS INT) AS INTEGER) AS AssocID,
    TRY_CAST(t.start_date AS DATE) AS TimesheetDate,
    TRY_CAST(l.hours AS DOUBLE) AS HoursWorked,
    TRY_CAST(t.status AS VARCHAR) AS Status,
    TRY_CAST(l.added_by AS VARCHAR) AS AddedBy,
    TRY_CAST(l.created_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_timesheet_lines') }} AS l
LEFT JOIN {{ ref('mid_timesheets') }} AS t ON t.timesheet_id = l.timesheet_id
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = l.candidate_id))
