USE Migration_Staging;

TRUNCATE TABLE mid.Timesheets;

INSERT INTO mid.Timesheets (
    timesheet_id,
    po_no,
    timesheet_type,
    pay_rate,
    charge_rate,
    start_date,
    end_date,
    status,
    approved_by,
    approved_at
)
SELECT
    t.ID                       AS timesheet_id,
    t.PONo                     AS po_no,
    tt.[Desc]                  AS timesheet_type,
    t.Payrate                  AS pay_rate,
    t.Billrate                 AS charge_rate,
    CAST(t.StartDate AS DATE)  AS start_date,
    CAST(t.Enddate AS DATE)    AS end_date,
    LOWER(t.Status)            AS status,
    t.Approved_By              AS approved_by,
    t.Approved_Date            AS approved_at
FROM Cobaltdesk_Legacy.dbo.TimeSheets t
LEFT JOIN Cobaltdesk_Legacy.dbo.TimesheetType tt ON tt.Timesheet_TypeID = t.Timesheet_TypeID;
