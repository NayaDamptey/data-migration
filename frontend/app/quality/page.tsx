"use client";

// Data quality (/quality): step 2, after Source upload (/). The engine's rules (engine/validation) run against
// the legacy database, the clean baseline or this project's uploaded files.
// API: GET /dq/sources, GET /dq/report?source=…, GET /dq/rules/{id}?source=…  (backend/app/routers/dq.py)
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { DuplicateReview } from "../../components/DuplicateReview";
import { Modal, Shell, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { useStore } from "../../lib/store";

type Source = { id: string; label: string; detail: string; available: boolean };
type Rule = { is_duplicate?: boolean; id: string; category: string; category_label: string; critical: boolean; table: string; description: string; violations: number; sample: { key: string; detail: string }[] };
type Report = {
  source: { id: string; label: string; checked_at: string; seconds: number; unrecognised_files?: string[]; note?: string };
  totals: { tables: number; rows: number; rules: number; passed: number; failed: number; violations: number; critical_violations: number; affected_records: number; score: number | null; clean_records_pct: number | null };
  categories: { category: string; label: string; critical: boolean; rules: number; failed_rules: number; violations: number }[];
  tables: { table: string; rows: number; columns: number; completeness: number | null; violations: number; failed_rules: number; affected_records: number; clean_pct: number | null }[];
  rules: Rule[];
  standard_checks: StandardCheck[];
  duplicate_review?: { total: number; merged: number; not_duplicate: number; to_review: number };
  not_applicable?: { count: number; missing_tables: string[] };
  answer_key?: { planted: number; found: number } | null;
};
type StandardCheck = { id: string; name: string; why: string; status: "pass" | "fail" | "not_run"; rules: number; rules_run: number; rules_failing: number; violations: number; records: number; rule_ids: string[]; failing_rule_ids: string[] };
type RuleRows = { rule: { id: string; table: string; key_column: string; description: string; category_label: string; sql: string }; total: number; rows: { key: string; detail: string; record: Record<string, string | null> | null }[] };

// duplicate rule -> the tab of the duplicate review page
const DUP_ENTITY: Record<string, string> = {
  "dup.person": "person", "dup.associate": "contact", "dup.account": "company", "dup.account.split_history": "company",
  "dup.job": "job", "dup.timesheet_line": "timesheet_line",
};
const fmt = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString());

export default function DataQualityRoute() {
  return <Suspense fallback={null}><DataQualityPage /></Suspense>;
}

function DataQualityPage() {
  const params = useSearchParams();
  const [tab, setTab] = useState<"checks" | "duplicates">(params.get("tab") === "duplicates" ? "duplicates" : "checks");
  const [dupEntity, setDupEntity] = useState<string | undefined>(params.get("entity") ?? undefined);
  const openDuplicates = (entity?: string) => { setDupEntity(entity); setTab("duplicates"); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const { projectId, uploads, uploadsReady } = useStore();
  const blocked = uploadsReady && !uploads.some((u) => u.status === "uploaded");
  const [sources, setSources] = useState<Source[]>([]);
  const [source, setSource] = useState<string>(params.get("source") ?? `upload:${projectId}`);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [check, setCheck] = useState<StandardCheck | null>(null);
  const [open, setOpen] = useState<Rule | null>(null);

  useEffect(() => {
    api<Source[]>(`/dq/sources?project_id=${encodeURIComponent(projectId)}`)
      .then((s) => {
        setSources(s);
        // the uploaded files are what this step checks; the other sources stay available for comparison
        if (!s.find((x) => x.id === source)?.available) setSource(s.find((x) => x.id.startsWith("upload:") && x.available)?.id ?? "legacy");
      })
      .catch((e: Error) => setError(e.message));
  }, [projectId]);

  const load = useCallback((refresh = false) => {
    setLoading(true);
    setError(null);
    api<Report>(`/dq/report?source=${encodeURIComponent(source)}${refresh ? "&refresh=true" : ""}`)
      .then((r) => { setReport(r); setCheck(null); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [source]);
  useEffect(() => { if (uploadsReady && !blocked) load(); }, [load, uploadsReady, blocked]);

  const rules = useMemo(() => (report?.rules ?? []).filter((r) => !check || check.failing_rule_ids.includes(r.id)), [report, check]);
  // which standard check a rule belongs to (the most specific one, i.e. the check with the fewest rules)
  const checkOf = useMemo(() => {
    const m = new Map<string, string>();
    [...(report?.standard_checks ?? [])].sort((a, b) => b.rule_ids.length - a.rule_ids.length)
      .forEach((c) => c.rule_ids.forEach((id) => m.set(id, c.name)));
    return m;
  }, [report]);
  const pickCheck = (c: StandardCheck) => {
    setCheck(check?.id === c.id || c.status !== "fail" ? null : c);
    if (c.status === "fail") setTimeout(() => document.getElementById("failing-checks")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };
  const t = report?.totals;

  if (blocked) {
    return (
      <Shell>
        <div className="card p-10 max-w-[560px] mx-auto text-center space-y-2" role="status">
          <h2 className="section-title">Data quality is locked</h2>
          <p className="text-[13px] text-muted">Upload source data to assess data quality.</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        <div>
          <h2 className="section-title">Data quality</h2>
          <p className="text-[13px] text-muted mt-0.5">
            {report ? <>Last checked {report.source.checked_at}</> : "Every source record checked before anything moves."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex border border-line bg-surface" role="radiogroup" aria-label="Data to check">
            {(sources.length ? sources : [{ id: "legacy", label: "Legacy database", detail: "", available: true }]).map((s) => (
              <button key={s.id} role="radio" aria-checked={source === s.id} disabled={!s.available} title={s.detail}
                onClick={() => setSource(s.id)}
                className={`h-9 px-3 text-[13px] font-medium ${source === s.id ? "bg-ink text-white" : "text-muted hover:text-ink disabled:opacity-40 disabled:hover:text-muted"}`}>
                {s.label}
              </button>
            ))}
          </div>
          <button className="btn-secondary h-9" onClick={() => load(true)} disabled={loading}>{loading ? <Spinner /> : "Check again"}</button>
        </div>
      </div>

      <div className="flex gap-6 border-b border-line mb-5" role="tablist" aria-label="Data quality">
        {([["checks", "Checks"], ["duplicates", "Duplicates"]] as const).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`pb-2.5 -mb-px text-[14px] border-b-[3px] ${tab === k ? "border-ink text-ink font-semibold" : "border-transparent text-muted hover:text-ink"}`}>
            {label}
            {k === "duplicates" && !!report?.duplicate_review?.to_review && <span className="ml-2 pill bg-accent text-white py-0">{report.duplicate_review.to_review}</span>}
          </button>
        ))}
      </div>

      {tab === "duplicates" && <DuplicateReview source={source} entity={dupEntity} onChanged={() => load()} />}

      {tab === "checks" && error && (
        <div role="alert" className="card p-5 mb-5 text-[13px]">
          <p className="font-semibold">Couldn’t run the checks</p>
          <p className="text-muted mt-1">{error}</p>
          <p className="text-muted mt-2">Is the API running? <code className="font-mono text-[12px]">cd backend && APP_ENV=development uvicorn app.main:app --port 8000</code></p>
        </div>
      )}

      {tab === "checks" && loading && !report && (
        <div className="card p-10 grid place-items-center text-muted text-[14px] gap-3"><Spinner className="w-6 h-6 text-accent" />Running the data quality checks…</div>
      )}

      {tab === "checks" && report && t && (
        <div className={`space-y-5 ${loading ? "opacity-60" : ""}`}>
          {/* KPI tiles */}
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {(() => {
              const run = report.standard_checks.filter((c) => c.status !== "not_run");
              const passed = run.filter((c) => c.status === "pass").length;
              return <Tile label="Standard checks passed" value={`${passed} / ${run.length}`} sub={passed === run.length ? "Ready to migrate" : `${run.length - passed} need fixing before migrating`} meter={run.length ? (100 * passed) / run.length : 0} />;
            })()}
            <Tile label="Clean records" value={t.clean_records_pct == null ? "—" : `${t.clean_records_pct}%`} sub="records with no problems" meter={t.clean_records_pct ?? 0} />
            <Tile label="Issues found" value={fmt(t.violations)} sub={`across ${report.standard_checks.filter((c) => c.status === "fail").length} failing checks`} />
            <Tile label="Records to fix" value={fmt(t.affected_records)} sub="records with at least one issue" strong={t.affected_records > 0} />
          </div>

          {/* Standard checks: the fixed list every migration is held to */}
          <section className="card p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
              <h3 className="font-semibold">Standard checks</h3>
              <span className="text-[12px] text-muted">
                {report.standard_checks.filter((c) => c.status === "pass").length} of {report.standard_checks.length} pass
                {report.standard_checks.some((c) => c.status === "not_run") && ` · ${report.standard_checks.filter((c) => c.status === "not_run").length} not run`}
              </span>
            </div>
            <ul className="grid sm:grid-cols-2 xl:grid-cols-5 gap-3">
              {report.standard_checks.map((c) => (
                <li key={c.id}>
                  <button onClick={() => pickCheck(c)} title={c.why} aria-pressed={check?.id === c.id}
                    className={`w-full h-full text-left border p-3 flex flex-col gap-1.5 transition-colors ${check?.id === c.id ? "border-ink bg-sunken" : "border-line hover:border-ink"} ${c.status === "fail" ? "" : "cursor-default"}`}>
                    <span className="flex items-center gap-2">
                      <CheckStatus status={c.status} />
                      <span className="text-[13px] font-semibold leading-snug">{c.name}</span>
                    </span>
                    <span className="text-[12px] text-muted">
                      {c.status === "pass" ? "No problems found" : c.status === "not_run" ? "Not run: tables not uploaded"
                        : `${fmt(c.records)} record${c.records === 1 ? "" : "s"} · ${c.rules_failing} of ${c.rules_run} rules`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {check && <p className="text-[12.5px] text-muted mt-3">{check.why} <button className="text-accent hover:underline" onClick={() => setCheck(null)}>Clear filter</button></p>}
          </section>

          {!!report.duplicate_review?.total && (
            <div className="card p-4 flex flex-wrap items-center justify-between gap-3 text-[13px]">
              <p>
                <span className="font-semibold">{report.duplicate_review.to_review} suspected duplicate pair{report.duplicate_review.to_review === 1 ? "" : "s"} to review</span>
                <span className="text-muted"> · {report.duplicate_review.merged} merged · {report.duplicate_review.not_duplicate} not duplicates. Compare them side by side, then merge or keep both.</span>
              </p>
              <button className="btn-primary h-9" onClick={() => openDuplicates()}>Review duplicates</button>
            </div>
          )}

          {(report.answer_key || report.source.unrecognised_files?.length || report.not_applicable?.count) ? (
            <div className="grid md:grid-cols-2 gap-4">
              {report.answer_key && (
                <div className="card p-4 text-[13px] flex items-center gap-3">
                  <span className="pill bg-ok-soft text-ok">{report.answer_key.found} / {report.answer_key.planted}</span>
                  <span>known problems planted in the legacy data were found by these checks.</span>
                </div>
              )}
              {!!report.not_applicable?.count && (
                <div className="card p-4 text-[13px]">
                  <span className="font-medium">{report.not_applicable.count} rules not run</span>
                  <span className="text-muted"> — they need tables that weren’t uploaded: {report.not_applicable.missing_tables.slice(0, 8).join(", ")}{report.not_applicable.missing_tables.length > 8 ? "…" : ""}</span>
                </div>
              )}
              {!!report.source.unrecognised_files?.length && (
                <div className="card p-4 text-[13px]">
                  <span className="font-medium">Not checked: </span>
                  <span className="text-muted">{report.source.unrecognised_files.join(", ")} — the file name doesn’t match a known source table.</span>
                </div>
              )}
            </div>
          ) : null}

          {/* Failing rules */}
          <section id="failing-checks" className="card overflow-hidden scroll-mt-28">
            <div className="px-5 pt-4 pb-3 flex flex-wrap items-baseline justify-between gap-3">
              <h3 className="font-semibold">Problems to fix{check ? ` · ${check.name}` : ""} <span className="text-muted font-normal">({rules.length})</span></h3>
              {check && <button className="text-[12px] text-accent hover:underline" onClick={() => setCheck(null)}>Show all checks</button>}
            </div>
            {rules.length === 0 ? <p className="px-5 pb-5 text-[13px] text-muted">Nothing to fix here.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead><tr><th className="th pl-5">Problem</th><th className="th">Table</th><th className="th">Standard check</th><th className="th text-right">Records</th><th className="th pr-5">Example</th></tr></thead>
                  <tbody>
                    {rules.map((r) => (
                      <tr key={r.id} className="hover:bg-[#F5F8FF] cursor-pointer"
                        onClick={() => (DUP_ENTITY[r.id] ? openDuplicates(DUP_ENTITY[r.id]) : setOpen(r))}>
                        <td className="td pl-5"><span className="font-medium">{r.description}</span></td>
                        <td className="td font-mono text-[12px]">{r.table}</td>
                        <td className="td text-muted">{checkOf.get(r.id) ?? r.category_label}</td>
                        <td className="td text-right tabular-nums font-semibold">{fmt(r.violations)}</td>
                        <td className="td pr-5 text-muted max-w-[320px] truncate" title={r.sample[0]?.detail}>
                          {DUP_ENTITY[r.id] && r.id !== "dup.account.split_history"
                            ? <>#{r.sample[0]?.detail.match(/\d+$/)?.[0]} ↔ #{r.sample[0]?.key} <span className="text-accent">· compare side by side</span></>
                            : <>#{r.sample[0]?.key} {r.sample[0]?.detail}</>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Next steps */}
          <div className="flex flex-wrap gap-3 justify-end">
            <Link href="/workspace" className="btn-primary">Continue to the migration workflow →</Link>
          </div>
        </div>
      )}

      <RuleDrawer rule={open} source={source} onClose={() => setOpen(null)} />
    </Shell>
  );
}

function CheckStatus({ status }: { status: StandardCheck["status"] }) {
  if (status === "pass")
    return <span className="grid place-items-center w-5 h-5 rounded-full bg-ink text-white shrink-0" aria-label="Pass"><svg width="11" height="11" viewBox="0 0 14 14" aria-hidden><path d="M3 7.5 5.8 10 11 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></span>;
  if (status === "fail")
    return <span className="grid place-items-center w-5 h-5 rounded-full border-2 border-ink text-ink shrink-0" aria-label="Fail"><svg width="9" height="9" viewBox="0 0 10 10" aria-hidden><path d="M2 2l6 6M8 2 2 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg></span>;
  return <span className="grid place-items-center w-5 h-5 rounded-full border border-dashed border-faint text-faint text-[11px] shrink-0" aria-label="Not run">–</span>;
}

function Tile({ label, value, sub, meter, strong }: { label: string; value: string; sub: string; meter?: number; strong?: boolean }) {
  return (
    <div className={`card p-5 ${strong ? "border-l-4 border-l-ink" : ""}`}>
      <p className="text-[12px] font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="text-[34px] leading-tight font-bold tracking-tight tabular-nums mt-1">{value}</p>
      {meter != null && <div className="h-1.5 bg-sunken mt-2"><div className="h-1.5 bg-ink" style={{ width: `${Math.max(0, Math.min(100, meter))}%` }} /></div>}
      <p className="text-[12.5px] text-muted mt-2">{sub}</p>
    </div>
  );
}

function RuleDrawer({ rule, source, onClose }: { rule: Rule | null; source: string; onClose: () => void }) {
  const [data, setData] = useState<RuleRows | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showSql, setShowSql] = useState(false);
  useEffect(() => {
    setData(null); setErr(null); setShowSql(false);
    if (rule) api<RuleRows>(`/dq/rules/${encodeURIComponent(rule.id)}?source=${encodeURIComponent(source)}`).then(setData).catch((e: Error) => setErr(e.message));
  }, [rule, source]);
  const cols = useMemo(() => Object.keys(data?.rows.find((r) => r.record)?.record ?? {}).slice(0, 12), [data]);
  return (
    <Modal open={!!rule} onClose={onClose} title={rule?.description ?? ""}>
      {err && <p className="text-[13px] text-bad">{err}</p>}
      {!data && !err && <div className="grid place-items-center py-8"><Spinner className="text-accent" /></div>}
      {data && (
        <div className="space-y-3 text-[13px] max-h-[65vh] overflow-auto">
          <p className="text-muted">{data.total.toLocaleString()} record{data.total === 1 ? "" : "s"} in <span className="font-mono">{data.rule.table}</span> · {data.rule.category_label}</p>
          <div className="overflow-x-auto border border-line">
            <table className="w-full text-[12px]">
              <thead><tr><th className="th pl-3">{data.rule.key_column ?? "Key"}</th><th className="th">Problem</th>{cols.filter((c) => c !== data.rule.key_column).slice(0, 6).map((c) => <th key={c} className="th">{c}</th>)}</tr></thead>
              <tbody>
                {data.rows.slice(0, 50).map((r) => (
                  <tr key={r.key + r.detail}>
                    <td className="td pl-3 font-mono">{r.key}</td>
                    <td className="td">{r.detail}</td>
                    {cols.filter((c) => c !== data.rule.key_column).slice(0, 6).map((c) => <td key={c} className="td text-muted max-w-[160px] truncate" title={r.record?.[c] ?? ""}>{r.record?.[c] ?? ""}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="text-[12px] text-accent hover:underline" onClick={() => setShowSql((v) => !v)}>{showSql ? "Hide" : "Show"} the check’s SQL</button>
          {showSql && <pre className="font-mono text-[11.5px] bg-sunken p-3 whitespace-pre-wrap">{data.rule.sql}</pre>}
        </div>
      )}
    </Modal>
  );
}
