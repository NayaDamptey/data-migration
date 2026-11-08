USE Migration_Staging;

TRUNCATE TABLE mid.Departments;

INSERT INTO mid.Departments (
    department_id,
    name,
    deleted,
    created_at,
    updated_at
)
SELECT
    d.DepartmentID  AS department_id,
    d.Name          AS name,
    d.Deleted       AS deleted,
    d.CreatedAt     AS created_at,
    d.UpdatedAt     AS updated_at
FROM Cobaltdesk_Legacy.dbo.Departments d;
