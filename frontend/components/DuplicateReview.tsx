"use client";

// Duplicates tab of the Data quality page: suspected duplicates side by side. For each pair the reviewer
// merges (keeps one record, choosing field by field which values to keep) or keeps both.
// Nothing changes in the source: decisions are saved and applied by the migration.
// API: GET /dq/duplicates, POST /dq/duplicates/decision  (backend/app/routers/dq.py)
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Compare, title, type DecideBody, type Payload } from "./DuplicateCompare";
import { Spinner, Toast } from "./ui";

export function DuplicateReview({ source, entity: initialEntity, onChanged }: { source: string; entity?: string; onChanged?: () => void }) {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [entity, setEntity] = useState<string>(initialEntity ?? "person");
  const [show, setShow] = useState<"to_review" | "decided" | "all">("to_review");
  const [selected, setSelected] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2200); };

  useEffect(() => { if (initialEntity) setEntity(initialEntity); }, [initialEntity]);

  const load = useCallback(() => {
    api<Payload>(`/dq/duplicates?source=${encodeURIComponent(source)}`)
      .then((d) => {
        setData(d);
        // open on a kind that has pairs
        setEntity((cur) => (d.entities[cur]?.total ? cur : Object.entries(d.entities).find(([, e]) => e.total)?.[0] ?? cur));
      })
      .catch((e: Error) => setError(e.message));
  }, [source]);
  useEffect(() => { load(); }, [load]);

  const pairs = useMemo(() => (data?.pairs ?? []).filter((p) => p.entity === entity
    && (show === "all" || (show === "to_review" ? !p.decision : !!p.decision))), [data, entity, show]);
  useEffect(() => {
    if (!pairs.find((p) => p.key === selected)) setSelected(pairs[0]?.key ?? null);
  }, [pairs, selected]);
  const pair = data?.pairs.find((p) => p.key === selected) ?? null;

  const decide = async (body: DecideBody) => {
    try {
      await api(`/dq/duplicates/decision`, { method: "POST", body: JSON.stringify({ source, ...body }) });
      flash(body.decision === "merge" ? "Merged — the migration will load one record" : body.decision === "not_duplicate" ? "Kept both" : "Decision undone");
      const idx = pairs.findIndex((p) => p.key === body.key);
      const next = pairs[idx + 1]?.key ?? pairs[idx - 1]?.key ?? null;
      load();
      onChanged?.();
      if (body.decision !== "undecided" && show === "to_review") setSelected(next);
    } catch (e) {
      flash((e as Error).message);
    }
  };

  const totalLeft = Object.values(data?.entities ?? {}).reduce((n, e) => n + e.to_review, 0);

  if (error) return <div role="alert" className="card p-5 text-[13px]"><p className="font-semibold">Couldn’t load duplicates</p><p className="text-muted mt-1">{error}</p></div>;
  if (!data) return <div className="card p-10 grid place-items-center"><Spinner className="w-6 h-6 text-accent" /></div>;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex border border-line bg-surface" role="tablist" aria-label="Kind of record">
          {Object.entries(data.entities).filter(([, e]) => e.total > 0).map(([k, e]) => (
            <button key={k} role="tab" aria-selected={entity === k} onClick={() => setEntity(k)}
              className={`h-9 px-3 text-[13px] font-medium ${entity === k ? "bg-ink text-white" : "text-muted hover:text-ink"}`}>
              {e.label} <span className={`ml-1 tabular-nums ${entity === k ? "text-white/80" : "text-faint"}`}>{e.to_review}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-[13px]">
          <span className="text-muted">{totalLeft} left to review</span>
          <select className="field h-9 w-auto" value={show} onChange={(e) => setShow(e.target.value as typeof show)} aria-label="Show">
            <option value="to_review">To review</option><option value="decided">Decided</option><option value="all">All</option>
          </select>
        </div>
      </div>

      <div className="grid lg:grid-cols-[280px_1fr] gap-5 items-start">
        <ul className="card divide-y divide-line max-h-[70vh] overflow-auto" aria-label="Pairs">
          {pairs.length === 0 && <li className="p-4 text-[13px] text-muted">{show === "to_review" ? "Nothing left to review here." : "No pairs."}</li>}
          {pairs.map((p) => (
            <li key={p.key}>
              <button onClick={() => setSelected(p.key)} aria-current={p.key === selected}
                className={`w-full text-left px-4 py-3 ${p.key === selected ? "bg-sunken" : "hover:bg-[#F5F8FF]"}`}>
                <p className="text-[13px] font-medium truncate">{title(p, "a")}</p>
                <p className="text-[12px] text-muted truncate">and {title(p, "b")}</p>
                {p.decision && <p className="mt-1"><span className="pill bg-ok-soft text-ok py-0 text-[11.5px]">{p.decision.decision === "merge" ? "Merged" : "Kept both"}</span></p>}
              </button>
            </li>
          ))}
        </ul>
        {pair ? <Compare key={pair.key + (pair.decision?.at ?? "")} pair={pair} onDecide={decide} /> : <div className="card p-10 text-center text-muted text-[13px]">Select a pair to compare.</div>}
      </div>
      <Toast message={toast} />
    </div>
  );
}
