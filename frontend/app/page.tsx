"use client";

// Source upload: the start page (step 1). Next: Data quality (/quality), then the migration workflow.
// Files are checked in the browser (type, size, encoding, delimiter, header), uploaded to the
// API (local mode: backend/app/routers/local_files.py), then checked by the data quality rules.
import Link from "next/link";
import { useState } from "react";
import { BulkUpload } from "../components/BulkUpload";
import { Select, Shell, Toast } from "../components/ui";
import { SOURCE_FORMATS, SOURCE_SYSTEMS } from "../lib/mock";
import { useStore } from "../lib/store";
import { formatBytes, uploadMode } from "../lib/upload";

export default function UploadPage() {
  const { setup, updateSetup, uploads } = useStore();
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400); };
  const done = uploads.filter((u) => u.status === "uploaded");
  const busy = uploads.some((u) => ["checking", "queued", "uploading"].includes(u.status));
  const rows = done.reduce((n, u) => n + (u.rows ?? 0), 0);
  const bytes = done.reduce((n, u) => n + u.size, 0);

  return (
    <Shell>
      <div className="grid lg:grid-cols-[1fr_320px] gap-5 items-start">
        <div className="space-y-5 min-w-0">
          <div>
            <h2 className="section-title">Source data</h2>
          </div>

          <section className="card p-5 grid sm:grid-cols-2 gap-4">
            <Select label="Source system" value={setup.sourceSystem} options={SOURCE_SYSTEMS} onChange={(v) => updateSetup({ sourceSystem: v })} />
            <Select label="Source format" value={setup.sourceFormat} options={SOURCE_FORMATS} onChange={(v) => updateSetup({ sourceFormat: v })}
              hint={setup.sourceFormat !== "CSV files" ? "Backups, JSON and API connections are coming next. Export to CSV for now." : undefined} />
          </section>

          {uploadMode === "demo" && (
            <p className="card p-4 text-[13px] text-muted">Demo mode: uploads are simulated and nothing leaves your browser. Unset <code className="font-mono">NEXT_PUBLIC_UPLOAD_MODE</code> to store files through the API.</p>
          )}

          <BulkUpload onNotice={flash} />
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
          <section className="card p-5 space-y-3">
            <h2 className="font-semibold">Next</h2>
            <p className="text-[13px] text-muted">Check the source data for duplicates, orphans and deleted records still in use.</p>
            {done.length && !busy
              ? <Link href="/quality" className="btn-primary w-full">Check data quality →</Link>
              : <button className="btn-primary w-full" disabled title="Upload the source data first">Check data quality →</button>}
          </section>
        </aside>
      </div>
      <Toast message={toast} />
    </Shell>
  );
}
