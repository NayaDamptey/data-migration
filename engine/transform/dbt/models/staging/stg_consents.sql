-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(g.GDPR_ConsentID AS VARCHAR) AS consent_id,
    TRY_CAST(g.Person_ID AS VARCHAR) AS person_id,
    TRY_CAST(g.Email AS BOOLEAN) AS email_ok,
    TRY_CAST(g.Phone AS BOOLEAN) AS phone_ok,
    TRY_CAST(g.Text AS BOOLEAN) AS text_ok,
    TRY_CAST(g.CreatedBy AS VARCHAR) AS added_by,
    TRY_CAST(g.CreatedAt AS TIMESTAMP) AS created_at,
    TRY_CAST(g.UpdatedAt AS TIMESTAMP) AS updated_at
FROM {{ source('legacy', 'GDPR_Consent') }} AS g
