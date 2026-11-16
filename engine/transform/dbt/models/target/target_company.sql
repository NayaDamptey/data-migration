-- generated from spec/target.yml: middle tier -> Company
{{ config(alias='Company') }}
SELECT
    TRY_CAST(c.client_id AS VARCHAR) AS ID,
    TRY_CAST(LEFT(CAST(c.company_name AS TEXT), 50) AS VARCHAR) AS CompanyName,
    TRY_CAST(c.industry AS VARCHAR) AS Industry,
    TRY_CAST(LEFT(CAST(c.website AS TEXT), 50) AS VARCHAR) AS Website,
    TRY_CAST(c.phone AS VARCHAR) AS Telephone,
    TRY_CAST(CASE WHEN NOT c.address_line_1 IS NULL THEN c.client_id END AS VARCHAR) AS LocationID,
    TRY_CAST('Client' AS VARCHAR) AS Type,
    TRY_CAST(c.owner_user_id AS VARCHAR) AS Company_OwnerID,
    TRY_CAST(c.owner_user_id AS VARCHAR) AS AddedBy,
    TRY_CAST(c.created_at AS TIMESTAMP) AS AddedDate,
    TRY_CAST(CASE WHEN c.status = 'deleted' THEN 1 ELSE 0 END AS BOOLEAN) AS Isdeleted,
    TRY_CAST(0 AS BOOLEAN) AS IsArchive
FROM {{ ref('mid_clients') }} AS c
