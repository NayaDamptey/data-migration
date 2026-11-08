USE Migration_Staging;

TRUNCATE TABLE mid.Activities;

INSERT INTO mid.Activities (
    activity_id,
    activity_type,
    candidate_id,
    contact_id,
    job_id,
    user_id,
    occurred_at,
    outcome,
    subject
)
SELECT
    sc.Schedule_ID                                                AS activity_id,
    sc.ScheduleType                                               AS activity_type,
    CASE WHEN sc.Person_Type = 'Candidate' THEN sc.Person_ID END  AS candidate_id,
    CASE WHEN sc.Person_Type = 'Contact' THEN ct.AssociateID END  AS contact_id,
    sc.Req_ID                                                     AS job_id,
    sc.CreatedBy                                                  AS user_id,
    sc.StartDate                                                  AS occurred_at,
    NULL                                                          AS outcome,
    sc.Notes                                                      AS subject
FROM Cobaltdesk_Legacy.dbo.Schedule sc
OUTER APPLY (SELECT MIN(s.AssociateID) AS AssociateID FROM Cobaltdesk_Legacy.dbo.Associates s WHERE s.Person_ID = sc.Person_ID) ct;
