-- generated from spec/target.yml: middle tier -> Currencies
{{ config(alias='Currencies') }}
SELECT
    TRY_CAST(ROW_NUMBER() OVER (ORDER BY cu.currency NULLS FIRST) AS INTEGER) AS CurrencyID,
    TRY_CAST(cu.currency AS VARCHAR) AS CurrencyCode
FROM (SELECT DISTINCT currency FROM {{ ref('mid_invoices') }} WHERE NOT currency IS NULL) AS cu
