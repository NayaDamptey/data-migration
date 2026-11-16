{{ config(alias='Consents') }}
SELECT
    s.consent_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.person_id), s.person_id) AS person_id,
    s.email_ok,
    s.phone_ok,
    s.text_ok,
    s.added_by,
    s.created_at,
    s.updated_at
FROM {{ ref('stg_consents') }} s
QUALIFY ROW_NUMBER() OVER (PARTITION BY COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.person_id), s.person_id) ORDER BY CASE WHEN s.person_id IN (SELECT survivor FROM {{ ref('merges') }}) THEN 0 ELSE 1 END, s.consent_id) = 1
