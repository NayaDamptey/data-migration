-- Canonical candidates.
-- In the finished platform this file is GENERATED from the approved mapping
-- spec (mappings/*.yaml). This hand-written version shows the target shape
-- for the Tracker example spec.
MODEL (
  name canonical.candidates,
  kind FULL,
  grain candidate_id,
  audits (
    not_null(columns := (candidate_id, first_name, last_name)),
    unique_values(columns := (candidate_id))
  )
);

SELECT
  CandidateID                                        AS candidate_id,
  trim(Forename)                                     AS first_name,
  trim(Surname)                                      AS last_name,
  lower(nullif(trim(Email1), ''))                    AS email,
  CASE
    WHEN MobileTel IS NULL OR trim(MobileTel) = '' THEN NULL
    WHEN regexp_replace(MobileTel, '[^0-9]', '', 'g') LIKE '0%'
      THEN '+44' || substr(regexp_replace(MobileTel, '[^0-9]', '', 'g'), 2)
    ELSE regexp_replace(MobileTel, '[^0-9+]', '', 'g')
  END                                                AS mobile,
  CurrentPosition                                    AS current_job_title,
  trim(split_part(Address, ',', 1))                  AS address_line_1,   -- needs review
  trim(split_part(Address, ',', -1))                 AS city,             -- needs review
  upper(trim(PostCode))                              AS postcode,
  CASE lower(trim(HowHeard))
    WHEN 'totaljobs'  THEN 'job_board'
    WHEN 'tj'         THEN 'job_board'
    WHEN 'total jobs' THEN 'job_board'
    WHEN 'referral'   THEN 'referral'
    WHEN 'linkedin'   THEN 'linkedin'
    ELSE NULL
  END                                                AS source,
  ConsultantID                                       AS owner_user_id,
  strptime(DateRegistered, '%d/%m/%Y %H:%M')         AS created_at
FROM raw.candidate
