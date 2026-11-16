-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(t.ID AS VARCHAR) AS timesheet_id,
    TRY_CAST(t.PONo AS VARCHAR) AS po_no,
    TRY_CAST(tt."Desc" AS VARCHAR) AS timesheet_type,
    TRY_CAST(t.Payrate AS DECIMAL(12,2)) AS pay_rate,
    TRY_CAST(t.Billrate AS DECIMAL(12,2)) AS charge_rate,
    TRY_CAST(CAST(t.StartDate AS DATE) AS DATE) AS start_date,
    TRY_CAST(CAST(t.Enddate AS DATE) AS DATE) AS end_date,
    TRY_CAST(LOWER(t.Status) AS VARCHAR) AS status,
    TRY_CAST(t.Approved_By AS VARCHAR) AS approved_by,
    TRY_CAST(t.Approved_Date AS TIMESTAMP) AS approved_at
FROM {{ source('legacy', 'TimeSheets') }} AS t
LEFT JOIN {{ source('legacy', 'TimesheetType') }} AS tt ON tt.Timesheet_TypeID = t.Timesheet_TypeID
