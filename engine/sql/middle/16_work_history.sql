USE Migration_Staging;

TRUNCATE TABLE mid.WorkHistory;

INSERT INTO mid.WorkHistory (
    history_id,
    candidate_id,
    employer,
    job_title,
    start_date,
    end_date,
    deleted
)
SELECT
    eh.Hist_ID                   AS history_id,
    ep.Person_ID                 AS candidate_id,
    eh.PlaceofWork               AS employer,
    eh.Title                     AS job_title,
    CAST(eh.Started_At AS DATE)  AS start_date,
    CAST(eh.Ended_At AS DATE)    AS end_date,
    eh.Deleted                   AS deleted
FROM Cobaltdesk_Legacy.dbo.EmpHist eh
JOIN Cobaltdesk_Legacy.dbo.Emp_Profile ep ON ep.Emp_ProfileID = eh.Emp_ID;
