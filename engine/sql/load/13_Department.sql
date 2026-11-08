USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.Department;

INSERT INTO dbo.Department (
    ID,
    Name,
    AddedAt,
    UpdatedAt
)
SELECT
    TRY_CAST(d.department_id AS INT)  AS ID,
    d.name                            AS Name,
    d.created_at                      AS AddedAt,
    d.updated_at                      AS UpdatedAt
FROM Migration_Staging.mid.Departments d;
