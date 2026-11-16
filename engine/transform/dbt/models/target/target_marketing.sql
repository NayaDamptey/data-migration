{{ config(alias='Marketing') }}
SELECT
    TRY_CAST(TRY_CAST(c.consent_id AS INT) AS INTEGER) AS ID,
    TRY_CAST(c.person_id AS VARCHAR) AS ApplicantID,
    TRY_CAST(CASE WHEN c.email_ok = 1 THEN 'Yes' ELSE 'No' END AS VARCHAR) AS Email,
    TRY_CAST(CASE WHEN c.phone_ok = 1 THEN 'Yes' ELSE 'No' END AS VARCHAR) AS Phone,
    TRY_CAST(CASE WHEN c.text_ok = 1 THEN 'Yes' ELSE 'No' END AS VARCHAR) AS Text,
    TRY_CAST(1 AS BOOLEAN) AS GDPRConsent,
    TRY_CAST(CASE WHEN c.email_ok = 1 OR c.phone_ok = 1 OR c.text_ok = 1 THEN 1 ELSE 0 END AS BOOLEAN) AS OptIn,
    TRY_CAST(CASE WHEN c.email_ok = 0 AND c.phone_ok = 0 AND c.text_ok = 0 THEN 1 ELSE 0 END AS BOOLEAN) AS OptOut,
    TRY_CAST(c.created_at AS TIMESTAMP) AS AddedAt,
    TRY_CAST(c.updated_at AS TIMESTAMP) AS UpdatedAt,
    TRY_CAST(c.added_by AS VARCHAR) AS AddedBy
FROM {{ ref('mid_consents') }} AS c
WHERE (c.person_id IN (SELECT candidate_id FROM {{ ref('mid_candidates') }}))
