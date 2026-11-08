USE Migration_Staging;

TRUNCATE TABLE mid.Users;

INSERT INTO mid.Users (
    user_id,
    first_name,
    last_name,
    email,
    role,
    office,
    is_active
)
SELECT
    r.RecruiterID                                                                        AS user_id,
    LEFT(r.Fullname, CHARINDEX(' ', r.Fullname + ' ') - 1)                               AS first_name,
    NULLIF(LTRIM(SUBSTRING(r.Fullname, CHARINDEX(' ', r.Fullname + ' ') + 1, 200)), '')  AS last_name,
    r.email                                                                              AS email,
    LOWER(ro.Description)                                                                AS role,
    NULL                                                                                 AS office,
    1                                                                                    AS is_active
FROM Cobaltdesk_Legacy.dbo.Recruiter r
LEFT JOIN Cobaltdesk_Legacy.dbo.Roles ro ON ro.Role_ID = r.Role_ID;
