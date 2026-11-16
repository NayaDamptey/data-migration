"use client";

// Review by records: the customer's own data as records in the canonical model (middle tier).
// Pick an entity, browse or search its records (flagged ones first), open a record to see its fields,
// related records and what to check; click any value to see where it came from in the legacy source.
// API: GET /review/{entity}, /review/{entity}/{id}, /review/{entity}/{id}/source/{column} (backend/app/review.py)
import { useEffect, useState } from "react";
import { PageHeader, Shell, Spinner } from "../../components/ui";
import { api } from "../../lib/api";

type Item = { id: string; title: string; subtitle: string; flags: number };
type List = { entity: string; label: string; total: number; flagged: number; records: Item[] };
type Flag = { level: "check" | "rejected" | "flagged" | "gap"; message: string };
type Related = { label: string; items: { entity?: string; id?: string; title: string; subtitle: string }[] };
type RecordT = { entity: string; label: string; id: string; title: string; subtitle: string; fields: { column: string; label: string; value: string | null }[]; flags: Flag[]; related: Related[] };
type Source = { column: string; expression: string | null; value: string | null; note: string | null;
  sources: { table: string; column: string; key_column: string | null; key: string | null; raw: string | null; derived?: boolean }[] };

const ENTITIES = [["candidates", "Candidates"], ["clients", "Clients"], ["contacts", "Contacts"], ["jobs", "Jobs"], ["placements", "Placements"]] as const;
const FLAG = { rejected: "bg-bad-soft text-bad", flagged: "bg-warn-soft text-warn", check: "bg-warn-soft text-warn", gap: "bg-sunken text-muted" } as const;
const FLAG_LABEL = { rejected: "Not loaded", flagged: "Loaded with a warning", check: "Data quality", gap: "Missing" } as const;

export default function ReviewPage() {
  const [entity, setEntity] = useState<string>("candidates");
  const [query, setQuery] = useState("");
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [list, setList] = useState<List | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<{ entity: string; id: string } | null>(null);

  useEffect(() => {
    setList(null); setError(null);
    const t = setTimeout(() => {
      api<List>(`/review/${entity}?flagged=${flaggedOnly}${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ""}`)
        .then((l) => { setList(l); setActive((a) => (a && a.entity === entity && a.id ? a : l.records[0] ? { entity, id: l.records[0].id } : null)); })
        .catch((e: Error) => setError(e.message));
    }, query ? 250 : 0);
    return () => clearTimeout(t);
  }, [entity, query, flaggedOnly]);

  const open = (e: string, id: string) => {
    if (e !== entity) { setEntity(e); setQuery(""); setFlaggedOnly(false); }
    setActive({ entity: e, id });
  };

  return (
    <Shell>
      <PageHeader title="Review records" />
      <div role="tablist" aria-label="Entity" className="flex flex-wrap gap-6 border-b border-line mb-4">
        {ENTITIES.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={entity === k} onClick={() => open(k, "")}
            className={`pb-2.5 -mb-px text-[14px] border-b-[3px] ${entity === k ? "border-ink text-ink font-semibold" : "border-transparent text-muted hover:text-ink"}`}>
            {label}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden grid md:grid-cols-[320px_1fr] min-h-[680px]">
        <nav aria-label="Records" className="border-b md:border-b-0 md:border-r border-line bg-[#F5F8FF] flex flex-col min-h-0">
          <div className="p-3 space-y-2 border-b border-line">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name or id" aria-label="Search" className="field h-8 text-[13px]" />
            <label className="flex items-center gap-2 text-[12.5px] text-muted cursor-pointer">
              <input type="checkbox" className="accent-[#0A1F44]" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} />
              Only records to check{list ? ` (${list.flagged})` : ""}
            </label>
          </div>
          {error ? <p className="p-4 text-[13px] text-bad">{error}</p> : !list ? (
            <div className="grid place-items-center py-16"><Spinner className="w-5 h-5 text-accent" /></div>
          ) : (
            <ul className="overflow-y-auto max-h-[620px] p-2 space-y-0.5">
              {list.records.map((r) => (
                <li key={r.id}>
                  <button onClick={() => setActive({ entity, id: r.id })}
                    className={`w-full text-left rounded-lg px-3 py-2 ${active?.entity === entity && active.id === r.id ? "bg-surface shadow-card border border-line" : "border border-transparent hover:bg-sunken"}`}>
                    <span className="flex items-center gap-2">
                      <span className="text-[13px] font-medium truncate flex-1">{r.title}</span>
                      {r.flags > 0 && <span className="pill bg-warn-soft text-warn py-0 text-[11px]">{r.flags}</span>}
                    </span>
                    {r.subtitle && <span className="block text-[11.5px] text-muted truncate">{r.subtitle}</span>}
                  </button>
                </li>
              ))}
              {list.records.length === 0 && <li className="p-3 text-[13px] text-muted">No records.</li>}
            </ul>
          )}
        </nav>

        <section className="min-w-0">
          {active?.id ? <RecordCard key={`${active.entity}-${active.id}`} entity={active.entity} id={active.id} onOpen={open} />
            : <div className="p-10 text-center text-[13px] text-muted">Pick a record.</div>}
        </section>
      </div>
    </Shell>
  );
}

function RecordCard({ entity, id, onOpen }: { entity: string; id: string; onOpen: (e: string, id: string) => void }) {
  const [rec, setRec] = useState<RecordT | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [src, setSrc] = useState<{ column: string; data: Source | null } | null>(null);

  useEffect(() => {
    api<RecordT>(`/review/${entity}/${encodeURIComponent(id)}`).then(setRec).catch((e: Error) => setError(e.message));
  }, [entity, id]);

  const showSource = (column: string) => {
    if (src?.column === column) { setSrc(null); return; }
    setSrc({ column, data: null });
    api<Source>(`/review/${entity}/${encodeURIComponent(id)}/source/${encodeURIComponent(column)}`)
      .then((d) => setSrc({ column, data: d })).catch(() => setSrc(null));
  };

  if (error) return <p className="p-5 text-[13px] text-bad">{error}</p>;
  if (!rec) return <div className="grid place-items-center py-24"><Spinner className="w-6 h-6 text-accent" /></div>;

  return (
    <div>
      <div className="px-6 pt-5 pb-4 border-b border-line">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-muted">{rec.label.replace(/s$/, "")} {rec.id}</p>
        <h2 className="text-[20px] font-semibold mt-0.5">{rec.title}</h2>
        {rec.subtitle && <p className="text-[13px] text-muted mt-0.5">{rec.subtitle}</p>}
      </div>

      {rec.flags.length > 0 && (
        <div className="mx-6 mt-4 border border-warn/40 bg-warn-soft/30 px-4 py-3">
          <p className="text-[13px] font-semibold mb-1.5">Check this record</p>
          <ul className="space-y-1">
            {rec.flags.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-[13px]">
                <span className={`pill py-0 text-[11px] shrink-0 ${FLAG[f.level]}`}>{FLAG_LABEL[f.level]}</span>
                <span>{f.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid lg:grid-cols-[1fr_300px] gap-6 px-6 py-5">
        <div>
          <h3 className="text-[13px] font-semibold mb-2">Details</h3>
          <dl className="divide-y divide-line border-y border-line">
            {rec.fields.map((f) => (
              <div key={f.column}>
                <div className="grid grid-cols-[170px_1fr] gap-3 py-2 text-[13px]">
                  <dt className="text-muted">{f.label}</dt>
                  <dd>
                    <button className={`text-left hover:underline decoration-dotted ${src?.column === f.column ? "underline" : ""}`}
                      title="Where did this come from?" onClick={() => showSource(f.column)}>
                      {f.value ?? <span className="text-faint">—</span>}
                    </button>
                  </dd>
                </div>
                {src?.column === f.column && (
                  <div className="mb-2 ml-[170px] bg-sunken px-3 py-2 text-[12.5px]">
                    {!src.data ? <Spinner className="text-accent" /> : (
                      <>
                        {src.data.sources.map((s, i) => (
                          <p key={i}>
                            From <span className="font-mono">{s.table}.{s.column}</span>
                            {s.key_column && s.key && <> in the row where <span className="font-mono">{s.key_column} = {s.key}</span></>}
                            {s.raw != null && <> : <span className="font-mono">{s.raw}</span></>}
                          </p>
                        ))}
                        {src.data.note && <p className="text-muted">{src.data.note}</p>}
                        {src.data.expression && <p className="text-muted mt-1">Mapping: <span className="font-mono">{src.data.expression}</span></p>}
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </dl>
        </div>

        <div className="space-y-4">
          {rec.related.filter((g) => g.items.length > 0).map((g) => (
            <div key={g.label}>
              <h3 className="text-[13px] font-semibold mb-1.5">{g.label} <span className="text-muted font-normal">({g.items.length})</span></h3>
              <ul className="border border-line divide-y divide-line">
                {g.items.slice(0, 12).map((it, i) => (
                  <li key={i}>
                    {it.entity && it.id ? (
                      <button className="w-full text-left px-3 py-2 hover:bg-[#F5F8FF]" onClick={() => onOpen(it.entity!, it.id!)}>
                        <span className="block text-[13px] font-medium truncate">{it.title}</span>
                        {it.subtitle && <span className="block text-[11.5px] text-muted truncate">{it.subtitle}</span>}
                      </button>
                    ) : (
                      <div className="px-3 py-2">
                        <span className="block text-[13px] truncate" title={it.title}>{it.title}</span>
                        {it.subtitle && <span className="block text-[11.5px] text-muted truncate">{it.subtitle}</span>}
                      </div>
                    )}
                  </li>
                ))}
                {g.items.length > 12 && <li className="px-3 py-1.5 text-[12px] text-muted">and {g.items.length - 12} more</li>}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
