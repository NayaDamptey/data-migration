-- generated from spec/target.yml: middle tier -> Contact
{{ config(alias='Contact') }}
SELECT
    TRY_CAST(ct.contact_id AS VARCHAR) AS ID,
    TRY_CAST(ct.first_name AS VARCHAR) AS FirstName,
    TRY_CAST(ct.last_name AS VARCHAR) AS LastName,
    TRY_CAST(ct.client_id AS VARCHAR) AS CompanyID,
    TRY_CAST(ct.email AS VARCHAR) AS Email,
    TRY_CAST(COALESCE(ct.phone, ct.mobile) AS VARCHAR) AS Phone,
    TRY_CAST(LEFT(CAST(ct.job_title AS TEXT), 50) AS VARCHAR) AS PositionTitle,
    TRY_CAST('Client contact' AS VARCHAR) AS Contacttype,
    TRY_CAST(ct.owner_user_id AS VARCHAR) AS ContactOwnerID,
    TRY_CAST(0 AS BOOLEAN) AS IsDeleted,
    TRY_CAST(CASE WHEN ct.status = 'inactive' THEN 1 ELSE 0 END AS BOOLEAN) AS IsArchived,
    TRY_CAST(ct.owner_user_id AS VARCHAR) AS AddedBy,
    TRY_CAST(ct.created_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_contacts') }} AS ct
WHERE (NOT ct.client_id IS NULL AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = ct.client_id))
