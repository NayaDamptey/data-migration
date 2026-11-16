-- generated: the middle tier for Candidates, with the reviewer's duplicate merges applied
{{ config(alias='Candidates') }}
SELECT
    s.candidate_id,
    s.first_name,
    s.last_name,
    s.email,
    s.mobile,
    s.phone,
    s.current_job_title,
    s.current_employer,
    s.address_line_1,
    s.address_line_2,
    s.city,
    s.postcode,
    s.country,
    s.source,
    s.status,
    s.linkedin_url,
    s.owner_user_id,
    s.created_at
FROM {{ ref('stg_candidates') }} s
WHERE s.candidate_id NOT IN (SELECT duplicate FROM {{ ref('merges') }} WHERE kind = 'candidate')
