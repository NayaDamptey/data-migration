-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(f.Interview_FeedbackID AS VARCHAR) AS interview_id,
    TRY_CAST(f.Interviewee_ID AS VARCHAR) AS candidate_id,
    TRY_CAST(f.Interviewer_ID AS VARCHAR) AS interviewer_person_id,
    TRY_CAST(f.Interview_Date AS TIMESTAMP) AS interview_date,
    TRY_CAST(f.Notes AS VARCHAR) AS feedback,
    TRY_CAST(f.Callback AS VARCHAR) AS callback,
    TRY_CAST(f.CreatedAt AS TIMESTAMP) AS created_at
FROM {{ source('legacy', 'Interview_Feedback') }} AS f
