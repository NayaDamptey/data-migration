-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(sc.Schedule_ID AS VARCHAR) AS activity_id,
    TRY_CAST(sc.ScheduleType AS VARCHAR) AS activity_type,
    TRY_CAST(CASE WHEN sc.Person_Type = 'Candidate' THEN sc.Person_ID END AS VARCHAR) AS candidate_id,
    TRY_CAST(CASE WHEN sc.Person_Type = 'Contact' THEN ct.AssociateID END AS VARCHAR) AS contact_id,
    TRY_CAST(sc.Req_ID AS VARCHAR) AS job_id,
    TRY_CAST(sc.CreatedBy AS VARCHAR) AS user_id,
    TRY_CAST(sc.StartDate AS TIMESTAMP) AS occurred_at,
    TRY_CAST(NULL AS VARCHAR) AS outcome,
    TRY_CAST(sc.Notes AS VARCHAR) AS subject
FROM {{ source('legacy', 'Schedule') }} AS sc
LEFT JOIN LATERAL (SELECT MIN(s.AssociateID) AS AssociateID FROM {{ source('legacy', 'Associates') }} AS s WHERE s.Person_ID = sc.Person_ID) AS ct ON TRUE
