USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Deal_Stage;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Deal_Stage';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Deal_Stage', CAST(TRY_CAST(pl.placement_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Placements pl
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id));

INSERT INTO dbo.Deal_Stage (
    ID,
    DealID,
    Stage
)
SELECT
    TRY_CAST(pl.placement_id AS INT)  AS ID,
    TRY_CAST(pl.placement_id AS INT)  AS DealID,
    'Won'                             AS Stage
FROM Migration_Staging.mid.Placements pl
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id));
