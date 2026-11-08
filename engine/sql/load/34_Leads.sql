USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Leads;

INSERT INTO dbo.Leads (
    ID,
    Fullname,
    PipelineStage,
    CompanyID,
    Type,
    Source,
    Notes,
    Deleted,
    AddedAt,
    AddedBy
)
SELECT
    TRY_CAST(ld.lead_id AS INT)  AS ID,
    ld.full_name                 AS Fullname,
    ld.status                    AS PipelineStage,
    ld.client_id                 AS CompanyID,
    ld.title                     AS Type,
    ld.source                    AS Source,
    ld.note                      AS Notes,
    0                            AS Deleted,
    ld.sourced_at                AS AddedAt,
    ld.assigned_to               AS AddedBy
FROM Migration_Staging.mid.Leads ld;
