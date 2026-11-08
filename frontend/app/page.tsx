"use client";

// Setup: the start page. Source and destination, the source upload, and the pipeline
// (upload source -> data quality -> canonical -> target -> get data).
// Files are checked in the browser, uploaded to the API (local mode: backend/app/routers/local_files.py),
// then checked by the data quality rules (/quality).
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BulkUpload } from "../components/BulkUpload";
import { Select, Shell, Toast } from "../components/ui";
import { Panel, Step } from "../components/Workflow";
import { ENTITIES, OUTPUTS, SOURCE_FORMATS, SOURCE_SYSTEMS, TARGET_DATABASES, TARGET_SYSTEMS } from "../lib/mock";
import { useStore } from "../lib/store";
import { formatBytes } from "../lib/upload";

export default function SourceSetupPage() {
  const router = useRouter();
  const { setup, updateSetup, uploads, steps, runStep, quality } = useStore();
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400); };
  const done = uploads.filter((u) => u.status === "uploaded");
  const busy = uploads.some((u) => ["checking", "queued", "uploading"].includes(u.status));
  const rows = done.reduce((n, u) => n + (u.rows ?? 0), 0);
  const bytes = done.reduce((n, u) => n + u.size, 0);
  const review = ENTITIES.flatMap((e) => e.fields).filter((f) => f.status === "review").length;

  return (
    <Shell>
      <div className="grid lg:grid-cols-[1fr_320px] gap-5 items-start">
        <div className="space-y-5 min-w-0">
          <div className="grid md:grid-cols-2 gap-5">
            <Panel title="Source" tag="From" system={setup.sourceSystem} status={done.length ? `${done.length} files` : "No files yet"}>
              <Select label="Source system" value={setup.sourceSystem} options={SOURCE_SYSTEMS} onChange={(v) => updateSetup({ sourceSystem: v })} />
              <Select label="Source format" value={setup.sourceFormat} options={SOURCE_FORMATS} onChange={(v) => updateSetup({ sourceFormat: v })}
                hint={setup.sourceFormat !== "CSV files" ? "CSV only for now." : undefined} />
            </Panel>
            <Panel title="Destination" tag="To" system={setup.targetSystem} status={setup.output === "SQL inserts" ? `${setup.targetDatabase} inserts` : setup.output}>
              <Select label="Target system" value={setup.targetSystem} options={TARGET_SYSTEMS} onChange={(v) => updateSetup({ targetSystem: v })} />
              <Select label="Output" value={setup.output} options={OUTPUTS} onChange={(v) => updateSetup({ output: v })} />
              <div className={setup.output === "SQL inserts" ? "" : "opacity-50"}>
                <Select label="Target database" value={setup.targetDatabase} options={TARGET_DATABASES} onChange={(v) => updateSetup({ targetDatabase: v })} />
              </div>
            </Panel>
          </div>

          <BulkUpload onNotice={flash} />

          <div className="card p-5">
            <h2 className="section-title mb-4">Pipeline</h2>
            <ol className="space-y-2">
              <Step n={1} title="Upload source" desc="CSV files, folders or a zip." state={done.length ? "done" : busy ? "running" : "idle"}
                action={<a href="#source-files" className="btn-secondary w-full">{done.length ? "Manage files" : "Upload files"}</a>}
                extra={done.length ? <p className="text-[12px] text-muted">{done.length} files · {rows.toLocaleString()} rows · {formatBytes(bytes)}</p> : undefined} />
              <Step n={2} title="Run data quality" desc="Duplicates, orphans, deleted records still in use." state={steps.quality}
                action={<button className="btn-secondary w-full" disabled={steps.quality === "running" || busy || !done.length} onClick={async () => { await runStep("quality"); flash("Data quality checked"); }}>{steps.quality === "done" ? "Run again" : "Run data quality"}</button>}
                extra={quality && (quality.error
                  ? <p className="text-[12px] text-bad">Couldn’t run the checks: {quality.error}</p>
                  : <Link href="/quality" className="text-[12px] text-accent font-medium hover:underline">{quality.passed} of {quality.total} checks pass{quality.toReview ? ` · ${quality.toReview} duplicates to review` : ""} →</Link>)} />
              <Step n={3} title="Run canonical layer" desc="Source mapped to the 10 standard entities." state={steps.canonical}
                action={<button className="btn-secondary w-full" disabled={steps.quality !== "done" || steps.canonical === "running"} onClick={async () => { await runStep("canonical"); flash("Canonical layer ready"); }}>{steps.canonical === "done" ? "Run again" : "Run canonical layer"}</button>}
                extra={steps.canonical === "done" && <Link href="/canonical" className="text-[12px] text-accent font-medium hover:underline">Schema mapping{review ? ` · ${review} to review` : ""} →</Link>} />
              <Step n={4} title="Run target" desc={`Canonical data in ${setup.targetSystem} format.`} state={steps.target}
                action={<button className="btn-secondary w-full" disabled={steps.canonical !== "done" || steps.target === "running"} onClick={async () => { await runStep("target"); flash("Target values ready"); }}>{steps.target === "done" ? "Run again" : "Run target"}</button>}
                extra={steps.target === "done" && <Link href="/target" className="text-[12px] text-accent font-medium hover:underline">Destination data →</Link>} />
              <Step n={5} title="Get data" desc={setup.output === "SQL inserts" ? `${setup.targetDatabase} inserts` : setup.output} state="idle"
                action={<button className="btn-primary w-full" disabled={steps.target !== "done"} onClick={() => router.push("/target?get=1")}>Get data</button>} />
            </ol>
          </div>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-[120px]">
          <section className="card p-5">
            <h2 className="font-semibold mb-3">Uploaded</h2>
            <dl className="grid grid-cols-3 gap-2 text-center">
              <div><dt className="text-[11px] uppercase tracking-wide text-muted">Files</dt><dd className="text-[22px] font-bold tabular-nums">{done.length}</dd></div>
              <div><dt className="text-[11px] uppercase tracking-wide text-muted">Rows</dt><dd className="text-[22px] font-bold tabular-nums">{rows.toLocaleString()}</dd></div>
              <div><dt className="text-[11px] uppercase tracking-wide text-muted">Size</dt><dd className="text-[22px] font-bold tabular-nums">{formatBytes(bytes)}</dd></div>
            </dl>
          </section>
        </aside>
      </div>
      <Toast message={toast} />
    </Shell>
  );
}
