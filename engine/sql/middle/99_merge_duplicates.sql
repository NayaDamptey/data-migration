USE Migration_Staging;

-- Candidates: 10005 merged into 370
UPDATE mid.Placements SET candidate_id = N'370' WHERE candidate_id = N'10005';
UPDATE mid.Notes SET entity_id = N'370' WHERE entity_type = 'candidate' AND entity_id = N'10005';
UPDATE mid.Histories SET entity_id = N'370' WHERE entity_type = 'candidate' AND entity_id = N'10005';
UPDATE mid.Activities SET candidate_id = N'370' WHERE candidate_id = N'10005';
UPDATE mid.Documents SET entity_id = N'370' WHERE entity_type = 'candidate' AND entity_id = N'10005';
UPDATE mid.Applications SET candidate_id = N'370' WHERE candidate_id = N'10005';
UPDATE mid.Interviews SET candidate_id = N'370' WHERE candidate_id = N'10005';
UPDATE mid.WorkHistory SET candidate_id = N'370' WHERE candidate_id = N'10005';
UPDATE mid.[References] SET candidate_id = N'370' WHERE candidate_id = N'10005';
UPDATE mid.CandidateProfiles SET candidate_id = N'370' WHERE candidate_id = N'10005';
UPDATE mid.TimesheetLines SET candidate_id = N'370' WHERE candidate_id = N'10005';
DELETE FROM mid.Consents WHERE person_id = N'10005' AND EXISTS (SELECT 1 FROM mid.Consents WHERE person_id = N'370');
UPDATE mid.Consents SET person_id = N'370' WHERE person_id = N'10005';
DELETE FROM mid.Candidates WHERE candidate_id = N'10005';

-- Candidates: 10011 merged into 446
UPDATE mid.Placements SET candidate_id = N'446' WHERE candidate_id = N'10011';
UPDATE mid.Notes SET entity_id = N'446' WHERE entity_type = 'candidate' AND entity_id = N'10011';
UPDATE mid.Histories SET entity_id = N'446' WHERE entity_type = 'candidate' AND entity_id = N'10011';
UPDATE mid.Activities SET candidate_id = N'446' WHERE candidate_id = N'10011';
UPDATE mid.Documents SET entity_id = N'446' WHERE entity_type = 'candidate' AND entity_id = N'10011';
UPDATE mid.Applications SET candidate_id = N'446' WHERE candidate_id = N'10011';
UPDATE mid.Interviews SET candidate_id = N'446' WHERE candidate_id = N'10011';
UPDATE mid.WorkHistory SET candidate_id = N'446' WHERE candidate_id = N'10011';
UPDATE mid.[References] SET candidate_id = N'446' WHERE candidate_id = N'10011';
UPDATE mid.CandidateProfiles SET candidate_id = N'446' WHERE candidate_id = N'10011';
UPDATE mid.TimesheetLines SET candidate_id = N'446' WHERE candidate_id = N'10011';
DELETE FROM mid.Consents WHERE person_id = N'10011' AND EXISTS (SELECT 1 FROM mid.Consents WHERE person_id = N'446');
UPDATE mid.Consents SET person_id = N'446' WHERE person_id = N'10011';
DELETE FROM mid.Candidates WHERE candidate_id = N'10011';

-- Contacts: 301 merged into 279
UPDATE mid.Jobs SET contact_id = N'279' WHERE contact_id = N'301';
UPDATE mid.Notes SET entity_id = N'279' WHERE entity_type = 'contact' AND entity_id = N'301';
UPDATE mid.Histories SET entity_id = N'279' WHERE entity_type = 'contact' AND entity_id = N'301';
UPDATE mid.Activities SET contact_id = N'279' WHERE contact_id = N'301';
UPDATE mid.Documents SET entity_id = N'279' WHERE entity_type = 'contact' AND entity_id = N'301';
UPDATE mid.Applications SET contact_id = N'279' WHERE contact_id = N'301';
UPDATE mid.Leads SET contact_id = N'279' WHERE contact_id = N'301';
DELETE FROM mid.Contacts WHERE contact_id = N'301';
