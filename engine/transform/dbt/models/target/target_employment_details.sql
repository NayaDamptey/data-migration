{{ config(alias='Employment_Details') }}
SELECT
    TRY_CAST(TRY_CAST(cp.profile_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(cp.employment_type AS VARCHAR) AS Employment_Type,
    TRY_CAST(cp.candidate_id AS VARCHAR) AS ApplicantID,
    TRY_CAST(c.email_ok AS BOOLEAN) AS MarketingEmail,
    TRY_CAST(c.phone_ok AS BOOLEAN) AS MarketingPhone,
    TRY_CAST(c.text_ok AS BOOLEAN) AS MarketingText,
    TRY_CAST(LEFT(CAST(cp.bank AS TEXT), 50) AS VARCHAR) AS Bank,
    TRY_CAST(cp.sort_code AS VARCHAR) AS SortCode,
    TRY_CAST(cp.notes AS VARCHAR) AS Notes,
    TRY_CAST(cp.added_by AS VARCHAR) AS AddedBy,
    TRY_CAST(cp.created_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(cp.updated_at AS TIMESTAMP) AS UpdatedAt
FROM {{ ref('mid_candidate_profiles') }} AS cp
LEFT JOIN {{ ref('mid_consents') }} AS c ON c.person_id = cp.candidate_id
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = cp.candidate_id))
