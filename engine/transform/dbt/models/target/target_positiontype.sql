-- generated from spec/target.yml: middle tier -> PositionType
{{ config(alias='PositionType') }}
SELECT
    TRY_CAST(ROW_NUMBER() OVER (ORDER BY j.employment_type NULLS FIRST) AS INTEGER) AS ID,
    TRY_CAST(UPPER(LEFT(CAST(j.employment_type AS TEXT), 1)) || SUBSTRING(j.employment_type, 2, 50) AS VARCHAR) AS Type
FROM (SELECT DISTINCT employment_type FROM {{ ref('mid_jobs') }} WHERE NOT employment_type IS NULL) AS j
