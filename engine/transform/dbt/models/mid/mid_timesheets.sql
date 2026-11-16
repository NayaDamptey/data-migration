-- generated: the middle tier for Timesheets, with the reviewer's duplicate merges applied
{{ config(alias='Timesheets') }}
SELECT
    s.timesheet_id,
    s.po_no,
    s.timesheet_type,
    s.pay_rate,
    s.charge_rate,
    s.start_date,
    s.end_date,
    s.status,
    s.approved_by,
    s.approved_at
FROM {{ ref('stg_timesheets') }} s
