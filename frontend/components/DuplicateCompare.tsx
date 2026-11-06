"use client";

// Two suspected duplicates side by side: every field in two columns (differences highlighted), what is
// attached to each record, and the decision: merge (keep one record, pick each differing value) or keep both.
// Used by the dashboard (click a duplicate problem) and the Duplicates page.
import { useState } from "react";

export type Field = { column: string; a: string | null; b: string | null; same: boolean; key: boolean };
export type Link_ = { table: string; column: string; count: number };
export type Decision = { decision: "merge" | "not_duplicate"; keep: "a" | "b" | null; fields: Record<string, "a" | "b">; by: string; at: string };
export type Pair = { key: string; entity: string; label: string; table: string; a: string; b: string; reason: string; fields: Field[]; links: { a: Link_[]; b: Link_[] }; decision: Decision | null };
export type Payload = { source: string; entities: Record<string, { label: string; total: number; to_review: number }>; pairs: Pair[] };

const NAME_FIELDS: Record<string, string[]> = {
  person: ["First_Name", "Last_Name"], contact: ["AssociateTitle", "Person_ID"], company: ["Account_name"],
  job: ["Req_Title", "AccountID"], timesheet_line: ["Timesheet_ID", "TotalHours"],
};
export const linksTotal = (l: Link_[]) => l.reduce((n, x) => n + x.count, 0);

export function title(p: Pair, side: "a" | "b") {
  const f = Object.fromEntries(p.fields.map((x) => [x.column, x[side]]));
  const [x, y] = NAME_FIELDS[p.entity] ?? [];
  if (p.entity === "person") return `${f[x] ?? ""} ${f[y] ?? ""}`.trim();
  if (p.entity === "contact") return `${f[x] ?? ""} contact · person ${f[y]}`;
  if (p.entity === "job") return `${f[x] ?? ""} · company ${f[y]}`;
  if (p.entity === "timesheet_line") return `Timesheet ${f[x]} · ${f[y]}h`;
  return f[x] ?? `#${p[side]}`;
}

export type DecideBody = { key: string; decision: string; keep?: "a" | "b"; fields?: Record<string, "a" | "b"> };

export function Compare({ pair, onDecide }: { pair: Pair; onDecide: (b: { key: string; decision: string; keep?: "a" | "b"; fields?: Record<string, "a" | "b"> }) => void }) {
  // default: keep the record that has more attached to it (older record on a tie)
  const defaultKeep: "a" | "b" = pair.decision?.keep ?? (linksTotal(pair.links.b) > linksTotal(pair.links.a) ? "b" : "a");
  const [keep, setKeep] = useState<"a" | "b">(defaultKeep);
  const differing = pair.fields.filter((f) => !f.same && !f.key);
  const [picks, setPicks] = useState<Record<string, "a" | "b">>(() => {
    const init: Record<string, "a" | "b"> = {};
    differing.forEach((f) => {
      // fill a gap from the other record; otherwise take the kept record's value
      init[f.column] = pair.decision?.fields?.[f.column] ?? (f[defaultKeep] == null && f[defaultKeep === "a" ? "b" : "a"] != null ? (defaultKeep === "a" ? "b" : "a") : defaultKeep);
    });
    return init;
  });
  const [onlyDiff, setOnlyDiff] = useState(true);
  const setKeepAll = (side: "a" | "b") => { setKeep(side); setPicks(Object.fromEntries(differing.map((f) => [f.column, f[side] == null && f[side === "a" ? "b" : "a"] != null ? (side === "a" ? "b" : "a") : side]))); };
  const rows = onlyDiff ? pair.fields.filter((f) => !f.same || f.key) : pair.fields;
  const decided = pair.decision;

  return (
    <section className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-line flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wide text-muted">{pair.label} · {pair.table}</p>
          <h3 className="text-[16px] font-semibold mt-0.5">{title(pair, "a")} <span className="text-faint font-normal">and</span> {title(pair, "b")}</h3>
          <p className="text-[12.5px] text-muted mt-1">Flagged because: {pair.reason.replace(/^No /, "").replace(/^near-duplicate /, "near-duplicate ")}</p>
        </div>
        {decided && (
          <div className="text-right text-[12.5px]">
            <span className="pill bg-ok-soft text-ok">{decided.decision === "merge" ? `Merged · keeping #${decided.keep === "a" ? pair.a : pair.b}` : "Not a duplicate"}</span>
            <p className="text-muted mt-1">{decided.at.replace("T", " ")}</p>
          </div>
        )}
      </div>

      {/* Records head to head */}
      <div className="grid grid-cols-[minmax(120px,0.8fr)_1fr_1fr] text-[13px]">
        <div className="th pl-5 border-b border-line">Field</div>
        {(["a", "b"] as const).map((s) => (
          <div key={s} className={`th border-b border-line ${keep === s ? "bg-sunken" : ""}`}>
            <label className="flex items-center gap-2 cursor-pointer normal-case">
              <input type="radio" name="keep" className="accent-[#0A1F44]" checked={keep === s} onChange={() => setKeepAll(s)} disabled={!!decided} />
              <span className="font-semibold text-ink">#{pair[s]}</span>
              <span className="text-muted font-normal">{keep === s ? "record to keep" : "duplicate"}</span>
            </label>
          </div>
        ))}
        {rows.map((f) => {
          const diff = !f.same && !f.key;
          return (
            <div key={f.column} className="contents">
              <div className={`td pl-5 font-mono text-[12px] ${diff ? "text-ink font-semibold" : "text-muted"}`}>{f.column}{diff && <span className="ml-1.5 pill bg-warn-soft text-warn py-0 font-sans">differs</span>}</div>
              {(["a", "b"] as const).map((s) => (
                <div key={s} className={`td ${keep === s ? "bg-sunken/60" : ""} ${diff && picks[f.column] === s ? "font-semibold" : diff ? "text-muted" : ""}`}>
                  {diff && !decided ? (
                    <label className="flex items-start gap-2 cursor-pointer">
                      <input type="radio" name={`f-${f.column}`} className="accent-[#0A1F44] mt-0.5" checked={picks[f.column] === s}
                        onChange={() => setPicks((p) => ({ ...p, [f.column]: s }))} />
                      <span className="break-words">{f[s] ?? <span className="text-faint italic font-normal">empty</span>}</span>
                    </label>
                  ) : (
                    <span className="break-words">{f[s] ?? <span className="text-faint italic">empty</span>}</span>
                  )}
                </div>
              ))}
            </div>
          );
        })}
        <div className="td pl-5 text-muted text-[12px]">Attached records</div>
        {(["a", "b"] as const).map((s) => (
          <div key={s} className={`td text-[12px] ${keep === s ? "bg-sunken/60" : ""}`}>
            {pair.links[s].length === 0 ? <span className="text-faint">Nothing attached</span> : (
              <ul className="space-y-0.5">{pair.links[s].map((l) => <li key={l.table + l.column}><span className="tabular-nums font-semibold">{l.count}</span> × {l.table} <span className="text-faint">({l.column})</span></li>)}</ul>
            )}
          </div>
        ))}
      </div>

      <div className="px-5 py-4 border-t border-line flex flex-wrap items-center justify-between gap-3 bg-[#F5F8FF]">
        <label className="flex items-center gap-2 text-[12.5px] text-muted cursor-pointer"><input type="checkbox" className="accent-[#0A1F44]" checked={onlyDiff} onChange={(e) => setOnlyDiff(e.target.checked)} />Only fields that differ</label>
        {decided ? (
          <button className="btn-secondary" onClick={() => onDecide({ key: pair.key, decision: "undecided" })}>Undo decision</button>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button className="btn-secondary" onClick={() => onDecide({ key: pair.key, decision: "not_duplicate" })}>Not a duplicate — keep both</button>
            <button className="btn-primary" onClick={() => onDecide({ key: pair.key, decision: "merge", keep, fields: picks })}>
              Merge into #{keep === "a" ? pair.a : pair.b}
            </button>
          </div>
        )}
        {!decided && (
          <p className="w-full text-[12px] text-muted">
            Merging keeps #{keep === "a" ? pair.a : pair.b} with the values selected above.
            {linksTotal(pair.links[keep === "a" ? "b" : "a"]) > 0 && ` The ${linksTotal(pair.links[keep === "a" ? "b" : "a"])} record(s) attached to #${keep === "a" ? pair.b : pair.a} will be moved to it.`}
          </p>
        )}
      </div>
    </section>
  );
}
