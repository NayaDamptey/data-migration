USE Migration_Staging;

TRUNCATE TABLE mid.CandidateProfiles;

INSERT INTO mid.CandidateProfiles (
    profile_id,
    candidate_id,
    employment_type,
    notes,
    bank,
    sort_code,
    added_by,
    created_at,
    updated_at
)
SELECT
    ep.Emp_ProfileID        AS profile_id,
    ep.Person_ID            AS candidate_id,
    ep.Emp_TypeDescription  AS employment_type,
    ep.Profile_Notes        AS notes,
    ep.BankDetails          AS bank,
    ep.SortCode             AS sort_code,
    ep.CreatedBy            AS added_by,
    ep.CreatedAt            AS created_at,
    ep.UpdatedAt            AS updated_at
FROM Cobaltdesk_Legacy.dbo.Emp_Profile ep;
