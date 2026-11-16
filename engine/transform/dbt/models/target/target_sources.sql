-- generated from spec/target.yml: middle tier -> Sources
{{ config(alias='Sources') }}
SELECT
    TRY_CAST(CAST(ROW_NUMBER() OVER (ORDER BY s.source NULLS FIRST) AS VARCHAR) AS VARCHAR) AS ID,
    TRY_CAST(UPPER(LEFT(CAST(s.source AS TEXT), 1)) || SUBSTRING(s.source, 2, 50) AS VARCHAR) AS Name
FROM (SELECT DISTINCT source FROM {{ ref('mid_candidates') }} WHERE NOT source IS NULL) AS s
