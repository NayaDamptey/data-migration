USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Comms;

INSERT INTO dbo.Comms (
    ID,
    ObjectID,
    ObjectType,
    Value,
    Type,
    Deleted,
    AddedBy
)
SELECT
    TRY_CAST(ca.candidate_id AS INT) * 10 + 1  AS ID,
    ca.candidate_id                            AS ObjectID,
    'Applicant'                                AS ObjectType,
    ca.email                                   AS Value,
    'Email'                                    AS Type,
    0                                          AS Deleted,
    ca.owner_user_id                           AS AddedBy
FROM Migration_Staging.mid.Candidates ca
WHERE (ca.email IS NOT NULL);

INSERT INTO dbo.Comms (
    ID,
    ObjectID,
    ObjectType,
    Value,
    Type,
    Deleted,
    AddedBy
)
SELECT
    TRY_CAST(ca.candidate_id AS INT) * 10 + 2  AS ID,
    ca.candidate_id                            AS ObjectID,
    'Applicant'                                AS ObjectType,
    ca.mobile                                  AS Value,
    'Mobile'                                   AS Type,
    0                                          AS Deleted,
    ca.owner_user_id                           AS AddedBy
FROM Migration_Staging.mid.Candidates ca
WHERE (ca.mobile IS NOT NULL);
