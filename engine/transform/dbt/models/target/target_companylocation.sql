-- generated from spec/target.yml: middle tier -> CompanyLocation
{{ config(alias='CompanyLocation') }}
SELECT
    TRY_CAST(c.client_id AS VARCHAR) AS ID,
    TRY_CAST(c.client_id AS VARCHAR) AS CompanyID,
    TRY_CAST(c.address_line_1 AS VARCHAR) AS AddressLine1,
    TRY_CAST(c.address_line_2 AS VARCHAR) AS AddressLine2,
    TRY_CAST(c.city AS VARCHAR) AS City,
    TRY_CAST(c.postcode AS VARCHAR) AS PostCode,
    TRY_CAST(c.country AS VARCHAR) AS Country,
    TRY_CAST(c.created_at AS TIMESTAMP) AS AddedAt
FROM {{ ref('mid_clients') }} AS c
WHERE (NOT c.address_line_1 IS NULL)
