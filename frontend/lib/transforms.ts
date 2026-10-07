// Previews of the mapping transforms, so a reviewer can drill into a field and see
// exactly what happens to real source values. The pipeline applies the same rules
// when it builds the canonical layer (pipeline/mapping → SQLMesh models).

export type SplitRule = "last_comma" | "first_comma" | "none";
export type DateFormat = "DMY" | "MDY";

export type TransformConfig = {
  splitRule?: SplitRule;
  dateFormat?: DateFormat;
  valueMap?: Record<string, string>; // source value (as written) → canonical value, "" = leave blank
  constant?: string;
};

export type Result = { value: string | null; problem?: string };

export const DEFAULTS: Required<Pick<TransformConfig, "splitRule" | "dateFormat">> = { splitRule: "last_comma", dateFormat: "DMY" };

// Which part of a split address each canonical field takes
export const ADDRESS_PART: Record<string, "line_1" | "line_2" | "city"> = { address_line_1: "line_1", address_line_2: "line_2", city: "city" };

export const ENUM_VALUES: Record<string, string[]> = {
  "users.role": ["recruiter", "manager", "admin", "other"],
  "candidates.source": ["job_board", "referral", "linkedin", "website", "agency", "other"],
  "jobs.employment_type": ["permanent", "contract", "temporary", "fixed_term"],
  "jobs.status": ["open", "on_hold", "filled", "closed", "cancelled"],
  "notes.entity_type": ["candidate", "contact", "client", "job", "placement"],
  "candidates.status": ["available", "placed", "not_looking", "archived"],
  "placements.placement_type": ["permanent", "contract", "temporary"],
};

export const DEFAULT_VALUE_MAPS: Record<string, Record<string, string>> = {
  "users.role": { Consultant: "recruiter", Manager: "manager", Admin: "admin" },
  "candidates.source": { Totaljobs: "job_board", TJ: "job_board", "total jobs": "job_board", Referral: "referral", LinkedIn: "linkedin", Indeed: "job_board" },
  "jobs.employment_type": { Permanent: "permanent", Contract: "contract", Temp: "temporary" },
  "jobs.status": { Open: "open", Filled: "filled", Closed: "closed", "On Hold": "on_hold" },
  "notes.entity_type": { CAN: "candidate", CON: "contact", COM: "client", VAC: "job" },
  "candidates.status": { Available: "available", Placed: "placed", "Not looking": "not_looking", Archived: "archived" },
  "placements.placement_type": { Permanent: "permanent", Contract: "contract", Temp: "temporary" },
};

/** Distinct source values with how many records have each. */
export const SOURCE_EXAMPLES: Record<string, { value: string; count: number }[]> = {
  "CANDIDATE.Address": [
    { value: "14 Mill Lane, Leeds", count: 1 }, { value: "2 Kirkgate, Wakefield", count: 1 },
    { value: "88 Manningham Lane, Bradford", count: 1 }, { value: "Flat 3, 21 Park Row, Leeds", count: 1 },
    { value: "7 Station Rd Castleford", count: 1 }, { value: "Unit 4, Ash Court, 12 High St, Otley", count: 1 },
    { value: "Leeds", count: 1 },
  ],
  "CANDIDATE.HowHeard": [
    { value: "Totaljobs", count: 3120 }, { value: "Referral", count: 1840 }, { value: "LinkedIn", count: 1502 },
    { value: "Indeed", count: 880 }, { value: "TJ", count: 410 }, { value: "Other", count: 330 },
    { value: "total jobs", count: 95 }, { value: "?", count: 45 },
  ],
  "USER.Role": [{ value: "Consultant", count: 9 }, { value: "Manager", count: 2 }, { value: "Resourcer", count: 2 }, { value: "Admin", count: 1 }],
  "VACANCY.Type": [{ value: "Permanent", count: 1210 }, { value: "Contract", count: 380 }, { value: "Temp", count: 40 }],
  "VACANCY.Status": [{ value: "Filled", count: 980 }, { value: "Closed", count: 400 }, { value: "Open", count: 210 }, { value: "On Hold", count: 40 }],
  "NOTE.LinkType": [{ value: "CAN", count: 30120 }, { value: "CON", count: 9800 }, { value: "COM", count: 3100 }, { value: "VAC", count: 2190 }],
  "CANDIDATE.MobileTel": [
    { value: "07700 900412", count: 1 }, { value: "07700900518", count: 1 }, { value: "+447700900633", count: 1 },
    { value: "(07700) 900 702", count: 1 }, { value: "0044 7700 900111", count: 1 }, { value: "n/a", count: 1 },
  ],
  "COMPANY.Tel": [{ value: "0113 496 0123", count: 1 }, { value: "0161-496-0777", count: 1 }, { value: "01274 496010", count: 1 }, { value: "496 0123", count: 1 }],
  "CANDIDATE.PostCode": [{ value: "LS6 2AB", count: 1 }, { value: "ls62ab", count: 1 }, { value: "WF1  3HQ", count: 1 }, { value: "bd7 1dp", count: 1 }, { value: "LS99", count: 1 }],
  "COMPANY.PostCode": [{ value: "LS4 2AZ", count: 1 }, { value: "M1 2AB", count: 1 }, { value: "bd11aa", count: 1 }],
  "CANDIDATE.DateRegistered": [
    { value: "14/03/2021 09:22", count: 1 }, { value: "02/04/2021 11:05", count: 1 }, { value: "19/05/2021 15:40", count: 1 },
    { value: "2021-06-01 08:51", count: 1 }, { value: "31/06/2021 10:00", count: 1 },
  ],
  "VACANCY.CreatedOn": [{ value: "02/05/2024", count: 1 }, { value: "2024-05-09", count: 1 }, { value: "15/05/2024", count: 1 }, { value: "05/13/2024", count: 1 }],
  "PLACEMENT.StartDate": [{ value: "01/07/2024", count: 1 }, { value: "12/08/2024", count: 1 }, { value: "02/09/2024", count: 1 }],
  "PLACEMENT.EndDate": [{ value: "", count: 2 }, { value: "12/02/2025", count: 1 }],
  "LOOKUP_STAGE.Description": [
    { value: "Available", count: 4100 }, { value: "Placed", count: 1900 }, { value: "Interviewing", count: 1200 },
    { value: "Not looking", count: 820 }, { value: "Archived", count: 400 },
  ],
  "CANDIDATE_PHONE.Number": [{ value: "0113 496 0555", count: 1 }, { value: "01924 496 222", count: 1 }, { value: "020 7946 0018", count: 1 }, { value: "ext 204", count: 1 }],
  "CANDIDATE_SOCIAL.Url": [{ value: "linkedin.com/in/amara-okafor", count: 1 }, { value: "https://www.linkedin.com/in/jwhitley", count: 1 }, { value: "http://linkedin.com/in/kasante", count: 1 }],
  "USER.Disabled": [{ value: "0", count: 12 }, { value: "1", count: 2 }],
  "COMPANY.Web": [{ value: "harlowfoods.example", count: 1 }, { value: "www.penninelog.example", count: 1 }, { value: "https://airevalley.example", count: 1 }, { value: "", count: 1 }],
};

// ---- transforms ----

export function splitAddress(raw: string, rule: SplitRule): { line_1: string | null; line_2: string | null; city: string | null; problem?: string } {
  const parts = raw.split(",").map((p) => p.trim()).filter(Boolean);
  if (rule === "none") return { line_1: raw.trim() || null, line_2: null, city: null };
  if (parts.length < 2) return { line_1: parts[0] ?? null, line_2: null, city: null, problem: "No comma, so the city couldn’t be split off" };
  const city = rule === "last_comma" ? parts[parts.length - 1] : parts.slice(1).join(", ");
  const street = rule === "last_comma" ? parts.slice(0, -1) : [parts[0]];
  return { line_1: street[0], line_2: street.slice(1).join(", ") || null, city };
}

export function normaliseUkPhone(raw: string): Result {
  let d = raw.replace(/[^\d+]/g, "");
  if (d.startsWith("+44")) d = "0" + d.slice(3);
  else if (d.startsWith("0044")) d = "0" + d.slice(4);
  d = d.replace(/\D/g, "");
  if (!/^0\d{10}$/.test(d)) return { value: null, problem: d.length ? "Not a full UK number" : "No number" };
  const n = d.slice(1);
  if (n.startsWith("7")) return { value: `+44 ${n.slice(0, 4)} ${n.slice(4)}` };
  if (/^(1\d1|11\d)/.test(n)) return { value: `+44 ${n.slice(0, 3)} ${n.slice(3, 6)} ${n.slice(6)}` };
  if (n.startsWith("2")) return { value: `+44 ${n.slice(0, 2)} ${n.slice(2, 6)} ${n.slice(6)}` };
  return { value: `+44 ${n.slice(0, 4)} ${n.slice(4)}` };
}

export function normalisePostcode(raw: string): Result {
  const p = raw.toUpperCase().replace(/\s+/g, "");
  if (!/^[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}$/.test(p)) return { value: null, problem: "Not a valid UK postcode" };
  return { value: `${p.slice(0, -3)} ${p.slice(-3)}` };
}

export function parseDate(raw: string, format: DateFormat, withTime: boolean): Result {
  const s = raw.trim();
  if (!s) return { value: null };
  let y: number, m: number, d: number, time = "";
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}:\d{2}))?/);
  const slash = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?: (\d{2}:\d{2}))?$/);
  if (iso) { [y, m, d] = [+iso[1], +iso[2], +iso[3]]; time = iso[4] ?? ""; }
  else if (slash) {
    const [a, b] = [+slash[1], +slash[2]];
    [d, m] = format === "DMY" ? [a, b] : [b, a];
    y = +slash[3]; time = slash[4] ?? "";
  } else return { value: null, problem: "Unrecognised date format" };
  const dt = new Date(Date.UTC(y, m - 1, d));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== m - 1 || dt.getUTCDate() !== d) {
    return { value: null, problem: m > 12 ? `Month ${m} doesn’t exist. Wrong date format?` : "Not a real date" };
  }
  const out = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  return { value: withTime && time ? `${out} ${time}` : out };
}

export function mapValue(raw: string, map: Record<string, string>): Result {
  if (!raw.trim()) return { value: null };
  const hit = Object.entries(map).find(([k]) => k.trim().toLowerCase() === raw.trim().toLowerCase());
  if (!hit) return { value: null, problem: "No match. Choose a value" };
  return { value: hit[1] || null };
}

export function addHttps(raw: string): Result {
  const s = raw.trim();
  if (!s) return { value: null };
  return { value: /^https?:\/\//i.test(s) ? s.replace(/^http:/i, "https:") : `https://${s}` };
}

export function invertFlag(raw: string): Result {
  if (raw === "0") return { value: "true" };
  if (raw === "1") return { value: "false" };
  return { value: null, problem: "Expected 0 or 1" };
}

/** Apply a field's transform to one source value. */
export function applyTransform(transform: string, entityField: string, fieldName: string, fieldType: string, raw: string, cfg: TransformConfig): Result {
  switch (transform) {
    case "split_address": {
      const r = splitAddress(raw, cfg.splitRule ?? DEFAULTS.splitRule);
      const part = ADDRESS_PART[fieldName] ?? "line_1";
      return { value: r[part], problem: r.problem && part === "city" ? r.problem : r.problem && part === "line_1" ? "City left in this line" : undefined };
    }
    case "normalise_uk_phone": return normaliseUkPhone(raw);
    case "normalise_postcode": return normalisePostcode(raw);
    case "parse_date": return parseDate(raw, cfg.dateFormat ?? DEFAULTS.dateFormat, fieldType === "datetime");
    case "value_map": return mapValue(raw, cfg.valueMap ?? DEFAULT_VALUE_MAPS[entityField] ?? {});
    case "add_https": return addHttps(raw);
    case "invert_flag": return invertFlag(raw);
    case "constant": return { value: cfg.constant ?? "United Kingdom" };
    default: return { value: raw };
  }
}

export const TRANSFORM_LABEL: Record<string, string> = {
  split_address: "Split address",
  normalise_uk_phone: "Format UK phone number",
  normalise_postcode: "Format UK postcode",
  parse_date: "Read date",
  value_map: "Map values",
  add_https: "Add https://",
  invert_flag: "Flip yes/no",
  constant: "Fixed value",
};
