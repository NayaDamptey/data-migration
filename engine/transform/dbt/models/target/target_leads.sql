-- generated from spec/target.yml: middle tier -> Leads
{{ config(alias='Leads') }}
SELECT
    TRY_CAST(TRY_CAST(ld.lead_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(ld.full_name AS VARCHAR) AS Fullname,
    TRY_CAST(ld.status AS VARCHAR) AS PipelineStage,
    TRY_CAST(ld.client_id AS VARCHAR) AS CompanyID,
    TRY_CAST(ld.title AS VARCHAR) AS Type,
    TRY_CAST(ld.source AS VARCHAR) AS Source,
    TRY_CAST(ld.note AS VARCHAR) AS Notes,
    TRY_CAST(0 AS BOOLEAN) AS Deleted,
    TRY_CAST(ld.sourced_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(ld.assigned_to AS VARCHAR) AS AddedBy
FROM {{ ref('mid_leads') }} AS ld
