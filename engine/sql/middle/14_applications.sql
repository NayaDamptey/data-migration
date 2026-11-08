USE Migration_Staging;

TRUNCATE TABLE mid.Applications;

INSERT INTO mid.Applications (
    application_id,
    candidate_id,
    job_id,
    client_id,
    contact_id,
    stage,
    employment_type,
    start_date,
    end_date,
    fee,
    source,
    owner_user_id,
    deleted,
    applied_at
)
SELECT
    h.Req_HiredID              AS application_id,
    h.Invoiced_PersonID        AS candidate_id,
    h.Req_ID                   AS job_id,
    h.Account_ID               AS client_id,
    h.Associate_ID             AS contact_id,
    LOWER(h.Pipeline_Stage)    AS stage,
    LOWER(h.Worktype)          AS employment_type,
    CAST(h.StartDate AS DATE)  AS start_date,
    CAST(h.EndDate AS DATE)    AS end_date,
    h.FeeValue                 AS fee,
    LOWER(h.Source)            AS source,
    h.Owner_ID                 AS owner_user_id,
    h.Deleted                  AS deleted,
    h.CreatedAt                AS applied_at
FROM Cobaltdesk_Legacy.dbo.Req_Hired h;
