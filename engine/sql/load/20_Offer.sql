USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Offer;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Offer';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Offer', CAST(TRY_CAST(a.application_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Applications a
WHERE (a.stage IN ('offer', 'placed'))
  AND NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));

INSERT INTO dbo.Offer (
    ID,
    PlacementID,
    Accepted,
    Terms,
    RecruiterID
)
SELECT
    TRY_CAST(a.application_id AS INT)                                        AS ID,
    CASE WHEN a.stage = 'placed' THEN TRY_CAST(a.application_id AS INT) END  AS PlacementID,
    CASE WHEN a.stage = 'placed' THEN 1 ELSE 0 END                           AS Accepted,
    a.employment_type                                                        AS Terms,
    a.owner_user_id                                                          AS RecruiterID
FROM Migration_Staging.mid.Applications a
WHERE (a.stage IN ('offer', 'placed'))
  AND (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = a.candidate_id));
