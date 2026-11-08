USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Deal;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Deal';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Deal', CAST(TRY_CAST(pl.placement_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Placements pl
LEFT JOIN Migration_Staging.mid.Jobs j ON j.job_id = pl.job_id
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id));

INSERT INTO dbo.Deal (
    ID,
    PlacementID,
    RecruiterID,
    CompanyID,
    DealDate,
    DealType,
    DealValue
)
SELECT
    TRY_CAST(pl.placement_id AS INT)  AS ID,
    TRY_CAST(pl.placement_id AS INT)  AS PlacementID,
    pl.owner_user_id                  AS RecruiterID,
    j.client_id                       AS CompanyID,
    pl.start_date                     AS DealDate,
    pl.placement_type                 AS DealType,
    pl.fee                            AS DealValue
FROM Migration_Staging.mid.Placements pl
LEFT JOIN Migration_Staging.mid.Jobs j ON j.job_id = pl.job_id
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id));
