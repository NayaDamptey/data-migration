USE Migration_Staging;

TRUNCATE TABLE mid.Placements;

INSERT INTO mid.Placements (
    placement_id,
    candidate_id,
    job_id,
    start_date,
    end_date,
    salary,
    fee,
    placement_type,
    owner_user_id
)
SELECT
    h.Req_HiredID              AS placement_id,
    h.Invoiced_PersonID        AS candidate_id,
    h.Req_ID                   AS job_id,
    CAST(h.StartDate AS DATE)  AS start_date,
    CAST(h.EndDate AS DATE)    AS end_date,
    NULL                       AS salary,
    h.FeeValue                 AS fee,
    LOWER(h.Worktype)          AS placement_type,
    h.Owner_ID                 AS owner_user_id
FROM Cobaltdesk_Legacy.dbo.Req_Hired h
WHERE (h.Pipeline_Stage = 'Placed');
