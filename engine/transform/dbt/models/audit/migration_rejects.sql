SELECT 'Contact' AS target_table, CAST(ct.contact_id AS VARCHAR) AS source_key, 'rejected' AS action, 'contact linked to no company (orphan)' AS reason
FROM {{ ref('mid_contacts') }} AS ct

WHERE NOT (NOT ct.client_id IS NULL AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = ct.client_id))
UNION ALL
SELECT 'Position' AS target_table, CAST(TRY_CAST(j.job_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'job linked to no company' AS reason
FROM {{ ref('mid_jobs') }} AS j

WHERE NOT (NOT j.client_id IS NULL AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = j.client_id))
UNION ALL
SELECT 'Placements' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no job, or to a job with no company' AS reason
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT 'Placements' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
UNION ALL
SELECT 'Placements' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'flagged' AS action, 'live placement on a deleted job' AS reason
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
  AND NOT (NOT EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND x.status = 'deleted'))
UNION ALL
SELECT 'Placements' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'flagged' AS action, 'live placement on a deleted company' AS reason
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
  AND (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
  AND NOT (NOT EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = j.client_id AND x.status = 'deleted'))
UNION ALL
SELECT 'Notes' AS target_table, CAST(TRY_CAST(n.note_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no migrated record (orphan)' AS reason
FROM {{ ref('mid_notes') }} AS n

WHERE NOT ((n.entity_type = 'candidate' AND EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = n.entity_id)) OR (n.entity_type = 'contact' AND EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = n.entity_id AND NOT x.client_id IS NULL)) OR (n.entity_type = 'job' AND EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = n.entity_id AND NOT x.client_id IS NULL)) OR (n.entity_type = 'client' AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = n.entity_id)))
UNION ALL
SELECT 'TaskItem' AS target_table, CAST(TRY_CAST(a.activity_id AS INT) * 10 + 1 AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_activities') }} AS a

WHERE (NOT a.candidate_id IS NULL)
  AND NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = a.candidate_id))
UNION ALL
SELECT 'TaskItem' AS target_table, CAST(TRY_CAST(a.activity_id AS INT) * 10 + 2 AS VARCHAR) AS source_key, 'rejected' AS action, 'contact not migrated' AS reason
FROM {{ ref('mid_activities') }} AS a

WHERE (NOT a.contact_id IS NULL)
  AND NOT (EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = a.contact_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT 'TaskItem' AS target_table, CAST(1000000 + TRY_CAST(iv.interview_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_interviews') }} AS iv

WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = iv.candidate_id))
UNION ALL
SELECT 'Attachments' AS target_table, CAST(CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no migrated record (orphan)' AS reason
FROM {{ ref('mid_documents') }} AS d

WHERE NOT ((d.entity_type = 'candidate' AND EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = d.entity_id)) OR (d.entity_type = 'contact' AND EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'job' AND EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'client' AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = d.entity_id)))
UNION ALL
SELECT 'Position_Details' AS target_table, CAST(TRY_CAST(j.job_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'job linked to no company' AS reason
FROM {{ ref('mid_jobs') }} AS j

WHERE NOT (NOT j.client_id IS NULL)
UNION ALL
SELECT 'Position_Applicant' AS target_table, CAST(TRY_CAST(a.application_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no job, or to a job with no company' AS reason
FROM {{ ref('mid_applications') }} AS a

WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = a.job_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT 'Position_Applicant' AS target_table, CAST(TRY_CAST(a.application_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_applications') }} AS a

WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = a.candidate_id))
UNION ALL
SELECT 'Shortlist' AS target_table, CAST(TRY_CAST(a.application_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no job, or to a job with no company' AS reason
FROM {{ ref('mid_applications') }} AS a

WHERE (a.stage IN ('screening', 'interview', 'offer'))
  AND NOT (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = a.job_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT 'Shortlist' AS target_table, CAST(TRY_CAST(a.application_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_applications') }} AS a

WHERE (a.stage IN ('screening', 'interview', 'offer'))
  AND NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = a.candidate_id))
UNION ALL
SELECT 'Offer' AS target_table, CAST(TRY_CAST(a.application_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no job, or to a job with no company' AS reason
FROM {{ ref('mid_applications') }} AS a

WHERE (a.stage IN ('offer', 'placed'))
  AND NOT (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = a.job_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT 'Offer' AS target_table, CAST(TRY_CAST(a.application_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_applications') }} AS a

WHERE (a.stage IN ('offer', 'placed'))
  AND NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = a.candidate_id))
UNION ALL
SELECT 'Deal' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no job, or to a job with no company' AS reason
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT 'Deal' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_placements') }} AS pl
LEFT JOIN {{ ref('mid_jobs') }} AS j ON j.job_id = pl.job_id
WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
UNION ALL
SELECT 'Deal_Stage' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no job, or to a job with no company' AS reason
FROM {{ ref('mid_placements') }} AS pl

WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = pl.job_id AND NOT x.client_id IS NULL))
UNION ALL
SELECT 'Deal_Stage' AS target_table, CAST(TRY_CAST(pl.placement_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_placements') }} AS pl

WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = pl.candidate_id))
UNION ALL
SELECT 'Work_History' AS target_table, CAST(TRY_CAST(w.history_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_work_history') }} AS w

WHERE (w.deleted = 0)
  AND NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = w.candidate_id))
UNION ALL
SELECT 'References' AS target_table, CAST(r.reference_id AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_references') }} AS r

WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = r.candidate_id))
UNION ALL
SELECT 'Employment_Details' AS target_table, CAST(TRY_CAST(cp.profile_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_candidate_profiles') }} AS cp
LEFT JOIN {{ ref('mid_consents') }} AS c ON c.person_id = cp.candidate_id
WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = cp.candidate_id))
UNION ALL
SELECT 'TimesheetActivity' AS target_table, CAST(TRY_CAST(l.line_id AS INT) AS VARCHAR) AS source_key, 'rejected' AS action, 'not a migrated candidate (a contact, a removed duplicate or missing)' AS reason
FROM {{ ref('mid_timesheet_lines') }} AS l
LEFT JOIN {{ ref('mid_timesheets') }} AS t ON t.timesheet_id = l.timesheet_id
WHERE NOT (EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = l.candidate_id))
UNION ALL
SELECT 'ApplicantAttachment' AS target_table, CAST(CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no migrated record (orphan)' AS reason
FROM {{ ref('mid_documents') }} AS d

WHERE (d.entity_type = 'candidate')
  AND NOT ((d.entity_type = 'candidate' AND EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = d.entity_id)) OR (d.entity_type = 'contact' AND EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'job' AND EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'client' AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = d.entity_id)))
UNION ALL
SELECT 'ContactAttachment' AS target_table, CAST(CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no migrated record (orphan)' AS reason
FROM {{ ref('mid_documents') }} AS d

WHERE (d.entity_type = 'contact')
  AND NOT ((d.entity_type = 'candidate' AND EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = d.entity_id)) OR (d.entity_type = 'contact' AND EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'job' AND EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'client' AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = d.entity_id)))
UNION ALL
SELECT 'PositionAttachment' AS target_table, CAST(CASE WHEN d.document_id LIKE 'CV%' THEN 100000 + TRY_CAST(SUBSTRING(d.document_id, 3, 20) AS INT) ELSE TRY_CAST(SUBSTRING(d.document_id, 2, 20) AS INT) END AS VARCHAR) AS source_key, 'rejected' AS action, 'linked to no migrated record (orphan)' AS reason
FROM {{ ref('mid_documents') }} AS d

WHERE (d.entity_type = 'job')
  AND NOT ((d.entity_type = 'candidate' AND EXISTS(SELECT 1 FROM {{ ref('mid_candidates') }} AS x WHERE x.candidate_id = d.entity_id)) OR (d.entity_type = 'contact' AND EXISTS(SELECT 1 FROM {{ ref('mid_contacts') }} AS x WHERE x.contact_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'job' AND EXISTS(SELECT 1 FROM {{ ref('mid_jobs') }} AS x WHERE x.job_id = d.entity_id AND NOT x.client_id IS NULL)) OR (d.entity_type = 'client' AND EXISTS(SELECT 1 FROM {{ ref('mid_clients') }} AS x WHERE x.client_id = d.entity_id)))
