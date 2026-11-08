USE Migration_Staging;

TRUNCATE TABLE mid.TimesheetLines;

INSERT INTO mid.TimesheetLines (
    line_id,
    timesheet_id,
    candidate_id,
    job_id,
    line_type,
    start_time,
    end_time,
    hours,
    added_by,
    created_at
)
SELECT
    i.ItemID        AS line_id,
    i.Timesheet_ID  AS timesheet_id,
    i.Person_ID     AS candidate_id,
    i.Req_ID        AS job_id,
    tt.[Desc]       AS line_type,
    i.StartTime     AS start_time,
    i.EndTime       AS end_time,
    i.TotalHours    AS hours,
    i.CreatedBy     AS added_by,
    i.CreatedAt     AS created_at
FROM Cobaltdesk_Legacy.dbo.TimesheetItems i
LEFT JOIN Cobaltdesk_Legacy.dbo.TimesheetType tt ON tt.Timesheet_TypeID = i.Timesheet_TypeID;
