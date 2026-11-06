"use client";

// Bulk CSV upload: many files, whole folders or zips, by picker or drag & drop.
// Each file is checked in the browser (type, size, encoding, delimiter, header),
// then uploaded 3 at a time in resumable parts. See lib/upload.ts.
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useStore } from "../lib/store";
import {
  ACCEPT, MAX_FILES, checkFile, deleteStored, uploadMode, formatBytes, fromDrop, fromFileList, startUploads, uploadOne,
  type Picked, type StartedFile, type UploadItem,
} from "../lib/upload";
import { Check, Spinner } from "./ui";

// local uploads are quick small POSTs: more in flight; S3 multipart parts already run 3 per file
const CONCURRENT_FILES = uploadMode === "local" ? 6 : 3;
type Filter = "all" | "attention" | "active";

export function BulkUpload({ onNotice }: { onNotice: (m: string) => void }) {
  const { uploads, setUploads, projectId } = useStore();
  const ref = useRef(uploads);
  const controllers = useRef(new Map<string, AbortController>());
  const started = useRef(new Map<string, StartedFile>());
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  // `ref` is the queue's source of truth. Only adopt the store's list when it changed from OUTSIDE this
  // component (e.g. stored files loaded on start). Our own committed lists can arrive here late, after newer
  // commits: copying one back would wipe "uploaded" statuses, leave slots looking busy and stall the queue.
  const committed = useRef(new WeakSet<UploadItem[]>());
  useEffect(() => { if (!committed.current.has(uploads)) ref.current = uploads; }, [uploads]);
  useEffect(() => { folderInput.current?.setAttribute("webkitdirectory", ""); }, []);
  useEffect(() => () => controllers.current.forEach((c) => c.abort()), []);

  // Keep the ref and React state in step, so the queue sees changes immediately
  const commit = useCallback((fn: (items: UploadItem[]) => UploadItem[]) => {
    ref.current = fn(ref.current);
    committed.current.add(ref.current);
    setUploads(ref.current);
  }, [setUploads]);
  const patch = useCallback((id: string, changes: Partial<UploadItem>) => {
    commit((items) => items.map((it) => (it.id === id ? { ...it, ...changes } : it)));
  }, [commit]);

  const pump = useCallback(() => {
    const items = ref.current;
    let free = CONCURRENT_FILES - items.filter((i) => i.status === "uploading").length;
    for (const item of items) {
      if (free <= 0) break;
      if (item.status !== "queued") continue;
      free--;
      const ctrl = new AbortController();
      controllers.current.set(item.id, ctrl);
      patch(item.id, { status: "uploading", progress: 0, error: undefined });
      let last = 0;
      uploadOne(projectId, item, started.current.get(item.id), (p) => {
        const now = performance.now();
        if (now - last > 100 || p >= 1) { last = now; patch(item.id, { progress: p }); }
      }, ctrl.signal)
        .then(() => patch(item.id, { status: "uploaded", progress: 1 }))
        .catch((e: Error) => patch(item.id, ctrl.signal.aborted ? { status: "cancelled" } : { status: "failed", error: e.message }))
        .finally(() => { controllers.current.delete(item.id); pump(); });
    }
  }, [patch, projectId]);

  const addFiles = useCallback(async (picked: Picked[]) => {
    if (!picked.length) return;
    const seen = new Set(ref.current.map((i) => `${i.path}|${i.size}`));
    const fresh = picked.filter((p) => !seen.has(`${p.path}|${p.file.size}`));
    const room = MAX_FILES - ref.current.length;
    const take = fresh.slice(0, Math.max(0, room));
    const skipped = picked.length - take.length;
    if (skipped) onNotice(`${skipped} file${skipped > 1 ? "s" : ""} skipped (already added${room < fresh.length ? ` or over the ${MAX_FILES}-file limit` : ""})`);
    if (!take.length) return;

    const items: UploadItem[] = take.map((p, i) => ({
      id: `${Date.now()}-${i}-${Math.random().toString(36).slice(2, 8)}`,
      file: p.file, name: p.file.name, path: p.path, size: p.file.size,
      kind: p.file.name.toLowerCase().endsWith(".zip") ? "zip" : "csv",
      status: "checking", progress: 0, warnings: [],
    }));
    commit((all) => [...all, ...items]);
    setFilter("all");

    // Check files 6 at a time; reading a 64 KB sample each is fast
    const queue = [...items];
    await Promise.all(Array.from({ length: 6 }, async () => {
      for (let it = queue.shift(); it; it = queue.shift()) {
        const c = await checkFile(it.file!);
        patch(it.id, c.error ? { ...c, status: "invalid" } : { ...c, error: undefined, status: "queued" });
      }
    }));

    const ready = ref.current.filter((i) => items.some((n) => n.id === i.id) && i.status === "queued");
    try {
      const res = await startUploads(projectId, ready);
      res.forEach((v, id) => ("error" in v ? patch(id, { status: "invalid", error: v.error }) : started.current.set(id, v)));
    } catch (e) {
      ready.forEach((i) => patch(i.id, { status: "failed", error: (e as Error).message }));
    }
    pump();
  }, [commit, patch, pump, projectId, onNotice]);

  const retry = (ids: string[]) => {
    ids.forEach((id) => patch(id, { status: "queued", error: undefined, progress: 0 }));
    pump();
  };
  const cancel = (id: string) => controllers.current.get(id)?.abort();
  const remove = (ids: string[]) => {
    ids.forEach((id) => { controllers.current.get(id)?.abort(); started.current.delete(id); });
    // local mode: uploaded files are stored on the API's disk, so delete them there too
    ref.current.filter((i) => ids.includes(i.id) && i.status === "uploaded").forEach((i) => { deleteStored(projectId, i.name).catch(() => {}); });
    commit((all) => all.filter((i) => !ids.includes(i.id)));
  };

  const onDrop = async (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(await fromDrop(e.dataTransfer));
  };

  // ---- summary ----
  const s = useMemo(() => {
    const by = (st: UploadItem["status"][]) => uploads.filter((u) => st.includes(u.status));
    const active = by(["checking", "queued", "uploading"]);
    const totalBytes = uploads.reduce((n, u) => n + u.size, 0);
    const activeBytes = active.reduce((n, u) => n + u.size, 0);
    const doneBytes = active.reduce((n, u) => n + u.size * u.progress, 0);
    return {
      total: uploads.length,
      totalBytes,
      rows: uploads.filter((u) => u.status === "uploaded").reduce((n, u) => n + (u.rows ?? 0), 0),
      uploaded: by(["uploaded"]).length,
      active,
      activeProgress: activeBytes ? doneBytes / activeBytes : 0,
      failed: by(["failed"]),
      invalid: by(["invalid", "cancelled"]),
      warned: uploads.filter((u) => u.status === "uploaded" && u.warnings.length && u.kind === "csv"),
    };
  }, [uploads]);
  const attention = s.failed.length + s.invalid.length + s.warned.length;

  const shown = uploads.filter((u) =>
    filter === "all" ? true
      : filter === "active" ? ["checking", "queued", "uploading"].includes(u.status)
        : ["failed", "invalid", "cancelled"].includes(u.status) || (u.warnings.length > 0 && u.kind === "csv"));

  return (
    <section
      className={`card relative ${dragging ? "ring-2 ring-accent/50" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
      onDrop={onDrop}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4 pb-3">
        <div>
          <h2 className="font-semibold">Source files</h2>
          <p className="text-[12px] text-muted mt-0.5">
            {s.total ? <>{s.total.toLocaleString()} file{s.total > 1 ? "s" : ""} · {formatBytes(s.totalBytes)}{s.rows ? <> · {s.rows.toLocaleString()} rows</> : null}</> : "No files yet"}          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn-secondary h-8 text-[12px]" onClick={() => fileInput.current?.click()}>Choose files</button>
          <button type="button" className="btn-secondary h-8 text-[12px]" onClick={() => folderInput.current?.click()}>Choose folder</button>
        </div>
        <input ref={fileInput} type="file" multiple accept={ACCEPT} hidden onChange={(e) => { addFiles(fromFileList(e.target.files)); e.target.value = ""; }} />
        <input ref={folderInput} type="file" multiple hidden onChange={(e) => { addFiles(fromFileList(e.target.files)); e.target.value = ""; }} />
      </div>

      {/* Drop zone: large when empty, a slim strip once files are added */}
      <div className="px-5">
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className={`w-full rounded-lg border border-dashed transition-colors text-center ${dragging ? "border-accent bg-accent-soft" : "border-[#B9CBF0] bg-[#F5F8FF] hover:bg-sunken"} ${s.total ? "py-3" : "py-10"}`}
        >
          <span className="block text-[13px] font-medium">{dragging ? "Drop to add" : "Drag CSV files, folders or a .zip here"}</span>
          <span className="block text-[12px] text-faint">Up to {MAX_FILES.toLocaleString()} files, 5 GB each · .csv .tsv .txt .zip</span>
        </button>
      </div>

      {s.active.length > 0 && (
        <div className="px-5 pt-3">
          <div className="flex justify-between text-[12px] text-muted mb-1">
            <span className="flex items-center gap-1.5"><Spinner className="w-3 h-3 text-accent" /> Uploading {s.active.length} file{s.active.length > 1 ? "s" : ""}…</span>
            <span className="tabular-nums">{Math.round(s.activeProgress * 100)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-sunken overflow-hidden"><div className="h-full bg-accent transition-[width] duration-200" style={{ width: `${s.activeProgress * 100}%` }} /></div>
        </div>
      )}

      {s.total > 0 && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4 pb-2">
            <div className="flex gap-1" role="tablist" aria-label="Filter files">
              {([["all", `All ${s.total}`], ["active", `In progress ${s.active.length}`], ["attention", `Needs attention ${attention}`]] as [Filter, string][])
                .filter(([k]) => k === "all" || (k === "active" ? s.active.length : attention))
                .map(([k, label]) => (
                  <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)} className={`h-7 px-3 rounded-full text-[12px] transition-colors ${filter === k ? "bg-ink text-white" : "text-muted hover:bg-sunken"}`}>{label}</button>
                ))}
            </div>
            <div className="flex gap-1">
              {s.failed.length > 0 && <button className="btn-ghost h-7 px-2.5 text-[12px]" onClick={() => retry(s.failed.map((f) => f.id))}>Retry failed ({s.failed.length})</button>}
              {s.invalid.length > 0 && <button className="btn-ghost h-7 px-2.5 text-[12px]" onClick={() => remove(s.invalid.map((f) => f.id))}>Remove rejected ({s.invalid.length})</button>}
            </div>
          </div>

          <ul className="mx-5 mb-5 border border-line rounded-lg divide-y divide-line max-h-[380px] overflow-y-auto">
            {shown.map((u) => (
              <FileRow
                key={u.id}
                item={u}
                open={expanded === u.id}
                onToggle={() => setExpanded(expanded === u.id ? null : u.id)}
                onRetry={() => retry([u.id])}
                onCancel={() => cancel(u.id)}
                onRemove={() => remove([u.id])}
              />
            ))}
            {shown.length === 0 && <li className="px-4 py-6 text-center text-[13px] text-muted">Nothing here.</li>}
          </ul>
        </>
      )}
    </section>
  );
}

function FileRow({ item: u, open, onToggle, onRetry, onCancel, onRemove }: {
  item: UploadItem; open: boolean; onToggle: () => void; onRetry: () => void; onCancel: () => void; onRemove: () => void;
}) {
  const folder = u.path.includes("/") ? u.path.slice(0, u.path.lastIndexOf("/")) : null;
  const canExpand = (u.columns?.length ?? 0) > 0 || u.warnings.length > 0;
  const details = u.kind === "zip"
    ? "Zip archive"
    : u.columns ? `${u.columns.length} column${u.columns.length === 1 ? "" : "s"}${u.rows !== undefined ? ` · ${u.rowsExact ? "" : "≈ "}${u.rows.toLocaleString()} row${u.rows === 1 ? "" : "s"}` : ""}` : null;
  const ext = u.name.includes(".") ? u.name.split(".").pop()!.slice(0, 4) : "file";

  return (
    <li className={u.status === "invalid" || u.status === "failed" ? "bg-bad-soft/30" : ""}>
      <div className="flex items-center gap-3 px-3 py-2.5">
        <span className={`grid place-items-center w-8 h-8 shrink-0 rounded-md text-[10px] font-semibold uppercase ${u.kind === "zip" ? "bg-accent-soft text-accent" : "bg-sunken text-muted"}`}>{ext}</span>
        <button type="button" onClick={canExpand ? onToggle : undefined} className={`flex-1 min-w-0 text-left ${canExpand ? "cursor-pointer" : "cursor-default"}`} aria-expanded={canExpand ? open : undefined}>
          <span className="block font-mono text-[12px] truncate">{u.name}</span>
          <span className="block text-[11px] text-muted truncate">
            {formatBytes(u.size)}{details && <> · {details}</>}{folder && <span className="text-faint"> · {folder}/</span>}
          </span>
        </button>

        <div className="w-[190px] shrink-0 text-[12px] hidden sm:block">
          <Status item={u} onToggle={onToggle} />
        </div>

        <div className="flex gap-1 shrink-0">
          {(u.status === "failed" || u.status === "cancelled") && u.file && <button className="btn-ghost h-7 px-2 text-[12px]" onClick={onRetry}>Retry</button>}
          {u.status === "uploading" && <button className="btn-ghost h-7 px-2 text-[12px]" onClick={onCancel}>Cancel</button>}
          {u.status !== "uploading" && <button className="btn-ghost h-7 w-7 px-0 text-[13px]" onClick={onRemove} aria-label={`Remove ${u.name}`}>✕</button>}
        </div>
      </div>
      <div className="sm:hidden px-3 pb-2.5 -mt-1 text-[12px]"><Status item={u} onToggle={onToggle} /></div>

      {open && canExpand && (
        <div className="px-3 pb-3 pl-14 space-y-2">
          {u.warnings.map((w) => <p key={w} className="text-[12px] text-warn">⚠ {w}</p>)}
          {u.columns && u.columns.length > 0 && (
            <div>
              <p className="text-[11px] text-muted mb-1">Columns{u.delimiter && u.delimiter !== "," ? ` (separated by ${u.delimiter === "\t" ? "tabs" : `“${u.delimiter}”`})` : ""}</p>
              <div className="flex flex-wrap gap-1">
                {u.columns.map((c, i) => <span key={i} className="pill bg-sunken text-muted font-mono text-[11px]">{c || <em>blank</em>}</span>)}
              </div>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function Status({ item: u, onToggle }: { item: UploadItem; onToggle: () => void }) {
  switch (u.status) {
    case "checking":
      return <span className="text-muted flex items-center gap-1.5"><Spinner className="w-3 h-3" /> Checking…</span>;
    case "queued":
      return <span className="text-muted">Waiting…</span>;
    case "uploading":
      return (
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 rounded-full bg-sunken overflow-hidden"><div className="h-full bg-accent" style={{ width: `${u.progress * 100}%` }} /></div>
          <span className="tabular-nums text-muted w-9 text-right">{Math.round(u.progress * 100)}%</span>
        </div>
      );
    case "uploaded":
      return u.warnings.length && u.kind === "csv"
        ? <button onClick={onToggle} className="text-warn hover:underline text-left">⚠ Uploaded, {u.warnings.length} warning{u.warnings.length > 1 ? "s" : ""}</button>
        : <span className="text-ok flex items-center gap-1"><Check /> Uploaded</span>;
    case "invalid":
      return <span className="text-bad leading-snug block">{u.error}</span>;
    case "failed":
      return <span className="text-bad leading-snug block">Failed: {u.error}</span>;
    case "cancelled":
      return <span className="text-muted">Cancelled</span>;
    default:
      return null;
  }
}
