SELECT
    TRY_CAST(eh.Hist_ID AS VARCHAR) AS history_id,
    TRY_CAST(ep.Person_ID AS VARCHAR) AS candidate_id,
    TRY_CAST(eh.PlaceofWork AS VARCHAR) AS employer,
    TRY_CAST(eh.Title AS VARCHAR) AS job_title,
    TRY_CAST(CAST(eh.Started_At AS DATE) AS DATE) AS start_date,
    TRY_CAST(CAST(eh.Ended_At AS DATE) AS DATE) AS end_date,
    TRY_CAST(eh.Deleted AS BOOLEAN) AS deleted
FROM {{ source('legacy', 'EmpHist') }} AS eh
JOIN {{ source('legacy', 'Emp_Profile') }} AS ep ON ep.Emp_ProfileID = eh.Emp_ID
