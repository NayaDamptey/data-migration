-- generated: the middle tier for Candidate profiles, with the reviewer's duplicate merges applied
{{ config(alias='CandidateProfiles') }}
SELECT
    s.profile_id,
    COALESCE((SELECT m.survivor FROM {{ ref('merges') }} m WHERE m.kind = 'candidate' AND m.duplicate = s.candidate_id), s.candidate_id) AS candidate_id,
    s.employment_type,
    s.notes,
    s.bank,
    s.sort_code,
    s.added_by,
    s.created_at,
    s.updated_at
FROM {{ ref('stg_candidate_profiles') }} s
