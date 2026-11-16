-- generated from spec/target.yml: middle tier -> Applicant
{{ config(alias='Applicant') }}
SELECT
    TRY_CAST(ca.candidate_id AS VARCHAR) AS ApplicantID,
    TRY_CAST(ca.first_name AS VARCHAR) AS FirstName,
    TRY_CAST(ca.last_name AS VARCHAR) AS LastName,
    TRY_CAST(CASE WHEN NOT ca.email IS NULL THEN TRY_CAST(ca.candidate_id AS INT) * 10 + 1 END AS INTEGER) AS ApplicantCommsID,
    TRY_CAST(ca.status AS VARCHAR) AS Status,
    TRY_CAST(LEFT(CAST(ca.current_job_title AS TEXT), 50) AS VARCHAR) AS JobTitle,
    TRY_CAST(ca.source AS VARCHAR) AS Source,
    TRY_CAST(1 AS BOOLEAN) AS Active,
    TRY_CAST(ca.owner_user_id AS VARCHAR) AS ApplicantOwner,
    TRY_CAST(ca.owner_user_id AS VARCHAR) AS AddedBy,
    TRY_CAST(ca.created_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(0 AS BOOLEAN) AS Deleted
FROM {{ ref('mid_candidates') }} AS ca
