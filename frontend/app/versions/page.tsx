"use client";

// Version review: every mapping change since the last saved version, what it does
// to each entity's SQL, and save-as-new-version / discard. Changes are made in
// Schema mapping; this page is where they're checked before they become a version.
// API (later): GET /projects/:id/changes, POST /projects/:id/versions
import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import { Check, PageHeader, Shell, Toast } from "../../components/ui";
import { ENTITIES } from "../../lib/mock";
import { diffLines, entitySql, type DiffLine } from "../../lib/sql";
import { useStore } from "../../lib/store";
import { joinsOf, resolveIn, type Change, type ChangeKind } from "../../lib/versions";

export default function VersionsPage() {
  const { pendingChanges, savedOverrides, currentOverrides, revertChange, discardChanges, saveVersion, runs } = useStore();
  const [label, setLabel] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const latest = runs[0];
  const next = Math.max(0, ...runs.map((r) => r.version)) + 1;
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400); };

  const byEntity = useMemo(() => {
    const groups = new Map<string, Change[]>();
    for (const c of pendingChanges) groups.set(c.entity, [...(groups.get(c.entity) ?? []), c]);
    return Array.from(groups.entries()).map(([key, changes]) => ({ entity: ENTITIES.find((e) => e.key === key)!, changes }));
  }, [pendingChanges]);

  return (
    <Shell>
      <PageHeader
        title="Version review"
        sub={pendingChanges.length
          ? `${pendingChanges.length} change${pendingChanges.length > 1 ? "s" : ""} since v${latest.version}. Check them, then save as v${next}.`
          : undefined}
      />

      {pendingChanges.length === 0 ? (
        <div className="grid lg:grid-cols-[1fr_340px] gap-5 items-start">
          <div className="card px-6 py-12 text-center">
            <span className="inline-grid place-items-center w-10 h-10 rounded-full bg-ok-soft text-ok mb-3"><Check /></span>
            <p className="font-semibold">No changes since v{latest.version}</p>
            <p className="text-[13px] text-muted mt-1 max-w-[420px] mx-auto">Changes you make in Schema mapping (columns, transforms, joins, reviews) appear here before they’re saved as a new version.</p>
            <Link href="/canonical" className="btn-secondary mt-5">Go to Schema mapping</Link>
          </div>
          <History />
        </div>
      ) : (
        <div className="grid lg:grid-cols-[1fr_340px] gap-5 items-start">
          <div className="space-y-5 min-w-0">
            {byEntity.map(({ entity, changes }) => (
              <section key={entity.key} className="card overflow-hidden">
                <div className="flex items-baseline justify-between gap-2 px-5 pt-4 pb-3 border-b border-line">
                  <h2 className="font-semibold">{entity.label}</h2>
                  <span className="text-[12px] text-muted">{changes.length} change{changes.length > 1 ? "s" : ""}</span>
                </div>
                <ul className="divide-y divide-line">
                  {changes.map((c) => (
                    <li key={c.id} className="px-5 py-3 flex flex-wrap items-start gap-x-4 gap-y-2">
                      <KindPill kind={c.kind} />
                      <div className="flex-1 min-w-[260px]">
                        <p className="font-mono text-[12.5px] font-medium">{c.subject}</p>
                        <div className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-[12.5px]">
                          <span className="text-faint">was</span><span className="font-mono text-muted line-through decoration-faint break-all">{c.before}</span>
                          <span className="text-faint">now</span><span className="font-mono text-ink break-all">{c.after}</span>
                        </div>
                      </div>
                      <button className="btn-ghost h-7 px-2.5 text-[12px]" onClick={() => { revertChange(c.id); flash("Change reverted"); }}>Revert</button>
                    </li>
                  ))}
                </ul>
                <SqlDiff before={entitySql(entity, joinsOf(savedOverrides, entity.key), (f) => resolveIn(savedOverrides, entity.key, f))}
                  after={entitySql(entity, joinsOf(currentOverrides, entity.key), (f) => resolveIn(currentOverrides, entity.key, f))}
                  name={`${entity.key}.sql`} />
              </section>
            ))}
          </div>

          <aside className="space-y-5 lg:sticky lg:top-[120px]">
            <section className="card p-5">
              <h2 className="font-semibold mb-3">Save as v{next}</h2>
              <label htmlFor="version-label" className="label">What changed</label>
              <input id="version-label" className="field" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Fixed candidate job titles" />
              <button className="btn-primary w-full mt-3" onClick={() => { const v = saveVersion(label); setLabel(""); flash(`Saved as v${v}`); }}>
                Save {pendingChanges.length} change{pendingChanges.length > 1 ? "s" : ""} as v{next}
              </button>
              {confirmDiscard ? (
                <div className="mt-3 text-[12.5px]">
                  <p className="text-muted mb-2">Undo all {pendingChanges.length} changes and go back to v{latest.version}?</p>
                  <div className="flex gap-2">
                    <button className="btn-secondary flex-1" onClick={() => setConfirmDiscard(false)}>Keep them</button>
                    <button className="btn-primary flex-1" onClick={() => { discardChanges(); setConfirmDiscard(false); flash(`Back to v${latest.version}`); }}>Discard</button>
                  </div>
                </div>
              ) : (
                <button className="btn-ghost w-full mt-2" onClick={() => setConfirmDiscard(true)}>Discard all changes</button>
              )}
            </section>
            <History />
          </aside>
        </div>
      )}
      <Toast message={toast} />
    </Shell>
  );
}

const KIND_STYLE: Record<ChangeKind, string> = {
  Mapping: "bg-accent-soft text-accent",
  Transform: "bg-sunken text-ink",
  Join: "bg-ink text-white",
  Review: "bg-warn-soft text-warn",
};

function KindPill({ kind }: { kind: ChangeKind }) {
  return <span className={`pill w-[84px] justify-center ${KIND_STYLE[kind]}`}>{kind}</span>;
}

function History() {
  const { runs } = useStore();
  return (
    <section className="card p-5">
      <h2 className="font-semibold mb-3">Versions</h2>
      <ul className="space-y-1">
        {runs.map((r, i) => (
          <li key={r.id} className={`flex gap-3 px-2 py-2 -mx-2 ${i === 0 ? "bg-accent-soft/60" : ""}`}>
            <span className="font-mono text-[12px] text-muted pt-0.5 w-7">v{r.version}</span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium truncate">{r.label}</p>
              <p className="text-[12px] text-muted">{r.when} · {r.by}</p>
            </div>
            {i === 0 && <span className="pill bg-ok-soft text-ok h-fit">Current</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---- SQL diff ----

const CONTEXT = 2;

function SqlDiff({ before, after, name }: { before: string; after: string; name: string }) {
  const lines = diffLines(before, after);
  const added = lines.filter((l) => l.kind === "add").length;
  const removed = lines.filter((l) => l.kind === "del").length;
  if (!added && !removed) {
    return <p className="px-5 py-3 border-t border-line text-[12px] text-muted">No change to the SQL (review decisions only).</p>;
  }
  // Show changed lines with a little context; fold long unchanged runs
  const keep = lines.map((l, i) => l.kind !== "same" || lines.slice(Math.max(0, i - CONTEXT), i + CONTEXT + 1).some((x) => x.kind !== "same"));
  const blocks: (DiffLine | { fold: number })[] = [];
  let folded = 0;
  lines.forEach((l, i) => {
    if (keep[i]) { if (folded) blocks.push({ fold: folded }); folded = 0; blocks.push(l); }
    else folded++;
  });
  if (folded) blocks.push({ fold: folded });

  return (
    <details open className="border-t border-line group/diff">
      <summary className="flex items-center gap-2 px-5 py-2.5 cursor-pointer list-none text-[12.5px] [&::-webkit-details-marker]:hidden">
        <svg width="10" height="10" viewBox="0 0 10 10" className="text-muted transition-transform group-open/diff:rotate-90" aria-hidden><path d="M3.5 2 6.5 5l-3 3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <span className="font-medium">SQL changes</span>
        <span className="font-mono text-muted">{name}</span>
        <span className="ml-auto font-mono text-[12px]"><span className="text-accent font-semibold">+{added}</span> <span className="text-muted">−{removed}</span></span>
      </summary>
      <div className="bg-nav font-mono text-[12px] leading-[1.8] overflow-x-auto">
        <table className="border-collapse min-w-full">
          <tbody>
            {blocks.map((b, i) => "fold" in b ? (
              <tr key={i}><td colSpan={4} className="px-4 py-0.5 text-[11px] text-[#5E77A8] bg-[#0B1F45]">⋯ {b.fold} unchanged line{b.fold > 1 ? "s" : ""}</td></tr>
            ) : (
              <Fragment key={i}>
                <tr className={b.kind === "add" ? "bg-[#1F4FA8]/45" : b.kind === "del" ? "bg-[#0B1F45]" : ""}>
                  <td className="select-none text-right pl-3 pr-2 text-[#3E5687] tabular-nums w-10">{b.oldNo ?? ""}</td>
                  <td className="select-none text-right pr-3 text-[#3E5687] tabular-nums w-10">{b.newNo ?? ""}</td>
                  <td className={`select-none w-4 ${b.kind === "add" ? "text-[#9DB9FF]" : "text-[#5E77A8]"}`}>{b.kind === "add" ? "+" : b.kind === "del" ? "−" : ""}</td>
                  <td className={`pr-6 whitespace-pre ${b.kind === "add" ? "text-white" : b.kind === "del" ? "text-[#6F86B5] line-through decoration-[#3E5687]" : "text-[#C9D8FF]"}`}>{b.text}</td>
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
