-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(er.EmpRef_ID AS VARCHAR) AS reference_id,
    TRY_CAST(ep.Person_ID AS VARCHAR) AS candidate_id,
    TRY_CAST(rf.Fullname AS VARCHAR) AS full_name,
    TRY_CAST(rf.Job_Title AS VARCHAR) AS job_title,
    TRY_CAST(rf.Company AS VARCHAR) AS company,
    TRY_CAST(er.Relationship AS VARCHAR) AS relationship,
    TRY_CAST(rf.email AS VARCHAR) AS email,
    TRY_CAST(rf.Telephone AS VARCHAR) AS phone,
    TRY_CAST(er.Status AS VARCHAR) AS status,
    TRY_CAST(er.Reference AS VARCHAR) AS reference_text,
    TRY_CAST(er.CreatedAt AS TIMESTAMP) AS created_at,
    TRY_CAST(er.UpdatedAt AS TIMESTAMP) AS updated_at
FROM {{ source('legacy', 'EmpRef') }} AS er
JOIN {{ source('legacy', 'Referees') }} AS rf ON rf.Referee_ID = er.Ref_ID
JOIN {{ source('legacy', 'Emp_Profile') }} AS ep ON ep.Emp_No = er.EmpNo
