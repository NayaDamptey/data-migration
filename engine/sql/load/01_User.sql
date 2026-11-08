USE RecruitPlatform_Target;

TRUNCATE TABLE dbo.[User];

INSERT INTO dbo.[User] (
    UserID,
    Loginname,
    FullName,
    Email,
    Role,
    Status,
    IsDeleted,
    IsArchived
)
SELECT
    u.user_id                                                    AS UserID,
    LEFT(u.email, CHARINDEX('@', u.email + '@') - 1)             AS Loginname,
    CONCAT_WS(' ', u.first_name, u.last_name)                    AS FullName,
    u.email                                                      AS Email,
    u.role                                                       AS Role,
    CASE WHEN u.is_active = 1 THEN 'Active' ELSE 'Inactive' END  AS Status,
    0                                                            AS IsDeleted,
    0                                                            AS IsArchived
FROM Migration_Staging.mid.Users u;
