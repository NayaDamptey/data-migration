USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Marketing;

INSERT INTO dbo.Marketing (
    ID,
    ApplicantID,
    Email,
    Phone,
    Text,
    GDPRConsent,
    OptIn,
    OptOut,
    AddedAt,
    UpdatedAt,
    AddedBy
)
SELECT
    TRY_CAST(c.consent_id AS INT)                                                    AS ID,
    c.person_id                                                                      AS ApplicantID,
    CASE WHEN c.email_ok = 1 THEN 'Yes' ELSE 'No' END                                AS Email,
    CASE WHEN c.phone_ok = 1 THEN 'Yes' ELSE 'No' END                                AS Phone,
    CASE WHEN c.text_ok = 1 THEN 'Yes' ELSE 'No' END                                 AS Text,
    1                                                                                AS GDPRConsent,
    CASE WHEN c.email_ok = 1 OR c.phone_ok = 1 OR c.text_ok = 1 THEN 1 ELSE 0 END    AS OptIn,
    CASE WHEN c.email_ok = 0 AND c.phone_ok = 0 AND c.text_ok = 0 THEN 1 ELSE 0 END  AS OptOut,
    c.created_at                                                                     AS AddedAt,
    c.updated_at                                                                     AS UpdatedAt,
    c.added_by                                                                       AS AddedBy
FROM Migration_Staging.mid.Consents c
WHERE (c.person_id IN (SELECT candidate_id FROM Migration_Staging.mid.Candidates));
