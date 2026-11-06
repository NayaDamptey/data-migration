"use client";

// Screen 2: Set up migration. Sketch: docs/sketches/2-setup.jpeg
// Source: system + format (CSV, backup, JSON, API); files are uploaded on /upload
// Target: system + database (MySQL, PostgreSQL, T-SQL) + output (CSV, SQL inserts, API)
// Actions: Inspect · Run canonical layer · Run target · Get data
// Side panel: runs & versions, request a change (plain English)
// API (later): POST /projects, POST /projects/:id/runs
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Check, Select, Shell, Spinner, SystemTile, Toast } from "../../components/ui";
import { ENTITIES, OUTPUTS, SOURCE_FORMATS, SOURCE_SYSTEMS, SOURCE_TABLES, TARGET_DATABASES, TARGET_SYSTEMS } from "../../lib/mock";
import { useStore, type StepState } from "../../lib/store";

export default function WorkspacePage() {
  const router = useRouter();
  const { setup, updateSetup, steps, runStep, uploads, quality } = useStore();
  const [toast, setToast] = useState<string | null>(null);
  const uploaded = uploads.filter((u) => u.status === "uploaded");
  const uploading = uploads.some((u) => ["checking", "queued", "uploading"].includes(u.status));

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400); };
  const review = ENTITIES.flatMap((e) => e.fields).filter((f) => f.status === "review").length;

  return (
    <Shell>
      <div className="grid lg:grid-cols-[1fr_340px] gap-5 items-start">
        <div className="space-y-5 min-w-0">
          {/* Source + target, side by side as in the sketch */}
          <div>
            <Caption title="Connection" />
            <div className="grid md:grid-cols-2 gap-5">
              <Panel title="Source" tag="From" system={setup.sourceSystem} status={uploaded.length ? `${uploaded.length} files connected` : "No files yet"}>
                <Select label="Source system" value={setup.sourceSystem} options={SOURCE_SYSTEMS} onChange={(v) => updateSetup({ sourceSystem: v })} />
                <Select label="Source format" value={setup.sourceFormat} options={SOURCE_FORMATS} onChange={(v) => updateSetup({ sourceFormat: v })}
                  hint={setup.sourceFormat === "CSV files" ? `${uploaded.length} file${uploaded.length === 1 ? "" : "s"} uploaded (step 1 below)` : undefined} />
              </Panel>

              <Panel title="Destination" tag="To" system={setup.targetSystem} status={setup.output === "SQL inserts" ? `${setup.targetDatabase} inserts` : setup.output}>
                <Select label="Target system" value={setup.targetSystem} options={TARGET_SYSTEMS} onChange={(v) => updateSetup({ targetSystem: v })} />
                <Select label="Output" value={setup.output} options={OUTPUTS} onChange={(v) => updateSetup({ output: v })} hint={setup.output === "API push" ? "Records are sent straight to the target system." : undefined} />
                <div className={setup.output === "SQL inserts" ? "" : "opacity-50"}>
                  <Select label="Target database" value={setup.targetDatabase} options={TARGET_DATABASES} onChange={(v) => updateSetup({ targetDatabase: v })} hint={setup.output === "SQL inserts" ? "Insert statements are written in this dialect." : "Only used for SQL inserts."} />
                </div>
              </Panel>
            </div>
          </div>

          {/* Pipeline: upload source -> data quality -> canonical -> target -> get data */}
          <div className="card p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
              <h2 className="section-title">Pipeline</h2>
            </div>
            <ol className="space-y-2">
              <Step n={1} title="Upload source" desc="Upload the source tables as CSV files, folders or a zip." state={uploaded.length ? "done" : uploading ? "running" : "idle"}
                action={<Link href="/" className="btn-secondary w-full">{uploaded.length ? "Manage files" : "Upload files"}</Link>}
                extra={<p className="text-[12px] text-muted">{uploaded.length ? `${uploaded.length} file${uploaded.length === 1 ? "" : "s"} uploaded` : "Upload files to unlock data quality."}</p>} />
              <Step n={2} title="Run data quality" desc="Check for duplicates, orphans and deleted records still in use." state={steps.quality}
                action={<button className="btn-secondary w-full" disabled={steps.quality === "running" || uploading || !uploaded.length} onClick={async () => { await runStep("quality"); flash("Data quality checked"); }}>{steps.quality === "done" ? "Run again" : "Run data quality"}</button>}
                extra={quality && (quality.error
                  ? <p className="text-[12px] text-bad">Couldn’t run the checks: {quality.error}</p>
                  : <Link href="/quality" className="text-[12px] text-accent font-medium hover:underline">{quality.passed} of {quality.total} checks pass{quality.toReview ? ` · ${quality.toReview} duplicates to review` : ""} →</Link>)} />
              <Step n={3} title="Run canonical layer" desc="Map the source into the 10 standard entities." state={steps.canonical}
                action={<button className="btn-secondary w-full" disabled={steps.quality !== "done" || steps.canonical === "running"} onClick={async () => { await runStep("canonical"); flash("Canonical layer ready to review"); }}>{steps.canonical === "done" ? "Run again" : "Run canonical layer"}</button>}
                extra={steps.canonical === "done" && <Link href="/canonical" className="text-[12px] text-accent font-medium hover:underline">Review fields{review ? ` · ${review} need a look` : ""} →</Link>} />
              <Step n={4} title="Run target" desc={`Turn the canonical data into ${setup.targetSystem} format and check it.`} state={steps.target}
                action={<button className="btn-secondary w-full" disabled={steps.canonical !== "done" || steps.target === "running"} onClick={async () => { await runStep("target"); flash("Target values ready"); }}>{steps.target === "done" ? "Run again" : "Run target"}</button>}
                extra={steps.target === "done" && <Link href="/target" className="text-[12px] text-accent font-medium hover:underline">See target values →</Link>} />
              <Step n={5} title="Get data" desc={`Download as ${setup.output === "SQL inserts" ? `${setup.targetDatabase} inserts` : setup.output.toLowerCase()}.`} state="idle"
                action={<button className="btn-primary w-full" disabled={steps.target !== "done"} onClick={() => router.push("/target?get=1")}>Get data</button>} />
            </ol>
          </div>

        </div>

        <aside className="space-y-5 lg:sticky lg:top-[120px]">
          <Versions />
          <ChangeRequests onSent={() => flash("Request sent. It will be in the next run.")} />
        </aside>
      </div>
      <Toast message={toast} />
    </Shell>
  );
}

function Caption({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-3">
      <h2 className="section-title">{title}</h2>
      {sub && <p className="text-[12.5px] text-muted mt-0.5">{sub}</p>}
    </div>
  );
}

function Panel({ title, tag, system, status, children }: { title: string; tag: string; system: string; status: string; children: ReactNode }) {
  return (
    <section className="card">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-line">
        <SystemTile name={system} size={32} />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{tag} · {title}</p>
          <h2 className="text-[14px] font-semibold truncate">{system}</h2>
        </div>
        <span className="pill bg-ok-soft text-ok"><span className="w-1.5 h-1.5 rounded-full bg-current" />{status}</span>
      </div>
      <div className="space-y-4 p-5">{children}</div>
    </section>
  );
}

function Step({ n, title, desc, state, action, extra }: { n: number; title: string; desc: string; state: StepState; action: ReactNode; extra?: ReactNode }) {
  // one row per step: status, what it does (and its result), the action on the right
  return (
    <li className={`border border-line p-4 flex flex-wrap sm:flex-nowrap items-center gap-4 ${state === "done" ? "bg-surface" : "bg-[#F5F8FF]"}`}>
      <span className={`grid place-items-center w-7 h-7 rounded-full text-[12px] font-semibold shrink-0 ${state === "done" ? "bg-ok text-white" : state === "running" ? "bg-accent text-white" : "bg-surface border border-line text-muted"}`}>
        {state === "done" ? <Check /> : state === "running" ? <Spinner className="w-3 h-3" /> : n}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="font-semibold text-[14px]">{title}</h3>
        <p className="text-[12.5px] text-muted mt-0.5">{state === "running" ? "Working on it…" : desc}</p>
        {extra && <div className="mt-1">{extra}</div>}
      </div>
      <div className="w-full sm:w-44 shrink-0">{action}</div>
    </li>
  );
}

// Sync history strip: one bar per run, height = rows processed, like an ETL tool's run chart
const HISTORY = [
  { rows: 161_000, ok: true }, { rows: 164_200, ok: true }, { rows: 0, ok: false }, { rows: 166_900, ok: true },
  { rows: 170_300, ok: true }, { rows: 172_000, ok: true }, { rows: 175_800, ok: true }, { rows: 177_842, ok: true },
];

function Versions() {
  const { runs } = useStore();
  const max = Math.max(...HISTORY.map((h) => h.rows));
  return (
    <section className="card p-5">
      <div className="flex items-end gap-1 h-12 mb-4" aria-label="Rows processed per run">
        {HISTORY.map((h, i) => (
          <span key={i} title={h.ok ? `${h.rows.toLocaleString()} rows` : "Failed"}
            className={`flex-1 ${h.ok ? "bg-ink" : "border border-ink"}`}
            style={h.ok ? { height: `${20 + (h.rows / max) * 80}%` } : { height: "100%", background: "repeating-linear-gradient(135deg, #0B1F4D 0 1px, transparent 1px 5px)" }} />
        ))}
      </div>
      <ul className="space-y-1 border-t border-line pt-3">
        {runs.map((r, i) => (
          <li key={r.id} className={`flex gap-3 rounded-lg px-2 py-2 -mx-2 ${i === 0 ? "bg-accent-soft/60" : ""}`}>
            <span className="font-mono text-[12px] text-muted pt-0.5 w-6">v{r.version}</span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium truncate">{r.label}</p>
              <p className="text-[12px] text-muted">{r.when} · {r.by}</p>
            </div>
            {r.status === "running" ? <Spinner className="text-accent mt-1" /> : i === 0 ? <span className="pill bg-ok-soft text-ok h-fit">Latest</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ChangeRequests({ onSent }: { onSent: () => void }) {
  const { requests, addRequest } = useStore();
  const [text, setText] = useState("");
  return (
    <section className="card p-5">
      <h2 className="font-semibold mb-3">Request a change</h2>
      <form onSubmit={(e) => { e.preventDefault(); if (!text.trim()) return; addRequest(text.trim()); setText(""); onSent(); }}>
        <label htmlFor="cr" className="sr-only">Describe the change</label>
        <textarea id="cr" value={text} onChange={(e) => setText(e.target.value)} rows={3} placeholder="e.g. Put the candidate’s LinkedIn link in the notes" className="field h-auto py-2 resize-none" />
        <div className="flex justify-end mt-2">
          <button type="submit" className="btn-primary" disabled={!text.trim()}>Send request</button>
        </div>
      </form>
      {requests.length > 0 && (
        <details className="group mt-4 border-t border-line pt-3">
          <summary className="flex items-center justify-between cursor-pointer list-none text-[13px] font-medium text-ink py-1 [&::-webkit-details-marker]:hidden">
            Previous requests ({requests.length})
            <svg width="12" height="12" viewBox="0 0 12 12" className="text-muted transition-transform group-open:rotate-180" aria-hidden>
              <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </summary>
          <ul className="mt-3 space-y-2.5">
            {requests.map((r) => (
              <li key={r.id} className="text-[13px]">
                <p>{r.text}</p>
                <p className="text-[12px] text-muted mt-0.5 flex items-center gap-2">
                  <span className={`pill ${r.status === "done" ? "bg-ok-soft text-ok" : "bg-warn-soft text-warn"}`}>{r.status === "done" ? "Done" : "Waiting"}</span>
                  {r.when}
                </p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
