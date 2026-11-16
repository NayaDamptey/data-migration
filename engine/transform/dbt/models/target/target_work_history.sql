{{ config(alias='Work_History') }}
SELECT
    TRY_CAST(TRY_CAST(w.history_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(w.candidate_id AS VARCHAR) AS ApplicationID,
    TRY_CAST(LEFT(CAST(w.employer AS TEXT), 50) AS VARCHAR) AS CompanyName,
    TRY_CAST(LEFT(CAST(w.job_title AS TEXT), 50) AS VARCHAR) AS PositionTitle,
    TRY_CAST(w.start_date AS DATE) AS StartDate,
    TRY_CAST(w.end_date AS DATE) AS EndDate
FROM {{ ref('mid_work_history') }} AS w
WHERE (w.deleted = 0)
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = w.candidate_id))
