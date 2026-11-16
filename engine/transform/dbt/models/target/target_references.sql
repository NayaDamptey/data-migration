{{ config(alias='References') }}
SELECT
    TRY_CAST(r.reference_id AS VARCHAR) AS ID,
    TRY_CAST(r.candidate_id AS VARCHAR) AS ApplicantID,
    TRY_CAST(r.full_name AS VARCHAR) AS Fullname,
    TRY_CAST(LEFT(CAST(r.job_title AS TEXT), 50) AS VARCHAR) AS PositionTitle,
    TRY_CAST(LEFT(CAST(r.company AS TEXT), 50) AS VARCHAR) AS CompanyName,
    TRY_CAST(r.relationship AS VARCHAR) AS Relationship,
    TRY_CAST(LEFT(CAST(r.email AS TEXT), 50) AS VARCHAR) AS Email,
    TRY_CAST(r.phone AS VARCHAR) AS PhoneContact,
    TRY_CAST('Employment' AS VARCHAR) AS ReferenceType,
    TRY_CAST(LEFT(CAST(r.status AS TEXT), 50) AS VARCHAR) AS Notes,
    TRY_CAST(CASE WHEN r.status = 'Received' THEN r.updated_at END AS TIMESTAMP) AS VerifiedAt,
    TRY_CAST(r.created_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(r.updated_at AS TIMESTAMP) AS UpdatedAt
FROM {{ ref('mid_references') }} AS r
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = r.candidate_id))
