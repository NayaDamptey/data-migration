USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.TaskItem;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'TaskItem';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'TaskItem', CAST(TRY_CAST(a.activity_id AS INT) * 10 + 1 AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Activities a
WHERE (a.candidate_id IS NOT NULL)
  AND NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));

INSERT INTO dbo.TaskItem (
    ID,
    TaskID,
    ObjectID,
    ObjectType,
    AddedAt
)
SELECT
    TRY_CAST(a.activity_id AS INT) * 10 + 1  AS ID,
    TRY_CAST(a.activity_id AS INT)           AS TaskID,
    a.candidate_id                           AS ObjectID,
    'Applicant'                              AS ObjectType,
    a.occurred_at                            AS AddedAt
FROM Migration_Staging.mid.Activities a
WHERE (a.candidate_id IS NOT NULL)
  AND (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'TaskItem', CAST(TRY_CAST(a.activity_id AS INT) * 10 + 2 AS NVARCHAR(200)), N'rejected', N'contact not migrated'
FROM Migration_Staging.mid.Activities a
WHERE (a.contact_id IS NOT NULL)
  AND NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Contacts x WHERE x.contact_id = a.contact_id AND x.client_id IS NOT NULL));

INSERT INTO dbo.TaskItem (
    ID,
    TaskID,
    ObjectID,
    ObjectType,
    AddedAt
)
SELECT
    TRY_CAST(a.activity_id AS INT) * 10 + 2  AS ID,
    TRY_CAST(a.activity_id AS INT)           AS TaskID,
    a.contact_id                             AS ObjectID,
    'Contact'                                AS ObjectType,
    a.occurred_at                            AS AddedAt
FROM Migration_Staging.mid.Activities a
WHERE (a.contact_id IS NOT NULL)
  AND (EXISTS (SELECT 1 FROM Migration_Staging.mid.Contacts x WHERE x.contact_id = a.contact_id AND x.client_id IS NOT NULL));

INSERT INTO dbo.TaskItem (
    ID,
    TaskID,
    ObjectID,
    ObjectType,
    AddedAt
)
SELECT
    TRY_CAST(a.activity_id AS INT) * 10 + 3  AS ID,
    TRY_CAST(a.activity_id AS INT)           AS TaskID,
    a.job_id                                 AS ObjectID,
    'Position'                               AS ObjectType,
    a.occurred_at                            AS AddedAt
FROM Migration_Staging.mid.Activities a
WHERE (a.job_id IS NOT NULL);

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'TaskItem', CAST(1000000 + TRY_CAST(iv.interview_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Interviews iv
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = iv.candidate_id));

INSERT INTO dbo.TaskItem (
    ID,
    TaskID,
    ObjectID,
    ObjectType,
    AddedAt
)
SELECT
    1000000 + TRY_CAST(iv.interview_id AS INT)  AS ID,
    100000 + TRY_CAST(iv.interview_id AS INT)   AS TaskID,
    iv.candidate_id                             AS ObjectID,
    'Applicant'                                 AS ObjectType,
    iv.created_at                               AS AddedAt
FROM Migration_Staging.mid.Interviews iv
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = iv.candidate_id));
