"use client";

// Version review on Dolt: every middle-tier / target run and every field change is a version.
// Each version shows the change made; a merge shows both records and the record they became.
// API: GET /versions (backend/app/versions.py)
import { useEffect, useState } from "react";
import { PageHeader, Shell, Spinner } from "../../components/ui";
import { api } from "../../lib/api";

type Stat = { table: string; added: number; deleted: number; modified: number };
type Count = { table: string; rows: number | null };
type Recon = { entity: string; source: Count[]; middle: Count; target: Count[] };
type Row = Record<string, string | null>;
type Merge = { entity: string; id_column: string; kept: Row | null; duplicate: Row | null; merged: Row | null; taken_from_duplicate: string[] };
type Commit = { hash: string; message: string; date: string; tables: Stat[]; counts: Recon[]; merges: Merge[] };
type Log = { available: boolean; commits: Commit[] };


export default function VersionsPage() {
  const [log, setLog] = useState<Log | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => { api<Log>("/versions").then(setLog).catch((e: Error) => setError(e.message)); }, []);
  const commits = log?.commits ?? [];
  const idx = Math.max(0, commits.findIndex((c) => c.hash === active));
  const commit = commits[idx];

  return (
    <Shell>
      <PageHeader title="Version review" />
      {error ? <p className="card p-5 text-[13px] text-bad">{error}</p> : !log ? (
        <div className="card p-10 grid place-items-center"><Spinner className="w-6 h-6 text-accent" /></div>
      ) : !log.available || commits.length === 0 ? (
        <div className="card p-6 text-[13px] text-muted">No version review yet.</div>
      ) : (
        <div className="card overflow-hidden grid md:grid-cols-[280px_1fr] min-h-[620px]">
          <nav aria-label="Versions" className="border-b md:border-b-0 md:border-r border-line bg-[#F5F8FF]">
            <ul className="p-2 space-y-0.5">
              {commits.map((c, i) => (
                <li key={c.hash}>
                  <button onClick={() => setActive(c.hash)}
                    className={`w-full text-left rounded-lg px-3 py-2 ${c.hash === commit?.hash ? "bg-surface shadow-card border border-line" : "border border-transparent hover:bg-sunken"}`}>
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-muted">v{commits.length - i}</span>
                      <span className="text-[13px] font-medium truncate flex-1">{c.message}</span>
                    </span>
                    <span className="block text-[11.5px] text-muted mt-0.5 pl-6">{c.date}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>

          <section className="min-w-0 flex flex-col">
            <div className="px-5 pt-4 pb-3 border-b border-line">
              <h2 className="text-[17px] font-semibold">{commit.message}</h2>
            </div>

            {commit.merges.length > 0 ? commit.merges.map((m, i) => <MergeView key={i} m={m} />) : <Summary c={commit} />}

          </section>
        </div>
      )}
    </Shell>
  );
}

// Two records merged into one: both as they were, side by side, and the record they became.
function MergeView({ m }: { m: Merge }) {
  const cols = Object.keys(m.merged ?? m.kept ?? m.duplicate ?? {});
  const v = (r: Row | null, c: string) => r?.[c] ?? null;
  return (
    <div className="px-5 pt-4">
      <h3 className="text-[13px] font-semibold mb-2">{m.entity}: two records merged into one</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-[12.5px]">
          <thead>
            <tr>
              <th className="th pl-0">Field</th>
              <th className="th">Record {v(m.kept, m.id_column)}</th>
              <th className="th">Record {v(m.duplicate, m.id_column)}</th>
              <th className="th">Merged record</th>
            </tr>
          </thead>
          <tbody>
            {cols.map((c) => {
              const a = v(m.kept, c), b = v(m.duplicate, c), r = v(m.merged, c);
              const differs = a !== b;
              return (
                <tr key={c} className={differs ? "bg-warn-soft/30" : ""}>
                  <td className="td pl-0 font-mono text-[11.5px]">{c}</td>
                  <td className={`td ${differs && r === a ? "font-semibold" : ""}`}>{a ?? <span className="text-faint">—</span>}</td>
                  <td className={`td ${differs && r === b ? "font-semibold" : ""}`}>{b ?? <span className="text-faint">—</span>}</td>
                  <td className="td font-medium">{r ?? <span className="text-faint">—</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// A version without merges: what it did, then an audit trail of source tables read and target tables loaded.
function Summary({ c }: { c: Commit }) {
  const sum = (k: "added" | "modified" | "deleted") => c.tables.reduce((n, t) => n + t[k], 0);
  const tables = c.tables.filter((t) => t.added || t.modified || t.deleted).length;
  const [added, changed, removed] = [sum("added"), sum("modified"), sum("deleted")];
  const parts = [added && `${added.toLocaleString()} rows added`, changed && `${changed.toLocaleString()} changed`, removed && `${removed.toLocaleString()} removed`].filter(Boolean);
  // one line per source table (or set of tables), each target table listed once
  const groups = new Map<string, { source: Count[]; target: Count[] }>();
  for (const r of c.counts.filter((x) => x.target.length > 0)) {
    const k = r.source.map((x) => x.table).join(", ");
    const g = groups.get(k) ?? { source: r.source, target: [] };
    for (const t of r.target) if (!g.target.some((x) => x.table === t.table)) g.target.push(t);
    groups.set(k, g);
  }
  const audit = [...groups.entries()].map(([entity, g]) => ({ entity, ...g }));
  const uniq = (list: Count[]) => [...new Map(list.map((x) => [x.table, x.rows ?? 0])).values()].reduce((n, v) => n + v, 0);
  const totalSource = uniq(audit.flatMap((r) => r.source));
  const totalTarget = uniq(audit.flatMap((r) => r.target));
  return (
    <>
      <p className="px-5 pt-4 text-[13px]">
        {parts.length ? <>{parts.join(", ")} across {tables} table{tables === 1 ? "" : "s"}.</> : "No data changed."}
      </p>
      {audit.length > 0 && (
        <div className="px-5 pt-4 pb-5 overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr>
                <th className="th pl-0">Source table</th><th className="th text-right">Rows read</th>
                <th className="th">Target table</th><th className="th text-right">Rows loaded</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((r) => r.target.map((t, i) => (
                <tr key={`${r.entity}-${t.table}`} className={i === 0 ? "border-t border-line" : ""}>
                  {i === 0 && (
                    <>
                      <td className="td pl-0 font-mono align-top" rowSpan={r.target.length}>{r.source.map((x) => x.table).join(", ")}</td>
                      <td className="td text-right tabular-nums align-top" rowSpan={r.target.length}>{r.source.reduce((m, x) => m + (x.rows ?? 0), 0).toLocaleString()}</td>
                    </>
                  )}
                  <td className="td font-mono">{t.table}</td>
                  <td className="td text-right tabular-nums">{t.rows == null ? "—" : t.rows.toLocaleString()}</td>
                </tr>
              )))}
              <tr className="font-semibold">
                <td className="td pl-0">Total</td><td className="td text-right tabular-nums">{totalSource.toLocaleString()}</td>
                <td className="td" /><td className="td text-right tabular-nums">{totalTarget.toLocaleString()}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
