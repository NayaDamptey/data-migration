// Prototype data. Field lists follow canonical/model.yaml; source columns and
// samples follow mappings/tracker.example.yaml and samples/tracker/*.csv.
// Replace with API calls (lib/api.ts) once the backend routes are filled in.
import type { UploadItem } from "./upload";

export const SOURCE_SYSTEMS = ["Tracker", "JobAdder", "Bullhorn", "Seven20", "Vincere", "Other"];
export const SOURCE_FORMATS = ["CSV files", "Database backup", "JSON", "API connection"];
export const TARGET_SYSTEMS = ["Bullhorn", "JobAdder", "Vincere", "Seven20", "Tracker", "Custom schema"];
export const TARGET_DATABASES = ["PostgreSQL", "MySQL", "SQL Server (T-SQL)"];
export const OUTPUTS = ["CSV files", "SQL inserts", "API push"];

export type FieldStatus = "mapped" | "review" | "unmapped";

export type CanonicalField = {
  name: string;
  type: string;
  required?: boolean;
  from: string | null;
  transform?: string;
  sample: string;
  confidence: number;
  status: FieldStatus;
  note?: string;
};

export type Entity = {
  key: string;
  label: string;
  description: string;
  sourceTable: string | null;
  rows: number;
  fields: CanonicalField[];
};

type Row = [name: string, type: string, from: string | null, sample: string, confidence: number, status: FieldStatus, extra?: Partial<CanonicalField>];

const f = (rows: Row[]): CanonicalField[] =>
  rows.map(([name, type, from, sample, confidence, status, extra]) => ({ name, type, from, sample, confidence, status, ...extra }));

export const ENTITIES: Entity[] = [
  {
    key: "users", label: "Users", description: "Recruiters, managers and admins who own records.", sourceTable: "USER", rows: 14,
    fields: f([
      ["user_id", "id", "USER.UserID", "U-0012", 0.99, "mapped", { required: true }],
      ["first_name", "text", "USER.Forename", "Priya", 0.98, "mapped"],
      ["last_name", "text", "USER.Surname", "Shah", 0.98, "mapped"],
      ["email", "email", "USER.EmailAddress", "p.shah@spencerthomas.example", 0.97, "mapped", { required: true }],
      ["role", "enum", "USER.Role", "Consultant → recruiter", 0.81, "review", { transform: "value_map", note: "“Consultant” mapped to recruiter. Check “Resourcer”." }],
      ["office", "text", "USER.Branch", "Leeds", 0.93, "mapped"],
      ["is_active", "boolean", "USER.Disabled", "0 → true", 0.88, "mapped", { transform: "invert_flag" }],
    ]),
  },
  {
    key: "clients", label: "Clients", description: "Companies the agency recruits for.", sourceTable: "COMPANY", rows: 312,
    fields: f([
      ["client_id", "id", "COMPANY.CompanyID", "CL-2081", 0.99, "mapped", { required: true }],
      ["company_name", "text", "COMPANY.Name", "Harlow Foods Ltd", 0.98, "mapped", { required: true }],
      ["industry", "enum", "COMPANY.Sector", "Food manufacturing", 0.84, "review", { note: "11 sector values don’t match the target list." }],
      ["website", "url", "COMPANY.Web", "harlowfoods.example", 0.95, "mapped", { transform: "add_https" }],
      ["phone", "phone", "COMPANY.Tel", "0113 496 0123", 0.94, "mapped", { transform: "normalise_uk_phone" }],
      ["address_line_1", "text", null, "—", 0, "unmapped", { note: "No street address column in COMPANY." }],
      ["address_line_2", "text", null, "—", 0, "unmapped"],
      ["city", "text", "COMPANY.Town", "Leeds", 0.95, "mapped"],
      ["postcode", "postcode", "COMPANY.PostCode", "LS4 2AZ", 0.97, "mapped", { transform: "normalise_postcode" }],
      ["country", "text", null, "United Kingdom", 0.9, "mapped", { transform: "constant", note: "Defaulted to United Kingdom." }],
      ["status", "enum", null, "—", 0, "unmapped"],
      ["owner_user_id", "ref:users", "COMPANY.OwnerID", "U-0012", 0.95, "mapped"],
      ["created_at", "datetime", null, "—", 0, "unmapped"],
    ]),
  },
  {
    key: "contacts", label: "Contacts", description: "People who work at client companies.", sourceTable: "CONTACT", rows: 1184,
    fields: f([
      ["contact_id", "id", "CONTACT.ContactID", "CT-55102", 0.99, "mapped", { required: true }],
      ["client_id", "ref:clients", "CONTACT.CompanyID", "CL-2081", 0.97, "mapped", { required: true }],
      ["first_name", "text", "CONTACT.Forename", "Helen", 0.98, "mapped"],
      ["last_name", "text", "CONTACT.Surname", "Marsh", 0.98, "mapped", { required: true }],
      ["job_title", "text", "CONTACT.Position", "HR Manager", 0.94, "mapped"],
      ["email", "email", "CONTACT.Email", "h.marsh@harlowfoods.example", 0.97, "mapped"],
      ["phone", "phone", "CONTACT.DirectLine", "0113 496 0140", 0.92, "mapped"],
      ["mobile", "phone", "CONTACT.Mobile", "07700 900771", 0.95, "mapped"],
      ["status", "enum", "CONTACT.Left", "N → active", 0.76, "review", { note: "“Left = Y” could mean left_company or inactive." }],
      ["owner_user_id", "ref:users", "CONTACT.OwnerID", "U-0014", 0.94, "mapped"],
      ["created_at", "datetime", "CONTACT.Created", "2022-01-14 10:02", 0.92, "mapped"],
    ]),
  },
  {
    key: "candidates", label: "Candidates", description: "Job seekers the agency represents.", sourceTable: "CANDIDATE", rows: 8420,
    fields: f([
      ["candidate_id", "id", "CANDIDATE.CandidateID", "C-104233", 0.99, "mapped", { required: true }],
      ["first_name", "text", "CANDIDATE.Forename", "Amara", 0.98, "mapped", { required: true }],
      ["last_name", "text", "CANDIDATE.Surname", "Okafor", 0.98, "mapped", { required: true }],
      ["email", "email", "CANDIDATE.Email1", "amara.okafor@mail.example", 0.97, "mapped"],
      ["mobile", "phone", "CANDIDATE.MobileTel", "07700 900412", 0.94, "mapped", { transform: "normalise_uk_phone" }],
      ["phone", "phone", "CANDIDATE_PHONE.Number", "0113 496 0555", 0.9, "mapped", { transform: "normalise_uk_phone", note: "Home number from CANDIDATE_PHONE (latest)." }],
      ["current_job_title", "text", "CANDIDATE.CurrentPosition", "Payroll Administrator", 0.92, "mapped"],
      ["current_employer", "text", "CANDIDATE_EMPLOYMENT.Employer", "Leeds City Council", 0.88, "mapped", { note: "Current job from CANDIDATE_EMPLOYMENT." }],
      ["address_line_1", "text", "CANDIDATE.Address", "14 Mill Lane", 0.71, "review", { transform: "split_address", note: "Address is one free-text field; the split is a best guess." }],
      ["address_line_2", "text", null, "—", 0, "unmapped"],
      ["city", "text", "CANDIDATE.Address", "Leeds", 0.71, "review", { transform: "split_address" }],
      ["postcode", "postcode", "CANDIDATE.PostCode", "LS6 2AB", 0.96, "mapped", { transform: "normalise_postcode" }],
      ["country", "text", null, "United Kingdom", 0.9, "mapped", { transform: "constant" }],
      ["source", "enum", "CANDIDATE.HowHeard", "Totaljobs → job_board", 0.78, "review", { transform: "value_map", note: "“Other” and “?” have no match yet." }],
      ["status", "enum", "LOOKUP_STAGE.Description", "Placed → placed", 0.8, "review", { transform: "value_map", note: "Stage codes resolved through LOOKUP_STAGE. “Interviewing” has no match yet." }],
      ["linkedin_url", "url", "CANDIDATE_SOCIAL.Url", "linkedin.com/in/amara-okafor", 0.9, "mapped", { transform: "add_https" }],
      ["owner_user_id", "ref:users", "CANDIDATE.ConsultantID", "U-0012", 0.95, "mapped"],
      ["created_at", "datetime", "CANDIDATE.DateRegistered", "2021-03-14 09:22", 0.93, "mapped", { transform: "parse_date" }],
    ]),
  },
  {
    key: "jobs", label: "Jobs", description: "Vacancies the agency is working on.", sourceTable: "VACANCY", rows: 1630,
    fields: f([
      ["job_id", "id", "VACANCY.VacancyID", "J-7719", 0.99, "mapped", { required: true }],
      ["client_id", "ref:clients", "VACANCY.CompanyID", "CL-2081", 0.98, "mapped", { required: true }],
      ["contact_id", "ref:contacts", null, "—", 0, "unmapped"],
      ["title", "text", "VACANCY.JobTitle", "Payroll Supervisor", 0.98, "mapped", { required: true }],
      ["employment_type", "enum", "VACANCY.Type", "Permanent → permanent", 0.95, "mapped", { transform: "value_map" }],
      ["salary_min", "money", "VACANCY.SalaryFrom", "32000", 0.96, "mapped"],
      ["salary_max", "money", "VACANCY.SalaryTo", "36000", 0.96, "mapped"],
      ["rate", "money", null, "—", 0, "unmapped"],
      ["rate_unit", "enum", null, "—", 0, "unmapped"],
      ["location", "text", "COMPANY.Town", "Leeds", 0.72, "review", { note: "Jobs have no location column; using the client’s town." }],
      ["status", "enum", "VACANCY.Status", "Open → open", 0.94, "mapped", { transform: "value_map" }],
      ["owner_user_id", "ref:users", "VACANCY_CONSULTANT.UserID", "U-0012", 0.9, "mapped", { note: "Primary consultant from VACANCY_CONSULTANT." }],
      ["opened_at", "date", "VACANCY.CreatedOn", "2024-05-02", 0.8, "review", { transform: "parse_date", note: "Mixed formats: DD/MM/YYYY and YYYY-MM-DD." }],
      ["closed_at", "date", null, "—", 0, "unmapped"],
    ]),
  },
  {
    key: "placements", label: "Placements", description: "A candidate placed into a job.", sourceTable: "PLACEMENT", rows: 742,
    fields: f([
      ["placement_id", "id", "PLACEMENT.PlacementID", "P-3310", 0.99, "mapped", { required: true }],
      ["candidate_id", "ref:candidates", "PLACEMENT.CandidateID", "C-104233", 0.99, "mapped", { required: true }],
      ["job_id", "ref:jobs", "PLACEMENT.VacancyID", "J-7719", 0.99, "mapped", { required: true }],
      ["start_date", "date", "PLACEMENT.StartDate", "2024-07-01", 0.97, "mapped", { transform: "parse_date" }],
      ["end_date", "date", "PLACEMENT.EndDate", "(blank)", 0.95, "mapped", { transform: "parse_date" }],
      ["salary", "money", null, "—", 0, "unmapped"],
      ["fee", "money", "PLACEMENT.Fee", "6480", 0.93, "mapped"],
      ["placement_type", "enum", "VACANCY.Type", "Permanent → permanent", 0.74, "review", { transform: "value_map", note: "Taken from the linked job’s type." }],
      ["owner_user_id", "ref:users", "CANDIDATE.ConsultantID", "U-0012", 0.78, "review", { note: "Placement has no owner; using the candidate’s consultant." }],
    ]),
  },
  {
    key: "notes", label: "Notes", description: "Free-text notes attached to any record.", sourceTable: "NOTE", rows: 45210,
    fields: f([
      ["note_id", "id", "NOTE.NoteID", "N-900112", 0.99, "mapped", { required: true }],
      ["entity_type", "enum", "NOTE.LinkType", "CAN → candidate", 0.9, "mapped", { transform: "value_map" }],
      ["entity_id", "id", "NOTE.LinkID", "C-104233", 0.93, "mapped", { required: true }],
      ["author_user_id", "ref:users", "NOTE.CreatedBy", "U-0012", 0.94, "mapped"],
      ["note_type", "enum", "NOTE.Category", "Call", 0.82, "review"],
      ["body", "long_text", "NOTE.Text", "Called re: payroll role, keen to…", 0.97, "mapped"],
      ["created_at", "datetime", "NOTE.Created", "2024-04-02 14:31", 0.95, "mapped"],
    ]),
  },
  {
    key: "histories", label: "Histories", description: "Field-level change history from the source.", sourceTable: "AUDIT", rows: 120330,
    fields: f([
      ["history_id", "id", "AUDIT.AuditID", "A-5530021", 0.99, "mapped", { required: true }],
      ["entity_type", "enum", "AUDIT.TableName", "CANDIDATE → candidate", 0.88, "mapped"],
      ["entity_id", "id", "AUDIT.RecordID", "C-104233", 0.92, "mapped", { required: true }],
      ["field_changed", "text", "AUDIT.FieldName", "MobileTel", 0.95, "mapped"],
      ["old_value", "text", "AUDIT.OldValue", "07700 900400", 0.96, "mapped"],
      ["new_value", "text", "AUDIT.NewValue", "07700 900412", 0.96, "mapped"],
      ["changed_by", "ref:users", "AUDIT.UserID", "U-0012", 0.93, "mapped"],
      ["changed_at", "datetime", "AUDIT.Stamp", "2023-11-08 16:05", 0.94, "mapped"],
    ]),
  },
  {
    key: "activities", label: "Activities", description: "Calls, emails, meetings and interviews.", sourceTable: null, rows: 0,
    fields: f([
      ["activity_id", "id", null, "—", 0, "unmapped", { required: true, note: "No activity table found. Activities may live inside NOTE." }],
      ["activity_type", "enum", null, "—", 0, "unmapped"],
      ["candidate_id", "ref:candidates", null, "—", 0, "unmapped"],
      ["contact_id", "ref:contacts", null, "—", 0, "unmapped"],
      ["job_id", "ref:jobs", null, "—", 0, "unmapped"],
      ["user_id", "ref:users", null, "—", 0, "unmapped"],
      ["occurred_at", "datetime", null, "—", 0, "unmapped"],
      ["outcome", "text", null, "—", 0, "unmapped"],
      ["subject", "text", null, "—", 0, "unmapped"],
    ]),
  },
  {
    key: "documents", label: "Documents", description: "CVs and other files attached to records.", sourceTable: null, rows: 0,
    fields: f([
      ["document_id", "id", null, "—", 0, "unmapped", { required: true, note: "No document table in the upload. Add the CV folder or export." }],
      ["entity_type", "enum", null, "—", 0, "unmapped"],
      ["entity_id", "id", null, "—", 0, "unmapped", { required: true }],
      ["file_name", "text", null, "—", 0, "unmapped", { required: true }],
      ["file_type", "text", null, "—", 0, "unmapped"],
      ["storage_path", "text", null, "—", 0, "unmapped", { required: true }],
      ["uploaded_at", "datetime", null, "—", 0, "unmapped"],
    ]),
  },
];

// ---- Extracted canonical records (what the canonical layer actually holds) ----
// Values are after transforms: phones normalised, dates ISO, enums mapped.

export type CanonicalRecord = Record<string, string | null>;

export const CANONICAL_ROWS: Record<string, CanonicalRecord[]> = {
  users: [
    { user_id: "U-0012", first_name: "Priya", last_name: "Shah", email: "p.shah@spencerthomas.example", role: "recruiter", office: "Leeds", is_active: "true" },
    { user_id: "U-0014", first_name: "Tom", last_name: "Reid", email: "t.reid@spencerthomas.example", role: "recruiter", office: "Leeds", is_active: "true" },
    { user_id: "U-0020", first_name: "Grace", last_name: "Boateng", email: "g.boateng@spencerthomas.example", role: "manager", office: "Bradford", is_active: "true" },
    { user_id: "U-0031", first_name: "Liam", last_name: "Doyle", email: "l.doyle@spencerthomas.example", role: "other", office: "Leeds", is_active: "false" },
  ],
  clients: [
    { client_id: "CL-2081", company_name: "Harlow Foods Ltd", industry: "Food manufacturing", website: "https://harlowfoods.example", phone: "+44 113 496 0123", address_line_1: null, address_line_2: null, city: "Leeds", postcode: "LS4 2AZ", country: "United Kingdom", status: null, owner_user_id: "U-0012", created_at: null },
    { client_id: "CL-2090", company_name: "Pennine Logistics", industry: "Logistics", website: "https://penninelog.example", phone: "+44 161 496 0777", address_line_1: null, address_line_2: null, city: "Manchester", postcode: "M1 2AB", country: "United Kingdom", status: null, owner_user_id: "U-0014", created_at: null },
    { client_id: "CL-2102", company_name: "Aire Valley Health", industry: "Healthcare", website: "https://airevalley.example", phone: "+44 1274 496 010", address_line_1: null, address_line_2: null, city: "Bradford", postcode: "BD1 1AA", country: "United Kingdom", status: null, owner_user_id: "U-0020", created_at: null },
  ],
  contacts: [
    { contact_id: "CT-55102", client_id: "CL-2081", first_name: "Helen", last_name: "Marsh", job_title: "HR Manager", email: "h.marsh@harlowfoods.example", phone: "+44 113 496 0140", mobile: "+44 7700 900771", status: "active", owner_user_id: "U-0014", created_at: "2022-01-14 10:02" },
    { contact_id: "CT-55117", client_id: "CL-2090", first_name: "Raj", last_name: "Patel", job_title: "Ops Director", email: "raj.patel@penninelog.example", phone: null, mobile: "+44 7700 900808", status: "active", owner_user_id: "U-0014", created_at: "2022-03-02 09:41" },
    { contact_id: "CT-55130", client_id: "CL-2102", first_name: "Claire", last_name: "Ndlovu", job_title: "Ward Manager", email: "c.ndlovu@airevalley.example", phone: "+44 1274 496 022", mobile: null, status: "left_company", owner_user_id: "U-0020", created_at: "2022-05-19 15:10" },
  ],
  candidates: [
    { candidate_id: "C-104233", first_name: "Amara", last_name: "Okafor", email: "amara.okafor@mail.example", mobile: "+44 7700 900412", phone: "+44 113 496 0555", current_job_title: "Payroll Administrator", current_employer: "Leeds City Council", address_line_1: "14 Mill Lane", address_line_2: null, city: "Leeds", postcode: "LS6 2AB", country: "United Kingdom", source: "job_board", status: "placed", linkedin_url: "https://linkedin.com/in/amara-okafor", owner_user_id: "U-0012", created_at: "2021-03-14 09:22" },
    { candidate_id: "C-104240", first_name: "James", last_name: "Whitley", email: "j.whitley@mail.example", mobile: "+44 7700 900518", phone: "+44 1924 496 222", current_job_title: "Warehouse Supervisor", current_employer: "Pennine Logistics", address_line_1: "2 Kirkgate", address_line_2: null, city: "Wakefield", postcode: "WF1 3HQ", country: "United Kingdom", source: "job_board", status: "placed", linkedin_url: "https://www.linkedin.com/in/jwhitley", owner_user_id: "U-0014", created_at: "2021-04-02 11:05" },
    { candidate_id: "C-104251", first_name: "Kwame", last_name: "Asante", email: "kwame.asante@mail.example", mobile: "+44 7700 900633", phone: null, current_job_title: "Staff Nurse", current_employer: "Aire Valley Health", address_line_1: "88 Manningham Lane", address_line_2: null, city: "Bradford", postcode: "BD7 1DP", country: "United Kingdom", source: "referral", status: "placed", linkedin_url: "https://linkedin.com/in/kasante", owner_user_id: "U-0020", created_at: "2021-05-19 15:40" },
    { candidate_id: "C-104266", first_name: "Sofia", last_name: "Marchetti", email: null, mobile: "+44 7700 900702", phone: "+44 20 7946 0018", current_job_title: "Credit Controller", current_employer: "Northern Credit Ltd", address_line_1: "Flat 3, 21 Park Row", address_line_2: null, city: "Leeds", postcode: "LS1 5HD", country: "United Kingdom", source: null, status: null, linkedin_url: null, owner_user_id: "U-0012", created_at: "2021-06-01 08:51" },
    { candidate_id: "C-104270", first_name: "Daniel", last_name: "Hughes", email: "dan.hughes@mail.example", mobile: null, phone: null, current_job_title: "Forklift Driver", current_employer: null, address_line_1: "7 Station Rd", address_line_2: null, city: "Castleford", postcode: "WF10 1AA", country: "United Kingdom", source: "linkedin", status: "available", linkedin_url: null, owner_user_id: "U-0014", created_at: "2021-06-12 13:17" },
  ],
  jobs: [
    { job_id: "J-7719", client_id: "CL-2081", contact_id: null, title: "Payroll Supervisor", employment_type: "permanent", salary_min: "32000", salary_max: "36000", rate: null, rate_unit: null, location: null, status: "open", owner_user_id: null, opened_at: "2024-05-02", closed_at: null },
    { job_id: "J-7722", client_id: "CL-2090", contact_id: null, title: "Transport Planner", employment_type: "permanent", salary_min: "30000", salary_max: "34000", rate: null, rate_unit: null, location: null, status: "open", owner_user_id: null, opened_at: "2024-05-09", closed_at: null },
    { job_id: "J-7730", client_id: "CL-2102", contact_id: null, title: "Band 5 Staff Nurse", employment_type: "contract", salary_min: "29000", salary_max: "32000", rate: null, rate_unit: null, location: null, status: "filled", owner_user_id: null, opened_at: "2024-05-15", closed_at: null },
  ],
  placements: [
    { placement_id: "P-3310", candidate_id: "C-104233", job_id: "J-7719", start_date: "2024-07-01", end_date: null, salary: null, fee: "6480", placement_type: "permanent", owner_user_id: null },
    { placement_id: "P-3318", candidate_id: "C-104251", job_id: "J-7730", start_date: "2024-08-12", end_date: "2025-02-12", salary: null, fee: "4800", placement_type: "contract", owner_user_id: null },
    { placement_id: "P-3325", candidate_id: "C-104240", job_id: "J-7722", start_date: "2024-09-02", end_date: null, salary: null, fee: "6120", placement_type: "permanent", owner_user_id: null },
  ],
  notes: [
    { note_id: "N-900112", entity_type: "candidate", entity_id: "C-104233", author_user_id: "U-0012", note_type: "Call", body: "Called re: payroll role, keen to move closer to home.", created_at: "2024-04-02 14:31" },
    { note_id: "N-900118", entity_type: "contact", entity_id: "CT-55102", author_user_id: "U-0014", note_type: "Meeting", body: "Met Helen to discuss Q3 hiring plan.", created_at: "2024-04-03 10:00" },
    { note_id: "N-900131", entity_type: "job", entity_id: "J-7730", author_user_id: "U-0020", note_type: "General", body: "Client confirmed band 5 rate.", created_at: "2024-05-16 09:12" },
  ],
  histories: [
    { history_id: "A-5530021", entity_type: "candidate", entity_id: "C-104233", field_changed: "MobileTel", old_value: "07700 900400", new_value: "07700 900412", changed_by: "U-0012", changed_at: "2023-11-08 16:05" },
    { history_id: "A-5530090", entity_type: "job", entity_id: "J-7730", field_changed: "Status", old_value: "Open", new_value: "Filled", changed_by: "U-0020", changed_at: "2024-08-01 11:40" },
  ],
  activities: [],
  documents: [],
};

// Every column in each source table, with one sample value (from samples/tracker/*.csv
// where the file exists). Used for the mapping dropdowns in the developer view.
export const SOURCE_COLUMNS: Record<string, { name: string; sample: string }[]> = {
  CANDIDATE: [
    { name: "CandidateID", sample: "C-104233" }, { name: "Forename", sample: "Amara" }, { name: "Surname", sample: "Okafor" },
    { name: "Email1", sample: "amara.okafor@mail.example" }, { name: "MobileTel", sample: "07700 900412" },
    { name: "CurrentPosition", sample: "Payroll Administrator" }, { name: "Address", sample: "14 Mill Lane, Leeds" },
    { name: "PostCode", sample: "LS6 2AB" }, { name: "HowHeard", sample: "Totaljobs" }, { name: "ConsultantID", sample: "U-0012" },
    { name: "DateRegistered", sample: "14/03/2021 09:22" }, { name: "Stage", sample: "3" },
  ],
  COMPANY: [
    { name: "CompanyID", sample: "CL-2081" }, { name: "Name", sample: "Harlow Foods Ltd" }, { name: "Sector", sample: "Food manufacturing" },
    { name: "Web", sample: "harlowfoods.example" }, { name: "Tel", sample: "0113 496 0123" }, { name: "Town", sample: "Leeds" },
    { name: "PostCode", sample: "LS4 2AZ" }, { name: "OwnerID", sample: "U-0012" },
  ],
  CONTACT: [
    { name: "ContactID", sample: "CT-55102" }, { name: "CompanyID", sample: "CL-2081" }, { name: "Forename", sample: "Helen" },
    { name: "Surname", sample: "Marsh" }, { name: "Position", sample: "HR Manager" }, { name: "Email", sample: "h.marsh@harlowfoods.example" },
    { name: "DirectLine", sample: "0113 496 0140" }, { name: "Mobile", sample: "07700 900771" }, { name: "Left", sample: "N" },
    { name: "OwnerID", sample: "U-0014" }, { name: "Created", sample: "2022-01-14 10:02" },
  ],
  VACANCY: [
    { name: "VacancyID", sample: "J-7719" }, { name: "CompanyID", sample: "CL-2081" }, { name: "JobTitle", sample: "Payroll Supervisor" },
    { name: "Type", sample: "Permanent" }, { name: "SalaryFrom", sample: "32000" }, { name: "SalaryTo", sample: "36000" },
    { name: "Status", sample: "Open" }, { name: "CreatedOn", sample: "02/05/2024" },
  ],
  PLACEMENT: [
    { name: "PlacementID", sample: "P-3310" }, { name: "CandidateID", sample: "C-104233" }, { name: "VacancyID", sample: "J-7719" },
    { name: "StartDate", sample: "01/07/2024" }, { name: "EndDate", sample: "" }, { name: "Fee", sample: "6480" },
  ],
  USER: [
    { name: "UserID", sample: "U-0012" }, { name: "Forename", sample: "Priya" }, { name: "Surname", sample: "Shah" },
    { name: "EmailAddress", sample: "p.shah@spencerthomas.example" }, { name: "Role", sample: "Consultant" }, { name: "Branch", sample: "Leeds" },
    { name: "Disabled", sample: "0" },
  ],
  NOTE: [
    { name: "NoteID", sample: "N-900112" }, { name: "LinkType", sample: "CAN" }, { name: "LinkID", sample: "C-104233" },
    { name: "CreatedBy", sample: "U-0012" }, { name: "Category", sample: "Call" }, { name: "Text", sample: "Called re: payroll role, keen to…" },
    { name: "Created", sample: "02/04/2024 14:31" },
  ],
  LOOKUP_STAGE: [{ name: "StageID", sample: "3" }, { name: "Description", sample: "Placed" }, { name: "IsActive", sample: "1" }],
  CANDIDATE_PHONE: [
    { name: "PhoneID", sample: "PH-77120" }, { name: "CandidateID", sample: "C-104233" }, { name: "Type", sample: "Home" },
    { name: "Number", sample: "0113 496 0555" }, { name: "Updated", sample: "2023-02-11 10:15" },
  ],
  CANDIDATE_EMPLOYMENT: [
    { name: "EmploymentID", sample: "E-40021" }, { name: "CandidateID", sample: "C-104233" }, { name: "Employer", sample: "Leeds City Council" },
    { name: "JobTitle", sample: "Payroll Administrator" }, { name: "StartDate", sample: "01/09/2019" }, { name: "EndDate", sample: "" },
    { name: "IsCurrent", sample: "1" },
  ],
  CANDIDATE_SOCIAL: [
    { name: "SocialID", sample: "S-9001" }, { name: "CandidateID", sample: "C-104233" }, { name: "Network", sample: "LinkedIn" },
    { name: "Url", sample: "linkedin.com/in/amara-okafor" },
  ],
  VACANCY_CONSULTANT: [{ name: "VacancyID", sample: "J-7719" }, { name: "UserID", sample: "U-0012" }, { name: "IsPrimary", sample: "1" }],
  AUDIT: [
    { name: "AuditID", sample: "A-5530021" }, { name: "TableName", sample: "CANDIDATE" }, { name: "RecordID", sample: "C-104233" },
    { name: "FieldName", sample: "MobileTel" }, { name: "OldValue", sample: "07700 900400" }, { name: "NewValue", sample: "07700 900412" },
    { name: "UserID", sample: "U-0012" }, { name: "Stamp", sample: "08/11/2023 16:05" },
  ],
};

export function sourceSample(qualified: string | null): string {
  if (!qualified) return "—";
  const [table, col] = qualified.split(".");
  const s = SOURCE_COLUMNS[table]?.find((c) => c.name === col)?.sample;
  return s === undefined ? "—" : s === "" ? "(blank)" : s;
}

const FILE_SIZES: Record<string, [bytes: number, rows: number]> = {
  CANDIDATE: [1_480_000, 8420], COMPANY: [31_000, 312], CONTACT: [148_000, 1184], VACANCY: [139_000, 1630],
  PLACEMENT: [41_000, 742], USER: [1_100, 14], NOTE: [9_800_000, 45210], AUDIT: [11_400_000, 120330],
  LOOKUP_STAGE: [210, 6], CANDIDATE_PHONE: [412_000, 9870], CANDIDATE_EMPLOYMENT: [1_210_000, 19_440],
  CANDIDATE_SOCIAL: [198_000, 3020], VACANCY_CONSULTANT: [38_000, 2210],
};

// ---- Joins: one canonical entity can be built from several source tables ----

export type Join = {
  id: string;
  table: string;
  type: "left" | "inner";
  /** Join keys: a column already in the query (base or earlier join) = a column of this table. */
  on: { left: string; right: string }[];
  /** Optional row filter on this table, e.g. Type = 'Home'. */
  filter?: { column: string; value: string };
  /** many_to_one: each base row finds at most one match (lookups, parents).
   *  one_to_many: a base row can match several rows, so a pick rule is needed. */
  cardinality: "many_to_one" | "one_to_many";
  pick?: { rule: "latest" | "earliest"; orderBy: string };
  /** Base records that found a match on the last run. */
  matched: number;
};

export const ENTITY_JOINS: Record<string, Join[]> = {
  candidates: [
    { id: "j1", table: "LOOKUP_STAGE", type: "left", on: [{ left: "CANDIDATE.Stage", right: "StageID" }], cardinality: "many_to_one", matched: 8420 },
    { id: "j2", table: "CANDIDATE_PHONE", type: "left", on: [{ left: "CANDIDATE.CandidateID", right: "CandidateID" }], filter: { column: "Type", value: "Home" }, cardinality: "one_to_many", pick: { rule: "latest", orderBy: "Updated" }, matched: 3210 },
    { id: "j3", table: "CANDIDATE_EMPLOYMENT", type: "left", on: [{ left: "CANDIDATE.CandidateID", right: "CandidateID" }], filter: { column: "IsCurrent", value: "1" }, cardinality: "one_to_many", pick: { rule: "latest", orderBy: "StartDate" }, matched: 6050 },
    { id: "j4", table: "CANDIDATE_SOCIAL", type: "left", on: [{ left: "CANDIDATE.CandidateID", right: "CandidateID" }], filter: { column: "Network", value: "LinkedIn" }, cardinality: "one_to_many", pick: { rule: "latest", orderBy: "SocialID" }, matched: 2904 },
  ],
  jobs: [
    { id: "j1", table: "COMPANY", type: "left", on: [{ left: "VACANCY.CompanyID", right: "CompanyID" }], cardinality: "many_to_one", matched: 1630 },
    { id: "j2", table: "VACANCY_CONSULTANT", type: "left", on: [{ left: "VACANCY.VacancyID", right: "VacancyID" }], filter: { column: "IsPrimary", value: "1" }, cardinality: "one_to_many", pick: { rule: "earliest", orderBy: "UserID" }, matched: 1588 },
  ],
  placements: [
    { id: "j1", table: "VACANCY", type: "left", on: [{ left: "PLACEMENT.VacancyID", right: "VacancyID" }], cardinality: "many_to_one", matched: 742 },
    { id: "j2", table: "CANDIDATE", type: "left", on: [{ left: "PLACEMENT.CandidateID", right: "CandidateID" }], cardinality: "many_to_one", matched: 739 },
  ],
};

/** Suggest how to join a table, from shared key column names (…ID). */
export function suggestJoin(inQuery: string[], table: string): Omit<Join, "id" | "matched"> | null {
  const cols = SOURCE_COLUMNS[table]?.map((c) => c.name) ?? [];
  const ownKey = cols[0];
  for (const t of inQuery) {
    for (const c of SOURCE_COLUMNS[t] ?? []) {
      if (!/ID$/.test(c.name)) continue;
      if (cols.includes(c.name)) {
        // The other table's own key → we're pointing at a parent/lookup (one match each)
        return { table, type: "left", on: [{ left: `${t}.${c.name}`, right: c.name }], cardinality: c.name === ownKey ? "many_to_one" : "one_to_many", ...(c.name === ownKey ? {} : { pick: { rule: "latest", orderBy: cols[cols.length - 1] } }) };
      }
    }
  }
  return null;
}

export const INITIAL_UPLOADS: UploadItem[] = Object.entries(FILE_SIZES).map(([table, [size, rows]]) => ({
  id: `seed-${table}`,
  name: `${table}.csv`,
  path: `${table}.csv`,
  size,
  kind: "csv",
  status: "uploaded",
  progress: 1,
  warnings: [],
  columns: SOURCE_COLUMNS[table].map((c) => c.name),
  delimiter: ",",
  rows,
  rowsExact: true,
}));

export const SOURCE_TABLES = [
  { name: "CANDIDATE", rows: 8420, columns: 12, key: "CandidateID", entity: "candidates" },
  { name: "COMPANY", rows: 312, columns: 8, key: "CompanyID", entity: "clients" },
  { name: "CONTACT", rows: 1184, columns: 11, key: "ContactID", entity: "contacts" },
  { name: "VACANCY", rows: 1630, columns: 8, key: "VacancyID", entity: "jobs" },
  { name: "PLACEMENT", rows: 742, columns: 6, key: "PlacementID", entity: "placements" },
  { name: "USER", rows: 14, columns: 7, key: "UserID", entity: "users" },
  { name: "NOTE", rows: 45210, columns: 7, key: "NoteID", entity: "notes" },
  { name: "AUDIT", rows: 120330, columns: 8, key: "AuditID", entity: "histories" },
  { name: "LOOKUP_STAGE", rows: 6, columns: 3, key: "StageID", entity: "candidates (joined)" },
  { name: "CANDIDATE_PHONE", rows: 9870, columns: 5, key: "PhoneID", entity: "candidates (joined)" },
  { name: "CANDIDATE_EMPLOYMENT", rows: 19440, columns: 7, key: "EmploymentID", entity: "candidates (joined)" },
  { name: "CANDIDATE_SOCIAL", rows: 3020, columns: 4, key: "SocialID", entity: "candidates (joined)" },
  { name: "VACANCY_CONSULTANT", rows: 2210, columns: 3, key: null, entity: "jobs (joined)" },
  { name: "TMP_IMPORT_2019", rows: 2210, columns: 4, key: null, entity: "ignore" },
];

// ---- Target (Bullhorn-style, see pipeline/sqlmesh/models/target/bullhorn) ----

export type TargetEntity = {
  key: string;
  label: string;
  file: string;
  ready: number;
  warnings: number;
  rejected: number;
  columns: string[];
  preview: (string | null)[][];
  issues: { level: "warning" | "rejected"; text: string; count: number }[];
};

export const TARGET: TargetEntity[] = [
  {
    key: "candidates", label: "Candidates", file: "Candidate.csv", ready: 8291, warnings: 104, rejected: 25,
    columns: ["external_id", "first_name", "last_name", "email", "mobile", "occupation", "address.address1", "address.city", "address.zip", "source", "owner_id", "date_added"],
    preview: [
      ["C-104233", "Amara", "Okafor", "amara.okafor@mail.example", "+44 7700 900412", "Payroll Administrator", "14 Mill Lane", "Leeds", "LS6 2AB", "Job board", "U-0012", "2021-03-14 09:22"],
      ["C-104240", "James", "Whitley", "j.whitley@mail.example", "+44 7700 900518", "Warehouse Supervisor", "2 Kirkgate", "Wakefield", "WF1 3HQ", "Job board", "U-0014", "2021-04-02 11:05"],
      ["C-104251", "Kwame", "Asante", "kwame.asante@mail.example", "+44 7700 900633", "Staff Nurse", "88 Manningham Lane", "Bradford", "BD7 1DP", "Referral", "U-0020", "2021-05-19 15:40"],
      ["C-104266", "Sofia", "Marchetti", null, "+44 7700 900702", "Credit Controller", "Flat 3, 21 Park Row", "Leeds", "LS1 5HD", null, "U-0012", "2021-06-01 08:51"],
      ["C-104270", "Daniel", "Hughes", "dan.hughes@mail.example", null, "Forklift Driver", "7 Station Rd", "Castleford", "WF10 1AA", "LinkedIn", "U-0014", "2021-06-12 13:17"],
    ],
    issues: [
      { level: "warning", text: "Address split guessed (no comma in source)", count: 61 },
      { level: "warning", text: "Source value “Other” left blank", count: 43 },
      { level: "rejected", text: "No email or mobile (target requires one)", count: 25 },
    ],
  },
  {
    key: "clients", label: "Clients", file: "ClientCorporation.csv", ready: 301, warnings: 11, rejected: 0,
    columns: ["external_id", "name", "industry", "company_url", "phone", "address.city", "address.zip", "address.country", "owner_id"],
    preview: [
      ["CL-2081", "Harlow Foods Ltd", "Manufacturing", "https://harlowfoods.example", "+44 113 496 0123", "Leeds", "LS4 2AZ", "United Kingdom", "U-0012"],
      ["CL-2090", "Pennine Logistics", "Transport & Logistics", "https://penninelog.example", "+44 161 496 0777", "Manchester", "M1 2AB", "United Kingdom", "U-0014"],
      ["CL-2102", "Aire Valley Health", "Healthcare", "https://airevalley.example", "+44 1274 496 010", "Bradford", "BD1 1AA", "United Kingdom", "U-0020"],
    ],
    issues: [{ level: "warning", text: "Sector has no matching industry in target", count: 11 }],
  },
  {
    key: "contacts", label: "Contacts", file: "ClientContact.csv", ready: 1150, warnings: 30, rejected: 4,
    columns: ["external_id", "client_corporation_id", "first_name", "last_name", "occupation", "email", "phone", "mobile", "status"],
    preview: [
      ["CT-55102", "CL-2081", "Helen", "Marsh", "HR Manager", "h.marsh@harlowfoods.example", "+44 113 496 0140", "+44 7700 900771", "Active"],
      ["CT-55117", "CL-2090", "Raj", "Patel", "Ops Director", "raj.patel@penninelog.example", null, "+44 7700 900808", "Active"],
    ],
    issues: [
      { level: "warning", text: "“Left = Y” mapped to Inactive", count: 30 },
      { level: "rejected", text: "Company not found", count: 4 },
    ],
  },
  {
    key: "jobs", label: "Jobs", file: "JobOrder.csv", ready: 1598, warnings: 32, rejected: 0,
    columns: ["external_id", "client_corporation_id", "title", "employment_type", "salary_low", "salary_high", "status", "date_added"],
    preview: [
      ["J-7719", "CL-2081", "Payroll Supervisor", "Permanent", "32000", "36000", "Accepting Candidates", "2024-05-02"],
      ["J-7722", "CL-2090", "Transport Planner", "Permanent", "30000", "34000", "Accepting Candidates", "2024-05-09"],
      ["J-7730", "CL-2102", "Band 5 Staff Nurse", "Contract", "29000", "32000", "Filled", "2024-05-15"],
    ],
    issues: [{ level: "warning", text: "Date format guessed", count: 32 }],
  },
  {
    key: "placements", label: "Placements", file: "Placement.csv", ready: 742, warnings: 0, rejected: 0,
    columns: ["external_id", "candidate_id", "job_order_id", "date_begin", "date_end", "fee", "employment_type"],
    preview: [
      ["P-3310", "C-104233", "J-7719", "2024-07-01", null, "6480", "Permanent"],
      ["P-3318", "C-104251", "J-7730", "2024-08-12", "2025-02-12", "4800", "Contract"],
      ["P-3325", "C-104240", "J-7722", "2024-09-02", null, "6120", "Permanent"],
    ],
    issues: [],
  },
  {
    key: "users", label: "Users", file: "CorporateUser.csv", ready: 14, warnings: 0, rejected: 0,
    columns: ["external_id", "first_name", "last_name", "email", "user_type", "department", "enabled"],
    preview: [
      ["U-0012", "Priya", "Shah", "p.shah@spencerthomas.example", "Recruiter", "Leeds", "true"],
      ["U-0014", "Tom", "Reid", "t.reid@spencerthomas.example", "Recruiter", "Leeds", "true"],
      ["U-0020", "Grace", "Boateng", "g.boateng@spencerthomas.example", "Manager", "Bradford", "true"],
    ],
    issues: [],
  },
  {
    key: "notes", label: "Notes", file: "Note.csv", ready: 45020, warnings: 0, rejected: 190,
    columns: ["external_id", "person_reference_id", "commenting_person_id", "action", "comments", "date_added"],
    preview: [
      ["N-900112", "C-104233", "U-0012", "Call", "Called re: payroll role, keen to…", "2024-04-02 14:31"],
      ["N-900118", "CT-55102", "U-0014", "Meeting", "Met Helen to discuss Q3 hiring…", "2024-04-03 10:00"],
    ],
    issues: [{ level: "rejected", text: "Linked record was not migrated", count: 190 }],
  },
];

export type Run = {
  id: string;
  version: number;
  label: string;
  when: string;
  by: string;
  status: "complete" | "running" | "failed";
};

export const INITIAL_RUNS: Run[] = [
  { id: "r-3", version: 3, label: "Fixed candidate source values", when: "Today, 10:42", by: "Naya Damptey", status: "complete" },
  { id: "r-2", version: 2, label: "Added NOTE and AUDIT tables", when: "Yesterday, 16:10", by: "Naya Damptey", status: "complete" },
  { id: "r-1", version: 1, label: "First upload", when: "28 Sep, 09:15", by: "Tom Reid", status: "complete" },
];

export const INITIAL_REQUESTS = [
  { id: "cr-1", text: "Map “Totaljobs”, “TJ” and “total jobs” all to Job board.", status: "done" as const, when: "Today, 10:30" },
  { id: "cr-2", text: "Don’t migrate candidates who haven’t been updated since 2015.", status: "open" as const, when: "Today, 11:05" },
];
