-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(ep.Emp_ProfileID AS VARCHAR) AS profile_id,
    TRY_CAST(ep.Person_ID AS VARCHAR) AS candidate_id,
    TRY_CAST(ep.Emp_TypeDescription AS VARCHAR) AS employment_type,
    TRY_CAST(ep.Profile_Notes AS VARCHAR) AS notes,
    TRY_CAST(ep.BankDetails AS VARCHAR) AS bank,
    TRY_CAST(ep.SortCode AS VARCHAR) AS sort_code,
    TRY_CAST(ep.CreatedBy AS VARCHAR) AS added_by,
    TRY_CAST(ep.CreatedAt AS TIMESTAMP) AS created_at,
    TRY_CAST(ep.UpdatedAt AS TIMESTAMP) AS updated_at
FROM {{ source('legacy', 'Emp_Profile') }} AS ep
