"use client";

// Shared workflow pieces: source/destination panels, pipeline steps, run history, change requests.
import { useState, type ReactNode } from "react";
import { Check, Spinner, SystemTile } from "./ui";
import { useStore, type StepState } from "../lib/store";

export function Panel({ title, tag, system, status, children }: { title: string; tag: string; system: string; status: string; children: ReactNode }) {
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

export function Step({ n, title, desc, state, action, extra }: { n: number; title: string; desc: string; state: StepState; action: ReactNode; extra?: ReactNode }) {
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

export function Versions() {
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

export function ChangeRequests({ onSent }: { onSent: () => void }) {
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
