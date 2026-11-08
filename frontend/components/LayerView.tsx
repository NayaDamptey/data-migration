"use client";

// The two script layers of the migration (engine/mapping/tiers.py):
//   middle: source -> Migration_Staging.mid.<Entity>     (Schema mapping page)
//   target: mid -> RecruitPlatform_Target.dbo.<Table>     (Destination data page)
// LayerData shows a layer's tables; LayerScripts shows each table's INSERT script and lets a developer
// change any field's expression (saved, re-run on SQL Server, undone if it fails).
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Spinner } from "./ui";

type Field = { column: string; expression: string; default: string; overridden: boolean };
type LayerEntity = {
  key: string; label: string; table: string; file: string; sources: string[]; rows: number | null;
  inserts: { n: number; source: string; fields: Field[] }[]; sql: string;
};
export type LayerDetail = { layer: string; source_db: string; db: string; entities: LayerEntity[] };
type Rows = { total: number; matched: number; rows: Record<string, string | null>[] };

const useLayer = (layer: string) => {
  const [detail, setDetail] = useState<LayerDetail | null>(null);
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setDetail(null); setCounts(null); setError(null);
    api<LayerDetail>(`/layers/${layer}`).then(setDetail).catch((e: Error) => setError(e.message));
    api<{ entities: Record<string, number> }>(`/layers/${layer}/summary`).then((s) => setCounts(s.entities)).catch((e: Error) => setError(e.message));
  }, [layer]);
  return { detail, setDetail, counts, error, setError };
};

function EntityNav({ detail, counts, active, onPick }: { detail: LayerDetail; counts: Record<string, number> | null; active: string; onPick: (k: string) => void }) {
  return (
    <nav aria-label="Entities" className="border-b md:border-b-0 md:border-r border-line bg-[#F5F8FF]">
      <p className="px-4 pt-4 pb-3 text-[12px] text-muted font-mono">{detail.source_db} → {detail.db}</p>
      <ul className="px-2 pb-4 space-y-0.5">
        {detail.entities.map((e) => (
          <li key={e.key}>
            <button onClick={() => onPick(e.key)}
              className={`w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] ${e.key === active ? "bg-surface shadow-card border border-line font-medium" : "border border-transparent hover:bg-sunken text-ink/80"}`}>
              <span className="flex-1">{e.label}</span>
              <span className="text-[11px] text-muted tabular-nums">{counts?.[e.key]?.toLocaleString() ?? ""}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

const Loading = ({ error }: { error: string | null }) => (
  <div className="card p-10 grid place-items-center">{error ? <p className="text-bad text-[13px]">{error}</p> : <Spinner className="w-6 h-6 text-accent" />}</div>
);

export function LayerData({ layer, initial }: { layer: string; initial?: string }) {
  const { detail, counts, error } = useLayer(layer);
  const [active, setActive] = useState<string | null>(initial ?? null);
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Rows | null>(null);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const key = active ?? detail?.entities[0]?.key ?? null;
  const q = query.trim();

  useEffect(() => {
    if (!key) return;
    setData(null); setRowsError(null);
    const t = setTimeout(() => {
      api<Rows>(`/layers/${layer}/${encodeURIComponent(key)}/rows?limit=2000${q ? `&q=${encodeURIComponent(q)}` : ""}`)
        .then(setData).catch((e: Error) => setRowsError(e.message));
    }, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [layer, key, q]);

  if (!detail || !key) return <Loading error={error} />;
  const e = detail.entities.find((x) => x.key === key)!;
  const cols = e.inserts[0].fields.map((f) => f.column);

  return (
    <div className="card overflow-hidden grid md:grid-cols-[230px_1fr] min-h-[620px]">
      <EntityNav detail={detail} counts={counts} active={key} onPick={(k) => { setActive(k); setQuery(""); }} />
      <section className="flex flex-col min-w-0">
        <div className="px-5 pt-4 pb-3 border-b border-line flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-[17px] font-semibold">{e.label}</h2>
            <p className="text-[12px] text-muted font-mono mt-0.5">{e.table}{data ? ` · ${data.total.toLocaleString()} rows` : ""}</p>
          </div>
          <input value={query} onChange={(ev) => setQuery(ev.target.value)} placeholder="Search records" aria-label="Search records" className="field h-8 text-[13px] w-full sm:w-[240px]" />
        </div>
        {rowsError ? <p className="p-5 text-[13px] text-bad">{rowsError}</p> : !data ? (
          <div className="flex-1 grid place-items-center py-16"><Spinner className="w-5 h-5 text-accent" /></div>
        ) : (
          <>
            <div className="flex-1 overflow-auto max-h-[640px] mx-5 mt-4 mb-2">
              <table className="text-[12px] border border-line border-separate border-spacing-0">
                <thead className="sticky top-0 bg-surface"><tr>{cols.map((c) => <th key={c} className="th font-mono text-[11px]">{c}</th>)}</tr></thead>
                <tbody>
                  {data.rows.map((r, i) => (
                    <tr key={i} className="hover:bg-[#F5F8FF]">
                      {cols.map((c) => <td key={c} className="td whitespace-nowrap max-w-[260px] truncate" title={r[c] ?? undefined}>{r[c] ?? <span className="text-faint">—</span>}</td>)}
                    </tr>
                  ))}
                  {data.rows.length === 0 && <tr><td colSpan={cols.length} className="px-4 py-10 text-center text-muted">No records{q ? ` match “${q}”` : ""}.</td></tr>}
                </tbody>
              </table>
            </div>
            <p className="px-5 pb-4 text-[12px] text-muted">Showing {data.rows.length.toLocaleString()} of {(q ? data.matched : data.total).toLocaleString()}{q ? " matching" : ""} records</p>
          </>
        )}
      </section>
    </div>
  );
}

export function LayerScripts({ layer, initial }: { layer: string; initial?: string }) {
  const { detail, setDetail, counts, error, setError } = useLayer(layer);
  const [active, setActive] = useState<string | null>(initial ?? null);
  const [saving, setSaving] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<{ key: string; msg: string } | null>(null);

  if (!detail) return <Loading error={error} />;
  const e = detail.entities.find((x) => x.key === active) ?? detail.entities[0];

  const saveField = async (n: number, column: string, expression: string | null) => {
    const k = `${n}:${column}`;
    setSaving(k); setFieldError(null); setError(null);
    try {
      setDetail(await api<LayerDetail>(`/layers/${layer}/${encodeURIComponent(e.key)}/fields`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ insert: n, column, expression }),
      }));
    } catch (ex) {
      const m = (ex as Error).message;
      let detail: string | undefined;
      try { detail = JSON.parse(m.slice(m.indexOf("{"))).detail; } catch { /* not JSON */ }
      setFieldError({ key: k, msg: detail ? `SQL Server: ${detail.replace(/\s*\(\d+\)$/, "")}` : m });
    }
    finally { setSaving(null); }
  };

  return (
    <div className="card overflow-hidden grid md:grid-cols-[230px_1fr] min-h-[620px]">
      <EntityNav detail={detail} counts={counts} active={e.key} onPick={(k) => { setActive(k); setFieldError(null); }} />
      <section className="min-w-0 flex flex-col">
        <div className="px-5 pt-4 pb-3 border-b border-line">
          <h2 className="text-[17px] font-semibold">{e.label}</h2>
          <p className="text-[12px] text-muted mt-0.5 font-mono">{e.sources.join(", ")} → {e.table}</p>
        </div>

        {e.inserts.map((ins) => (
          <div key={`${e.key}-${ins.n}`} className="px-5 pt-4">
            {e.inserts.length > 1 && <p className="text-[12px] font-mono text-muted mb-1">INSERT {ins.n + 1} · FROM {ins.source}</p>}
            <table className="w-full text-[12.5px]">
              <thead><tr><th className="th pl-0 w-[220px]">Column</th><th className="th">Expression</th></tr></thead>
              <tbody>
                {ins.fields.map((f) => {
                  const k = `${ins.n}:${f.column}`;
                  return (
                    <tr key={k}>
                      <td className="td pl-0 font-mono align-top pt-3">{f.column}</td>
                      <td className="td align-top">
                        <ExpressionInput key={`${e.key}-${k}-${f.expression}`} value={f.expression} busy={saving === k}
                          onSave={(v) => saveField(ins.n, f.column, v)} />
                        {f.overridden && (
                          <button className="text-[11.5px] text-accent hover:underline mt-1" onClick={() => saveField(ins.n, f.column, null)}>
                            Reset to <span className="font-mono">{f.default}</span>
                          </button>
                        )}
                        {fieldError?.key === k && <p className="text-[12px] text-bad mt-1">{fieldError.msg}</p>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}

        <div className="m-5 bg-nav font-mono text-[12.5px] leading-[1.7]">
          <div className="flex items-center gap-2 px-4 h-9 border-b border-nav-line text-[11.5px] text-nav-text">
            <span className="text-white">{e.file}</span>
          </div>
          <pre className="overflow-auto px-4 py-3 text-[#D6E0F5] whitespace-pre">{e.sql}</pre>
        </div>
      </section>
    </div>
  );
}

function ExpressionInput({ value, busy, onSave }: { value: string; busy: boolean; onSave: (v: string) => void }) {
  const [text, setText] = useState(value);
  const dirty = text.trim() !== value;
  return (
    <form className="flex items-center gap-2" onSubmit={(ev) => { ev.preventDefault(); if (dirty) onSave(text); }}>
      <input value={text} onChange={(ev) => setText(ev.target.value)} spellCheck={false} aria-label="Expression"
        className={`field h-8 text-[12px] font-mono flex-1 ${dirty ? "border-accent" : ""}`} />
      {busy ? <Spinner className="text-accent" /> : dirty && (
        <>
          <button type="submit" className="btn-primary h-8 px-3 text-[12px]">Save</button>
          <button type="button" className="btn-ghost h-8 px-2 text-[12px]" onClick={() => setText(value)}>Cancel</button>
        </>
      )}
    </form>
  );
}

// Data / Developer view switch, remembered per page
export type View = "data" | "developer";

export function ViewToggle({ view, onChange, dataLabel }: { view: View; onChange: (v: View) => void; dataLabel: string }) {
  return (
    <div role="tablist" aria-label="View" className="inline-flex p-0.5 rounded-lg bg-sunken border border-line">
      {([["data", dataLabel], ["developer", "Developer view"]] as [View, string][]).map(([v, label]) => (
        <button key={v} role="tab" aria-selected={view === v} onClick={() => onChange(v)}
          className={`h-8 px-3 rounded-md text-[13px] flex items-center gap-1.5 transition-colors ${view === v ? "bg-surface shadow-card font-medium text-ink" : "text-muted hover:text-ink"}`}>
          {v === "developer" && <span className="font-mono text-[11px] opacity-70">{"</>"}</span>}
          {label}
        </button>
      ))}
    </div>
  );
}

export function useView(storageKey: string) {
  const [view, setView] = useState<View>("data");
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("view");
    if (fromUrl === "developer" || fromUrl === "data") { setView(fromUrl); return; }
    try { if (localStorage.getItem(storageKey) === "developer") setView("developer"); } catch {}
  }, [storageKey]);
  const change = (v: View) => { setView(v); try { localStorage.setItem(storageKey, v); } catch {} };
  return [view, change] as const;
}
