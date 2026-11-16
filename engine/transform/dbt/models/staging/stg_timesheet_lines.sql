SELECT
    TRY_CAST(i.ItemID AS VARCHAR) AS line_id,
    TRY_CAST(i.Timesheet_ID AS VARCHAR) AS timesheet_id,
    TRY_CAST(i.Person_ID AS VARCHAR) AS candidate_id,
    TRY_CAST(i.Req_ID AS VARCHAR) AS job_id,
    TRY_CAST(tt."Desc" AS VARCHAR) AS line_type,
    TRY_CAST(i.StartTime AS VARCHAR) AS start_time,
    TRY_CAST(i.EndTime AS VARCHAR) AS end_time,
    TRY_CAST(i.TotalHours AS DECIMAL(12,2)) AS hours,
    TRY_CAST(i.CreatedBy AS VARCHAR) AS added_by,
    TRY_CAST(i.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'TimesheetItems') }} AS i
LEFT JOIN {{ source('legacy', 'TimesheetType') }} AS tt ON tt.Timesheet_TypeID = i.Timesheet_TypeID
