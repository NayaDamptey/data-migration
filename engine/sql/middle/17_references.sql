USE Migration_Staging;

TRUNCATE TABLE mid.[References];

INSERT INTO mid.[References] (
    reference_id,
    candidate_id,
    full_name,
    job_title,
    company,
    relationship,
    email,
    phone,
    status,
    reference_text,
    created_at,
    updated_at
)
SELECT
    er.EmpRef_ID     AS reference_id,
    ep.Person_ID     AS candidate_id,
    rf.Fullname      AS full_name,
    rf.Job_Title     AS job_title,
    rf.Company       AS company,
    er.Relationship  AS relationship,
    rf.email         AS email,
    rf.Telephone     AS phone,
    er.Status        AS status,
    er.Reference     AS reference_text,
    er.CreatedAt     AS created_at,
    er.UpdatedAt     AS updated_at
FROM Cobaltdesk_Legacy.dbo.EmpRef er
JOIN Cobaltdesk_Legacy.dbo.Referees rf ON rf.Referee_ID = er.Ref_ID
JOIN Cobaltdesk_Legacy.dbo.Emp_Profile ep ON ep.Emp_No = er.EmpNo;
