USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Timesheets;

INSERT INTO dbo.Timesheets (
    ID,
    StartDate,
    EndDate,
    Payrate,
    ChargeRate,
    Currency,
    Status,
    TimesheetType,
    TotalWeekHours,
    ApprovedBy,
    Deleted
)
SELECT
    TRY_CAST(t.timesheet_id AS INT)                                                                          AS ID,
    t.start_date                                                                                             AS StartDate,
    t.end_date                                                                                               AS EndDate,
    t.pay_rate                                                                                               AS Payrate,
    t.charge_rate                                                                                            AS ChargeRate,
    'GBP'                                                                                                    AS Currency,
    UPPER(LEFT(t.status, 1)) + SUBSTRING(t.status, 2, 50)                                                    AS Status,
    t.timesheet_type                                                                                         AS TimesheetType,
    (SELECT SUM(l.hours) FROM Migration_Staging.mid.TimesheetLines l WHERE l.timesheet_id = t.timesheet_id)  AS TotalWeekHours,
    t.approved_by                                                                                            AS ApprovedBy,
    0                                                                                                        AS Deleted
FROM Migration_Staging.mid.Timesheets t;
