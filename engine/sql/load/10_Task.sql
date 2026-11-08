USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Task;

INSERT INTO dbo.Task (
    ID,
    TaskType,
    OwnerUserID,
    Subject,
    Note,
    Status,
    StartDate,
    Completed,
    AddedAt
)
SELECT
    TRY_CAST(a.activity_id AS INT)  AS ID,
    a.activity_type                 AS TaskType,
    a.user_id                       AS OwnerUserID,
    LEFT(a.subject, 50)             AS Subject,
    a.subject                       AS Note,
    'Completed'                     AS Status,
    CAST(a.occurred_at AS DATE)     AS StartDate,
    1                               AS Completed,
    a.occurred_at                   AS AddedAt
FROM Migration_Staging.mid.Activities a;

INSERT INTO dbo.Task (
    ID,
    TaskType,
    OwnerUserID,
    Subject,
    Note,
    Status,
    StartDate,
    Completed,
    AddedAt
)
SELECT
    100000 + TRY_CAST(iv.interview_id AS INT)  AS ID,
    'Interview'                                AS TaskType,
    NULL                                       AS OwnerUserID,
    'Interview feedback'                       AS Subject,
    iv.feedback                                AS Note,
    'Completed'                                AS Status,
    CAST(iv.interview_date AS DATE)            AS StartDate,
    1                                          AS Completed,
    iv.created_at                              AS AddedAt
FROM Migration_Staging.mid.Interviews iv;
