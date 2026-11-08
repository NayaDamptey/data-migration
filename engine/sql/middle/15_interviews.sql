USE Migration_Staging;

TRUNCATE TABLE mid.Interviews;

INSERT INTO mid.Interviews (
    interview_id,
    candidate_id,
    interviewer_person_id,
    interview_date,
    feedback,
    callback,
    created_at
)
SELECT
    f.Interview_FeedbackID  AS interview_id,
    f.Interviewee_ID        AS candidate_id,
    f.Interviewer_ID        AS interviewer_person_id,
    f.Interview_Date        AS interview_date,
    f.Notes                 AS feedback,
    f.Callback              AS callback,
    f.CreatedAt             AS created_at
FROM Cobaltdesk_Legacy.dbo.Interview_Feedback f;
