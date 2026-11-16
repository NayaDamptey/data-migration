-- generated from spec/middle.yml: source -> canonical shape
SELECT
    TRY_CAST(d.DepartmentID AS VARCHAR) AS department_id,
    TRY_CAST(d.Name AS VARCHAR) AS name,
    TRY_CAST(d.Deleted AS BOOLEAN) AS deleted,
    TRY_CAST(d.CreatedAt AS TIMESTAMP) AS created_at,
    TRY_CAST(d.UpdatedAt AS TIMESTAMP) AS updated_at
FROM {{ source('legacy', 'Departments') }} AS d
