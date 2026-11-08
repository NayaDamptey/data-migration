USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Placements;

DELETE FROM dbo.MigrationRejects WHERE target_table = N'Placements';

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Placements', CAST(TRY_CAST(pl.placement_id AS INT) AS NVARCHAR(200)), N'rejected', N'not a migrated candidate (a contact, a removed duplicate or missing)'
FROM Migration_Staging.mid.Placements pl
LEFT JOIN Migration_Staging.mid.Jobs j ON j.job_id = pl.job_id
WHERE NOT (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id));

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Placements', CAST(TRY_CAST(pl.placement_id AS INT) AS NVARCHAR(200)), N'flagged', N'live placement on a deleted job'
FROM Migration_Staging.mid.Placements pl
LEFT JOIN Migration_Staging.mid.Jobs j ON j.job_id = pl.job_id
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id))
  AND NOT (NOT EXISTS (SELECT 1 FROM Migration_Staging.mid.Jobs x WHERE x.job_id = pl.job_id AND x.status = 'deleted'));

INSERT INTO dbo.MigrationRejects (target_table, source_key, action, reason)
SELECT N'Placements', CAST(TRY_CAST(pl.placement_id AS INT) AS NVARCHAR(200)), N'flagged', N'live placement on a deleted company'
FROM Migration_Staging.mid.Placements pl
LEFT JOIN Migration_Staging.mid.Jobs j ON j.job_id = pl.job_id
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id))
  AND NOT (NOT EXISTS (SELECT 1 FROM Migration_Staging.mid.Clients x WHERE x.client_id = j.client_id AND x.status = 'deleted'));

INSERT INTO dbo.Placements (
    ID,
    ApplicantID,
    PositionID,
    CompanyID,
    EmploymentType,
    StartDate,
    EndDate,
    Fee,
    Status,
    OwnerID
)
SELECT
    TRY_CAST(pl.placement_id AS INT)  AS ID,
    pl.candidate_id                   AS ApplicantID,
    TRY_CAST(pl.job_id AS INT)        AS PositionID,
    j.client_id                       AS CompanyID,
    pl.placement_type                 AS EmploymentType,
    pl.start_date                     AS StartDate,
    pl.end_date                       AS EndDate,
    pl.fee                            AS Fee,
    'Placed'                          AS Status,
    pl.owner_user_id                  AS OwnerID
FROM Migration_Staging.mid.Placements pl
LEFT JOIN Migration_Staging.mid.Jobs j ON j.job_id = pl.job_id
WHERE (EXISTS (SELECT 1 FROM Migration_Staging.mid.Candidates x WHERE x.candidate_id = pl.candidate_id));
