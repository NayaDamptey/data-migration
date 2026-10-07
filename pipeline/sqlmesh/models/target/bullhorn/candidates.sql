-- Target: candidates in a Bullhorn-style schema.
-- Column names are illustrative; confirm against the real target spec.
MODEL (
  name target_bullhorn.candidates,
  kind FULL,
  grain external_id,
  audits (
    not_null(columns := (external_id, first_name, last_name))
  )
);

SELECT
  candidate_id      AS external_id,
  first_name,
  last_name,
  email,
  mobile,
  current_job_title AS occupation,
  address_line_1    AS "address.address1",
  city              AS "address.city",
  postcode          AS "address.zip",
  source,
  owner_user_id     AS owner_id,
  created_at        AS date_added
FROM canonical.candidates
-- Rows failing the target's required-contact rule go to a rejects file instead
WHERE coalesce(email, mobile) IS NOT NULL
