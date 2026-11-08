USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.TimesheetActivity;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'TimesheetActivity';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'TimesheetActivity', CAST(TRY_CAST(l.line_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.TimesheetLines l
LEFT JOIN Migration_Staging.mid.Timesheets t ON t.timesheet_id = l.timesheet_id
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = l.candidate_id));

INSERT INTO dbo.TimesheetActivity (
    ActivityID,
    TimesheetID,
    AssocID,
    TimesheetDate,
    HoursWorked,
    Status,
    AddedBy,
    AddedAt
)
SELECT
    TRY_CAST(l.line_id AS INT)       AS ActivityID,
    TRY_CAST(l.timesheet_id AS INT)  AS TimesheetID,
    TRY_CAST(l.candidate_id AS INT)  AS AssocID,
    t.start_date                     AS TimesheetDate,
    l.hours                          AS HoursWorked,
    t.status                         AS Status,
    l.added_by                       AS AddedBy,
    l.created_at                     AS AddedAt
FROM Migration_Staging.mid.TimesheetLines l
LEFT JOIN Migration_Staging.mid.Timesheets t ON t.timesheet_id = l.timesheet_id
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = l.candidate_id));
