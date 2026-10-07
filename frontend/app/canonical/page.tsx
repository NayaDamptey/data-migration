"use client";

// Screen 3: Canonical layer. Sketch: docs/sketches/3-canonical-fields.jpeg
// Left: 10 entities. Right, two views:
//   Extracted data (default): the records as they sit in the canonical layer.
//   Developer view: the schema mapping (canonical field | source column | transform |
//   sample | confidence | status). Reviewer can accept or flag mappings.
// API (later): GET /runs/:id/canonical/:entity, POST /runs/:id/reviews
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useState } from "react";
import { JoinsPanel } from "../../components/JoinsPanel";
import { TransformDrill } from "../../components/TransformDrill";
import { Check, PageHeader, Shell, Spinner, StatusPill, Toast } from "../../components/ui";
import { CANONICAL_ROWS, ENTITIES, SOURCE_COLUMNS, sourceSample, suggestJoin, type Entity, type FieldStatus, type Join } from "../../lib/mock";
import { useStore } from "../../lib/store";

type View = "data" | "developer";
type Filter = "all" | FieldStatus;

export default function CanonicalPage() {
  const router = useRouter();
  const { fieldStatus, changedFields, steps, runStep, canonicalApproved, approveCanonical } = useStore();
  const [active, setActive] = useState("candidates");
  const [view, setView] = useState<View>("data");
  const [toast, setToast] = useState<string | null>(null);

  // Remember the chosen view per browser; developers usually want to land on their view
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("view");
    if (fromUrl === "developer" || fromUrl === "data") { setView(fromUrl); return; }
    try { if (localStorage.getItem("canonical-view") === "developer") setView("developer"); } catch {}
  }, []);
  const changeView = (v: View) => {
    setView(v);
    try { localStorage.setItem("canonical-view", v); } catch {}
  };

  const entity = ENTITIES.find((e) => e.key === active)!;
  const statusCounts = (e: Entity) => {
    const s = e.fields.map((f) => fieldStatus(e.key, f.name));
    return { total: s.length, mapped: s.filter((x) => x === "mapped").length, review: s.filter((x) => x === "review").length, unmapped: s.filter((x) => x === "unmapped").length };
  };
  const totalReview = ENTITIES.reduce((n, e) => n + statusCounts(e).review, 0);
  const totalRecords = ENTITIES.reduce((n, e) => n + e.rows, 0);

  return (
    <Shell>
      <PageHeader
        title="Canonical layer"
        sub={view === "data"
          ? `Your data after extraction, in one standard shape. ${totalRecords.toLocaleString()} records across ${ENTITIES.filter((e) => e.rows).length} entities.`
          : undefined}
        actions={
          <div className="flex items-center gap-3">
            {totalReview > 0
              ? <button onClick={() => changeView("developer")} className="pill bg-warn-soft text-warn h-7 px-3 hover:brightness-95">{totalReview} mappings need review</button>
              : <span className="pill bg-ok-soft text-ok h-7 px-3"><Check /> All reviewed</span>}
            <div role="tablist" aria-label="View" className="inline-flex p-0.5 rounded-lg bg-sunken border border-line">
              {([["data", "Extracted data"], ["developer", "Developer view"]] as [View, string][]).map(([v, label]) => (
                <button
                  key={v}
                  role="tab"
                  aria-selected={view === v}
                  onClick={() => changeView(v)}
                  className={`h-8 px-3 rounded-md text-[13px] flex items-center gap-1.5 transition-colors ${view === v ? "bg-surface shadow-card font-medium text-ink" : "text-muted hover:text-ink"}`}
                >
                  {v === "developer" && <span className="font-mono text-[11px] opacity-70">{"</>"}</span>}
                  {label}
                </button>
              ))}
            </div>
          </div>
        }
      />

      {changedFields > 0 && (
        <div className="mb-4 rounded-lg bg-accent-soft text-accent-ink px-4 py-2.5 text-[13px] flex flex-wrap items-center justify-between gap-2">
          <span>You’ve changed {changedFields} mapping{changedFields > 1 ? "s" : ""}. Re-run the canonical layer to apply {changedFields > 1 ? "them" : "it"} to the data.</span>
          <button
            className="btn-primary h-8 text-[12px]"
            disabled={steps.canonical === "running"}
            onClick={async () => { await runStep("canonical"); setToast("Canonical layer re-run with your changes"); setTimeout(() => setToast(null), 2400); }}
          >
            {steps.canonical === "running" ? <Spinner /> : "Re-run canonical layer"}
          </button>
        </div>
      )}

      <div className="card overflow-hidden grid md:grid-cols-[230px_1fr] min-h-[620px]">
        <nav aria-label="Entities" className="border-b md:border-b-0 md:border-r border-line bg-[#F5F8FF]">
          <p className="px-4 pt-4 pb-2 text-[12px] font-medium text-muted">Entities</p>
          <ul className="flex md:block overflow-x-auto pb-2 md:pb-4 px-2 gap-1">
            {ENTITIES.map((e) => {
              const k = statusCounts(e);
              const on = e.key === active;
              return (
                <li key={e.key} className="shrink-0">
                  <button
                    onClick={() => setActive(e.key)}
                    className={`w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] transition-colors ${on ? "bg-surface shadow-card border border-line font-medium" : "border border-transparent hover:bg-sunken text-ink/80"}`}
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0 ${e.rows === 0 ? "bg-faint/50" : view === "developer" && k.review ? "bg-warn" : "bg-ok"}`} />
                    <span className="flex-1">{e.label}</span>
                    <span className="text-[11px] text-muted tabular-nums">
                      {view === "data" ? (e.rows ? compact(e.rows) : "—") : `${k.mapped}/${k.total}`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <section className="flex flex-col min-w-0">
          {view === "data" ? <DataView entity={entity} /> : <DeveloperView entity={entity} counts={statusCounts(entity)} />}
          <div className="flex flex-wrap items-center justify-end gap-2 px-5 py-4 border-t border-line bg-[#F5F8FF]">
            {canonicalApproved ? (
              <>
                <span className="mr-auto flex items-center gap-1.5 text-[13px] font-medium text-ok"><Check /> Canonical model approved</span>
                <button className="btn-secondary" onClick={() => router.push("/workspace")}>Back to setup</button>
                <button className="btn-primary" onClick={() => router.push("/target")}>Next: Destination data →</button>
              </>
            ) : (
              <>
                {totalReview > 0 && <span className="mr-auto text-[12px] text-muted">{totalReview} mapping{totalReview > 1 ? "s" : ""} still marked “Needs review”. You can approve anyway.</span>}
                <button className="btn-secondary" onClick={() => router.push("/workspace")}>Cancel</button>
                <button className="btn-primary min-w-[96px]" onClick={() => { approveCanonical(); setToast("Canonical model approved"); setTimeout(() => setToast(null), 2200); }}>Approve</button>
              </>
            )}
          </div>
        </section>
      </div>
      <Toast message={toast} />
    </Shell>
  );
}

const compact = (n: number) => (n >= 10_000 ? `${Math.round(n / 1000)}k` : n.toLocaleString());

// ---- Extracted data ----

function DataView({ entity }: { entity: Entity }) {
  const { fieldStatus, isChanged } = useStore();
  const [query, setQuery] = useState("");
  const rows = CANONICAL_ROWS[entity.key] ?? [];
  const q = query.trim().toLowerCase();
  const shown = q ? rows.filter((r) => Object.values(r).some((v) => v?.toLowerCase().includes(q))) : rows;
  const label = (name: string) => name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

  return (
    <>
      <div className="px-5 pt-4 pb-3 border-b border-line flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h2 className="text-[17px] font-semibold">{entity.label}</h2>
            <span className="text-[12px] text-muted">{entity.rows ? `${entity.rows.toLocaleString()} records` : "No records"}</span>
          </div>
          <p className="text-[13px] text-muted mt-0.5">{entity.description}</p>
        </div>
        {rows.length > 0 && (
          <div className="relative w-full sm:w-[240px]">
            <label htmlFor="search" className="sr-only">Search records</label>
            <input id="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search records" className="field h-8 pl-8 text-[13px]" />
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" width="14" height="14" viewBox="0 0 14 14" aria-hidden>
              <circle cx="6" cy="6" r="4.25" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="m9.5 9.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
        )}
      </div>

      {rows.length === 0 ? (
        <div className="flex-1 grid place-items-center px-6 py-16 text-center">
          <div className="max-w-[360px]">
            <p className="font-medium">Nothing was extracted for {entity.label.toLowerCase()}</p>
            <p className="text-[13px] text-muted mt-1">{entity.fields[0]?.note ?? "No source table matched this entity."}</p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-x-auto px-5 pt-4 pb-2">
            <table className="text-[12px] border border-line rounded-lg border-separate border-spacing-0 overflow-hidden">
              <thead>
                <tr>
                  {entity.fields.map((f) => {
                    const review = fieldStatus(entity.key, f.name) === "review";
                    const changed = isChanged(entity.key, f.name);
                    return (
                      <th
                        key={f.name}
                        className={`th ${changed ? "bg-accent-soft" : review ? "bg-warn-soft/70" : ""}`}
                        title={changed ? "Mapping changed. Re-run the canonical layer to refresh this column." : review ? "This column’s mapping still needs review (see Developer view)" : undefined}
                      >
                        {label(f.name)}
                        {changed ? <span className="text-accent ml-1">✎</span> : review && <span className="text-warn ml-1">•</span>}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {shown.map((r, i) => (
                  <tr key={i} className="hover:bg-[#F5F8FF]">
                    {entity.fields.map((f) => {
                      const v = r[f.name] ?? null;
                      const review = fieldStatus(entity.key, f.name) === "review";
                      return (
                        <td key={f.name} className={`td whitespace-nowrap max-w-[260px] truncate ${review ? "bg-warn-soft/30" : ""}`} title={v ?? undefined}>
                          {v === null ? <span className="text-faint">—</span> : v}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {shown.length === 0 && (
                  <tr><td colSpan={entity.fields.length} className="px-4 py-10 text-center text-muted">No records match “{query}”.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="px-5 pb-4 flex flex-wrap justify-between gap-2 text-[12px] text-muted">
            <span>Showing {shown.length} of {entity.rows.toLocaleString()} records</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-warn-soft border border-warn/30" /> Column still being reviewed</span>
          </div>
        </>
      )}
    </>
  );
}

// ---- Developer view: schema mapping ----

function DeveloperView({ entity, counts: c }: { entity: Entity; counts: { total: number; mapped: number; review: number; unmapped: number } }) {
  const router = useRouter();
  const { fieldStatus, setFieldStatus, fieldSource, setFieldSource, resetField, isChanged, joins, setJoins } = useStore();
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => { setFilter("all"); setOpen(null); }, [entity.key]);
  const fields = entity.fields.filter((f) => filter === "all" || fieldStatus(entity.key, f.name) === filter);
  const inQuery = entity.sourceTable ? [entity.sourceTable, ...joins(entity.key).map((j) => j.table)] : [];

  // Picking a column from a table that isn't joined yet adds the join (by key match when one exists)
  const pickSource = (field: string, value: string | null) => {
    const table = value?.split(".")[0];
    if (table && entity.sourceTable && !inQuery.includes(table)) {
      const s = suggestJoin(inQuery, table);
      const cols = SOURCE_COLUMNS[table];
      const join: Join = s
        ? { ...s, id: `j${Date.now()}`, matched: -1 }
        : { id: `j${Date.now()}`, table, type: "left", on: [{ left: `${entity.sourceTable}.${SOURCE_COLUMNS[entity.sourceTable][0].name}`, right: cols[0].name }], cardinality: "one_to_many", pick: { rule: "latest", orderBy: cols[0].name }, matched: -1 };
      setJoins(entity.key, [...joins(entity.key), join]);
      setNotice(s
        ? `Joined ${table} on ${join.on[0].left} = ${table}.${join.on[0].right}. Check the join in Source tables.`
        : `Joined ${table}, but no matching key was found. Set the join keys in Source tables.`);
      setTimeout(() => setNotice(null), 5000);
    }
    setFieldSource(entity.key, field, value);
  };

  return (
    <>
      <div className="px-5 pt-4 pb-3 border-b border-line">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-[17px] font-semibold">{entity.label}</h2>
          <span className="text-[12px] text-muted font-mono">
            {entity.sourceTable ? `${entity.sourceTable} → canonical.${entity.key}` : `? → canonical.${entity.key}`}
          </span>
        </div>
        <p className="text-[13px] text-muted mt-0.5">{entity.description}</p>

        <div className="mt-3 h-1.5 rounded-full bg-sunken overflow-hidden flex" aria-hidden>
          <span className="bg-ok" style={{ width: `${(c.mapped / c.total) * 100}%` }} />
          <span className="bg-warn" style={{ width: `${(c.review / c.total) * 100}%` }} />
        </div>

        <div className="flex flex-wrap gap-1 mt-3" role="tablist" aria-label="Filter mappings">
          {([["all", `All ${c.total}`], ["review", `Needs review ${c.review}`], ["mapped", `Mapped ${c.mapped}`], ["unmapped", `Unmapped ${c.unmapped}`]] as [Filter, string][]).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)} className={`h-7 px-3 rounded-full text-[12px] transition-colors ${filter === k ? "bg-ink text-white" : "text-muted hover:bg-sunken"}`}>{label}</button>
          ))}
        </div>
      </div>

      <JoinsPanel entity={entity} />
      {notice && <div role="status" className="mx-5 mt-3 rounded-lg bg-accent-soft text-accent-ink px-3 py-2 text-[12px]">{notice}</div>}

      <div className="flex-1 overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr>
              <th className="th pl-5">Canonical field</th>
              <th className="th">Source column</th>
              <th className="th">Sample</th>
              <th className="th">Confidence</th>
              <th className="th">Status</th>
              <th className="th pr-5 text-right"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {fields.map((f) => {
              const st = fieldStatus(entity.key, f.name);
              const { from, changed: sourceChanged } = fieldSource(entity.key, f.name);
              const changed = isChanged(entity.key, f.name);
              const sample = sourceChanged ? sourceSample(from) : f.sample;
              // The drill-down shows the transform on the column it was designed for
              const drillable = !!f.transform && !!from && !sourceChanged;
              const expanded = open === f.name && drillable;
              return (
                <Fragment key={f.name}>
                  <tr className={`group ${changed ? "bg-accent-soft/40" : st === "review" ? "bg-warn-soft/35" : ""} hover:bg-[#F5F8FF] ${expanded ? "[&>td]:border-b-0" : ""}`}>
                    <td className="td pl-3">
                      <div className="flex items-start gap-1.5">
                        {drillable ? (
                          <button
                            onClick={() => setOpen(expanded ? null : f.name)}
                            aria-expanded={expanded}
                            aria-label={`${expanded ? "Hide" : "Show"} how ${f.name} is transformed`}
                            className="mt-0.5 grid place-items-center w-5 h-5 rounded hover:bg-sunken text-muted"
                          >
                            <svg width="10" height="10" viewBox="0 0 10 10" className={`transition-transform ${expanded ? "rotate-90" : ""}`} aria-hidden><path d="M3.5 2 6.5 5l-3 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                          </button>
                        ) : <span className="w-5 shrink-0" />}
                        <div>
                          <div className="font-mono text-[12px] font-medium">{f.name}{f.required && <span className="text-bad ml-0.5" title="Required">*</span>}</div>
                          <div className="text-[11px] text-faint">{f.type}</div>
                        </div>
                      </div>
                    </td>
                    <td className="td min-w-[250px]">
                      <SourcePicker
                        id={`src-${entity.key}-${f.name}`}
                        label={`Source column for ${f.name}`}
                        value={from}
                        inQuery={inQuery}
                        onChange={(v) => pickSource(f.name, v)}
                      />
                      {sourceChanged ? (
                        <div className="text-[11px] text-accent mt-1">
                          Changed by you{f.from ? <> · was <span className="font-mono">{f.from}</span></> : null}
                          {f.transform && from && <span className="text-muted"> · check whether {f.transform.replace(/_/g, " ")} still applies</span>}
                        </div>
                      ) : (
                        <>
                          {f.transform && (
                            <button onClick={() => setOpen(expanded ? null : f.name)} className="text-[11px] text-accent mt-1 font-mono hover:underline block">
                              ↳ {f.transform}(){changed && <span className="font-sans not-italic"> · settings changed</span>}
                            </button>
                          )}
                          {f.note && <div className="text-[12px] text-muted mt-1 max-w-[280px]">{f.note}</div>}
                        </>
                      )}
                    </td>
                    <td className="td text-muted max-w-[220px]"><span className="block truncate font-mono text-[12px]" title={sample}>{sample}</span></td>
                    <td className="td">{changed ? <span className="text-[12px] text-accent">Set by you</span> : <Confidence value={f.confidence} />}</td>
                    <td className="td"><StatusPill status={st} /></td>
                    <td className="td pr-5 text-right whitespace-nowrap">
                      {changed && <button className="btn-ghost h-7 px-2.5 text-[12px]" onClick={() => resetField(entity.key, f.name)}>Reset</button>}
                      {!changed && st !== "mapped" && from && (
                        <button className="btn-secondary h-7 px-2.5 text-[12px]" onClick={() => setFieldStatus(entity.key, f.name, "mapped")}>Accept</button>
                      )}
                      {!changed && st === "mapped" && from && (
                        <button className="btn-ghost h-7 px-2.5 text-[12px] opacity-0 group-hover:opacity-100 focus:opacity-100" onClick={() => setFieldStatus(entity.key, f.name, "review")}>Flag</button>
                      )}
                      {!from && <button className="btn-ghost h-7 px-2.5 text-[12px]" onClick={() => router.push("/workspace")}>Ask for it</button>}
                    </td>
                  </tr>
                  {expanded && (
                    <tr className={changed ? "bg-accent-soft/40" : st === "review" ? "bg-warn-soft/35" : ""}>
                      <td colSpan={6} className="px-5 pb-4 pt-1 border-b border-line">
                        <TransformDrill entity={entity.key} field={f} from={from!} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {fields.length === 0 && (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-muted">Nothing here. Try another filter.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** Dropdown of every source column, grouped by table: tables already in the entity's query first. */
function SourcePicker({ id, label, value, inQuery, onChange }: { id: string; label: string; value: string | null; inQuery: string[]; onChange: (v: string | null) => void }) {
  const others = Object.keys(SOURCE_COLUMNS).filter((t) => !inQuery.includes(t)).sort();
  const tables = [...inQuery, ...others];
  return (
    <div className="relative">
      <label htmlFor={id} className="sr-only">{label}</label>
      <select
        id={id}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className={`w-full h-8 rounded-md border bg-surface pl-2.5 pr-7 font-mono text-[12px] appearance-none cursor-pointer transition-colors hover:border-[#B9CBF0] focus:border-accent ${value ? "border-line text-ink" : "border-dashed border-line text-faint"}`}
      >
        <option value="">— Not mapped</option>
        {tables.map((t) => (
          <optgroup key={t} label={t === inQuery[0] ? `${t} (base table)` : inQuery.includes(t) ? `${t} (joined)` : `${t} (not joined yet, picking adds a join)`}>
            {SOURCE_COLUMNS[t].map((c) => <option key={c.name} value={`${t}.${c.name}`}>{t}.{c.name}</option>)}
          </optgroup>
        ))}
      </select>
      <svg className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-faint" width="10" height="10" viewBox="0 0 12 12" aria-hidden>
        <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
  );
}

function Confidence({ value }: { value: number }) {
  if (!value) return <span className="text-faint">—</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.85 ? "bg-ok" : value >= 0.7 ? "bg-warn" : "bg-bad";
  return (
    <div className="flex items-center gap-2" title={`${pct}% confident`}>
      <span className="w-12 h-1.5 rounded-full bg-sunken overflow-hidden"><span className={`block h-full ${color}`} style={{ width: `${pct}%` }} /></span>
      <span className="text-[12px] tabular-nums text-muted">{pct}%</span>
    </div>
  );
}
