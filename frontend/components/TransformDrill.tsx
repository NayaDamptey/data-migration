"use client";

// Drill into one mapped field: see real source values go through the transform,
// change the transform's settings, and watch the preview update.
import { ENTITIES, type CanonicalField } from "../lib/mock";
import { useStore } from "../lib/store";
import {
  ADDRESS_PART, DEFAULTS, DEFAULT_VALUE_MAPS, ENUM_VALUES, SOURCE_EXAMPLES, TRANSFORM_LABEL,
  applyTransform, splitAddress, type DateFormat, type SplitRule,
} from "../lib/transforms";

export function TransformDrill({ entity, field, from }: { entity: string; field: CanonicalField; from: string }) {
  const { transformConfig, setTransformConfig } = useStore();
  const cfg = transformConfig(entity, field.name);
  const t = field.transform ?? "none";
  const examples = SOURCE_EXAMPLES[from] ?? [];
  const results = examples.map((ex) => ({ source: ex.value, count: ex.count, ...applyTransform(t, `${entity}.${field.name}`, field.name, field.type, ex.value, cfg) }));
  const problems = results.filter((r) => r.problem);
  const problemRecords = problems.reduce((n, r) => n + r.count, 0);
  const totalRecords = results.reduce((n, r) => n + r.count, 0);

  // Other canonical fields fed by the same split (address_line_1 + city share one rule)
  const siblings = t === "split_address"
    ? (ENTITIES.find((e) => e.key === entity)?.fields ?? []).filter((f) => f.transform === "split_address" && f.from === from && f.name !== field.name).map((f) => f.name)
    : [];

  return (
    <div className="rounded-lg border border-line bg-surface p-4 space-y-4">
      {/* Flow: source column → transform → canonical field */}
      <div className="flex flex-wrap items-center gap-2 text-[12px]">
        <span className="pill bg-sunken text-ink font-mono">{from}</span>
        <Arrow />
        <span className="pill bg-accent-soft text-accent">{TRANSFORM_LABEL[t] ?? t}</span>
        <Arrow />
        <span className="pill bg-ink text-white font-mono">{field.name}</span>
        {siblings.length > 0 && <span className="text-muted">· same split also feeds <span className="font-mono">{siblings.join(", ")}</span></span>}
      </div>

      {/* Settings for this transform */}
      {t === "split_address" && (
        <Setting label="How to split">
          <Segmented<SplitRule>
            value={cfg.splitRule ?? DEFAULTS.splitRule}
            options={[["last_comma", "City after the last comma"], ["first_comma", "Everything after the first comma"], ["none", "Don’t split"]]}
            onChange={(v) => setTransformConfig(entity, field.name, { splitRule: v })}
          />
        </Setting>
      )}
      {t === "parse_date" && (
        <Setting label="Dates in the source are written as">
          <Segmented<DateFormat>
            value={cfg.dateFormat ?? DEFAULTS.dateFormat}
            options={[["DMY", "Day / Month / Year (UK)"], ["MDY", "Month / Day / Year (US)"]]}
            onChange={(v) => setTransformConfig(entity, field.name, { dateFormat: v })}
          />
          <p className="text-[11px] text-muted mt-1">ISO dates (2024-05-09) are always read correctly.</p>
        </Setting>
      )}
      {t === "constant" && (
        <Setting label="Value for every record">
          <input className="field h-8 max-w-[260px] text-[13px]" value={cfg.constant ?? "United Kingdom"} onChange={(e) => setTransformConfig(entity, field.name, { constant: e.target.value })} />
        </Setting>
      )}

      {t === "value_map" ? (
        <ValueMapEditor entity={entity} field={field} examples={examples} />
      ) : t === "constant" ? null : examples.length === 0 ? (
        <p className="text-[12px] text-muted">No sample values for this column yet. They appear after the next Inspect.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px] border border-line rounded-md border-separate border-spacing-0 overflow-hidden">
            <thead>
              <tr>
                <th className="th">Source value</th>
                {t === "split_address"
                  ? (["line_1", "line_2", "city"] as const).map((p) => (
                    <th key={p} className={`th ${ADDRESS_PART[field.name] === p ? "text-ink bg-accent-soft" : ""}`}>{{ line_1: "address_line_1", line_2: "address_line_2", city: "city" }[p]}</th>
                  ))
                  : <th className="th">→ {field.name}</th>}
                <th className="th text-right">Records</th>
                <th className="th">Check</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => {
                const parts = t === "split_address" ? splitAddress(r.source, cfg.splitRule ?? DEFAULTS.splitRule) : null;
                return (
                  <tr key={r.source} className={r.problem ? "bg-warn-soft/40" : ""}>
                    <td className="td font-mono">{r.source === "" ? <span className="text-faint">(blank)</span> : r.source}</td>
                    {parts
                      ? (["line_1", "line_2", "city"] as const).map((p) => (
                        <td key={p} className={`td ${ADDRESS_PART[field.name] === p ? "bg-accent-soft/40 font-medium" : "text-muted"}`}>{parts[p] ?? <span className="text-faint">—</span>}</td>
                      ))
                      : <td className="td font-medium">{r.value ?? <span className="text-faint">—</span>}</td>}
                    <td className="td text-right tabular-nums text-muted">{r.count.toLocaleString()}</td>
                    <td className="td">{r.problem ? <span className="text-warn">⚠ {r.problem}</span> : <span className="text-ok">OK</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="text-[12px] text-muted mt-2">
            {problems.length
              ? <>{problems.length} of {results.length} sample values need a look ({problemRecords.toLocaleString()} of {totalRecords.toLocaleString()} sample records). Fix the rule above, or ask for those records to be cleaned in the source.</>
              : <>All {results.length} sample values come through cleanly.</>}
          </p>
        </div>
      )}
    </div>
  );
}

function ValueMapEditor({ entity, field, examples }: { entity: string; field: CanonicalField; examples: { value: string; count: number }[] }) {
  const { transformConfig, setTransformConfig } = useStore();
  const key = `${entity}.${field.name}`;
  const map = transformConfig(entity, field.name).valueMap ?? DEFAULT_VALUE_MAPS[key] ?? {};
  const options = ENUM_VALUES[key] ?? [];
  const lookup = (v: string) => Object.entries(map).find(([k]) => k.toLowerCase() === v.toLowerCase())?.[1];
  const unmatched = examples.filter((e) => lookup(e.value) === undefined);
  const unmatchedRecords = unmatched.reduce((n, e) => n + e.count, 0);

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] border border-line rounded-md border-separate border-spacing-0 overflow-hidden">
          <thead><tr><th className="th">Source value</th><th className="th text-right">Records</th><th className="th">→ {field.name}</th></tr></thead>
          <tbody>
            {examples.map((e) => {
              const v = lookup(e.value);
              return (
                <tr key={e.value} className={v === undefined ? "bg-warn-soft/40" : ""}>
                  <td className="td font-mono">{e.value}</td>
                  <td className="td text-right tabular-nums text-muted">{e.count.toLocaleString()}</td>
                  <td className="td">
                    <label className="sr-only" htmlFor={`vm-${key}-${e.value}`}>Map {e.value} to</label>
                    <select
                      id={`vm-${key}-${e.value}`}
                      value={v ?? "__none"}
                      onChange={(ev) => {
                        const next = { ...map };
                        Object.keys(next).forEach((k) => { if (k.toLowerCase() === e.value.toLowerCase()) delete next[k]; });
                        if (ev.target.value !== "__none") next[e.value] = ev.target.value === "__blank" ? "" : ev.target.value;
                        setTransformConfig(entity, field.name, { valueMap: next });
                      }}
                      className={`h-7 rounded-md border bg-surface px-2 font-mono text-[12px] ${v === undefined ? "border-warn/60 text-warn" : "border-line"}`}
                    >
                      <option value="__none">⚠ Not mapped yet</option>
                      {options.map((o) => <option key={o} value={o}>{o}</option>)}
                      <option value="__blank">(leave blank)</option>
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className={`text-[12px] mt-2 ${unmatched.length ? "text-warn" : "text-muted"}`}>
        {unmatched.length
          ? <>{unmatched.length} value{unmatched.length > 1 ? "s" : ""} ({unmatchedRecords.toLocaleString()} records) not mapped yet. They’ll be left blank until you choose.</>
          : "Every source value has a match."}
      </p>
    </div>
  );
}

function Setting({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><p className="text-[12px] font-medium text-muted mb-1.5">{label}</p>{children}</div>;
}

function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div role="radiogroup" className="inline-flex flex-wrap p-0.5 rounded-lg bg-sunken border border-line">
      {options.map(([v, label]) => (
        <button key={v} role="radio" aria-checked={value === v} onClick={() => onChange(v)}
          className={`h-7 px-3 rounded-md text-[12px] transition-colors ${value === v ? "bg-surface shadow-card font-medium text-ink" : "text-muted hover:text-ink"}`}>
          {label}
        </button>
      ))}
    </div>
  );
}

function Arrow() {
  return <svg width="14" height="10" viewBox="0 0 14 10" className="text-faint" aria-hidden><path d="M1 5h11M8 1l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
