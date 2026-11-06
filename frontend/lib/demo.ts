// Demo mode (NEXT_PUBLIC_DEMO=1): the app runs with no API or database, e.g. as a portfolio site.
// Every API call is answered from a snapshot in public/demo/ (made by scripts/make_demo_data.py).
// Duplicate decisions (merge / keep both) are saved in the visitor's browser, and the counts on the
// Data quality page update as they decide, the same way the real API does.

export const isDemo = process.env.NEXT_PUBLIC_DEMO === "1";

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
type Decision = { decision: "merge" | "not_duplicate"; entity: string; a: string; b: string; keep: "a" | "b" | null; fields: Record<string, string>; by: string; at: string };

const KEY = "migryr-demo-decisions";
const cache = new Map<string, Promise<Json>>();
const file = (name: string) => {
  if (!cache.has(name)) cache.set(name, fetch(`/demo/${name}`).then((r) => {
    if (!r.ok) throw new Error(`Demo data missing: ${name}`);
    return r.json();
  }));
  return cache.get(name)!;
};
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function decisions(): Record<string, Decision> {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { return {}; }
}
function saveDecisions(d: Record<string, Decision>) {
  try { localStorage.setItem(KEY, JSON.stringify(d)); } catch { /* private mode: decisions last for the visit */ }
}

// duplicate rule -> kind of record whose pairs it reports
const DUP_RULE: Record<string, string> = {
  "dup.person": "person", "dup.associate": "contact", "dup.account": "company", "dup.account.split_history": "company",
  "dup.job": "job", "dup.timesheet_line": "timesheet_line",
};

async function duplicates(entity: string | null) {
  const data = clone(await file("duplicates.json"));
  const d = decisions();
  for (const p of data.pairs) p.decision = d[p.key] ?? null;
  for (const [k, e] of Object.entries<Json>(data.entities)) e.to_review = data.pairs.filter((p: Json) => p.entity === k && !p.decision).length;
  if (entity) data.pairs = data.pairs.filter((p: Json) => p.entity === entity);
  return data;
}

async function report() {
  const rep = clone(await file("report.json"));
  const dups = await duplicates(null);
  const d = decisions();
  const total = dups.pairs.length;
  const merged = dups.pairs.filter((p: Json) => p.decision?.decision === "merge").length;
  const kept = dups.pairs.filter((p: Json) => p.decision?.decision === "not_duplicate").length;
  if (!Object.keys(d).length) return rep;

  // decided pairs stop counting as problems
  const before: Record<string, number> = {};
  for (const r of rep.rules) {
    before[r.id] = r.violations;
    const ent = DUP_RULE[r.id];
    if (!ent) continue;
    const all = dups.pairs.filter((p: Json) => p.entity === ent).length;
    const open = dups.pairs.filter((p: Json) => p.entity === ent && !p.decision).length;
    r.violations = all ? Math.round((r.violations * open) / all) : r.violations;
  }
  const removed = Object.values(before).reduce((n, v) => n + v, 0) - rep.rules.reduce((n: number, r: Json) => n + r.violations, 0);
  rep.rules = rep.rules.filter((r: Json) => r.violations > 0);
  const live = new Map(rep.rules.map((r: Json) => [r.id, r.violations]));
  for (const c of rep.standard_checks) {
    if (c.status === "not_run") continue;
    const failing = c.failing_rule_ids.filter((id: string) => live.has(id));
    const was = c.violations;
    c.violations = failing.reduce((n: number, id: string) => n + (live.get(id) as number), 0);
    c.records = was ? Math.round((c.records * c.violations) / was) : 0;
    c.failing_rule_ids = failing;
    c.rules_failing = failing.length;
    c.status = failing.length ? "fail" : "pass";
  }
  rep.totals.violations = rep.rules.reduce((n: number, r: Json) => n + r.violations, 0);
  rep.totals.affected_records = Math.max(0, rep.totals.affected_records - removed);
  rep.totals.failed = rep.rules.length;
  rep.totals.passed = rep.totals.rules - rep.totals.failed;
  rep.totals.clean_records_pct = rep.totals.rows ? Math.round(1000 * (1 - rep.totals.affected_records / rep.totals.rows)) / 10 : null;
  rep.duplicate_review = { total, merged, not_duplicate: kept, to_review: total - merged - kept };
  return rep;
}

/** Answers an API call from the demo snapshot. */
export async function demoApi<T>(path: string, init?: RequestInit): Promise<T> {
  const url = new URL(path, "http://demo");
  const p = url.pathname;
  await new Promise((r) => setTimeout(r, 250)); // feel like a real request
  if (p === "/dq/sources") {
    return [{ id: "legacy", label: "Sample legacy CRM", detail: "Generated recruitment CRM with planted problems", available: true }] as T;
  }
  if (p === "/dq/report") return (await report()) as T;
  if (p.startsWith("/dq/rules/")) return (await file(`rules/${decodeURIComponent(p.slice("/dq/rules/".length))}.json`)) as T;
  if (p === "/dq/duplicates") return (await duplicates(url.searchParams.get("entity"))) as T;
  if (p === "/dq/duplicates/decision" && init?.method === "POST") {
    const body = JSON.parse(String(init.body ?? "{}"));
    const all = decisions();
    const [entity, a, b] = String(body.key).split(":");
    if (body.decision === "undecided") delete all[body.key];
    else all[body.key] = { decision: body.decision, entity, a, b, keep: body.keep ?? null, fields: body.fields ?? {}, by: "demo visitor", at: new Date().toISOString().slice(0, 19) };
    saveDecisions(all);
    return { key: body.key, decision: all[body.key] ?? null } as T;
  }
  throw new Error("This isn’t available in the demo.");
}

/** Source tables shown as already uploaded, so the demo opens with data in place. */
export async function demoUploads() {
  return (await file("uploads.json")) as { name: string; rows: number; size: number; columns: number }[];
}
