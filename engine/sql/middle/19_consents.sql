USE Migration_Staging;

TRUNCATE TABLE mid.Consents;

INSERT INTO mid.Consents (
    consent_id,
    person_id,
    email_ok,
    phone_ok,
    text_ok,
    added_by,
    created_at,
    updated_at
)
SELECT
    g.GDPR_ConsentID  AS consent_id,
    g.Person_ID       AS person_id,
    g.Email           AS email_ok,
    g.Phone           AS phone_ok,
    g.Text            AS text_ok,
    g.CreatedBy       AS added_by,
    g.CreatedAt       AS created_at,
    g.UpdatedAt       AS updated_at
FROM Cobaltdesk_Legacy.dbo.GDPR_Consent g;
