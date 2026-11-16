-- generated from spec/target.yml: middle tier -> Timesheets
{{ config(alias='Timesheets') }}
SELECT
    TRY_CAST(TRY_CAST(t.timesheet_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(t.start_date AS DATE) AS StartDate,
    TRY_CAST(t.end_date AS DATE) AS EndDate,
    TRY_CAST(t.pay_rate AS DECIMAL(8,2)) AS Payrate,
    TRY_CAST(t.charge_rate AS DECIMAL(8,2)) AS ChargeRate,
    TRY_CAST('GBP' AS VARCHAR) AS Currency,
    TRY_CAST(UPPER(LEFT(CAST(t.status AS TEXT), 1)) || SUBSTRING(t.status, 2, 50) AS VARCHAR) AS Status,
    TRY_CAST(t.timesheet_type AS VARCHAR) AS TimesheetType,
    TRY_CAST((SELECT SUM(l.hours) FROM {{ ref('mid_timesheet_lines') }} AS l WHERE l.timesheet_id = t.timesheet_id) AS DOUBLE) AS TotalWeekHours,
    TRY_CAST(t.approved_by AS VARCHAR) AS ApprovedBy,
    TRY_CAST(0 AS BOOLEAN) AS Deleted
FROM {{ ref('mid_timesheets') }} AS t
