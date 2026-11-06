// Bulk upload: collect files (picker, folder, drag & drop), check them in the
// browser, then upload in resumable parts straight to storage.
// API side: backend/app/routers/uploads.py.
//
// NEXT_PUBLIC_UPLOAD_MODE=local (default) → files are posted to the API and stored on its disk
//                                          (backend/app/routers/local_files.py); no cloud storage needed
// NEXT_PUBLIC_UPLOAD_MODE=api              → resumable multipart uploads to object storage (S3)
// NEXT_PUBLIC_UPLOAD_MODE=demo             → progress is simulated, nothing leaves the browser

export type UploadStatus = "checking" | "ready" | "invalid" | "queued" | "uploading" | "uploaded" | "failed" | "cancelled";

export type UploadItem = {
  id: string;
  file?: File; // absent for files uploaded in an earlier session
  name: string;
  path: string; // folder path for folder uploads, else the name
  size: number;
  kind: "csv" | "zip";
  status: UploadStatus;
  progress: number; // 0–1
  error?: string;
  warnings: string[];
  columns?: string[];
  delimiter?: string;
  rows?: number;
  rowsExact?: boolean;
};

export const ACCEPT = ".csv,.tsv,.txt,.zip";
export const MAX_FILE_BYTES = 5 * 1024 ** 3; // matches MAX_UPLOAD_FILE_BYTES on the API
export const MAX_FILES = 2000;
const EXTENSIONS = ["csv", "tsv", "txt", "zip"];
const IGNORED = /^(\.ds_store|thumbs\.db|desktop\.ini|\._.*)$/i;
const SAMPLE_BYTES = 64 * 1024;
const MODE: "local" | "api" | "demo" =
  process.env.NEXT_PUBLIC_UPLOAD_MODE === "api" ? "api" : process.env.NEXT_PUBLIC_UPLOAD_MODE === "demo" ? "demo" : "local";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const uploadMode = MODE;

export function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

// ---- collecting files ----

export type Picked = { file: File; path: string };

export function fromFileList(list: FileList | null): Picked[] {
  return Array.from(list ?? [])
    .filter((f) => !IGNORED.test(f.name))
    .map((f) => ({ file: f, path: (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name }));
}

/** Files from a drop, walking into dropped folders. */
export async function fromDrop(dt: DataTransfer): Promise<Picked[]> {
  const entries = Array.from(dt.items)
    .map((i) => (i.kind === "file" ? i.webkitGetAsEntry?.() : null))
    .filter((e): e is FileSystemEntry => !!e);
  if (!entries.length) return fromFileList(dt.files);
  const out: Picked[] = [];
  const walk = async (entry: FileSystemEntry, prefix: string): Promise<void> => {
    if (out.length >= MAX_FILES) return;
    if (entry.isFile) {
      const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej));
      if (!IGNORED.test(file.name)) out.push({ file, path: prefix + file.name });
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      // readEntries returns results in batches; keep reading until an empty batch
      for (;;) {
        const batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej));
        if (!batch.length) break;
        for (const child of batch) await walk(child, `${prefix}${entry.name}/`);
      }
    }
  };
  for (const e of entries) await walk(e, "");
  return out;
}

// ---- checking a file before upload ----

type Check = Pick<UploadItem, "kind" | "columns" | "delimiter" | "rows" | "rowsExact" | "warnings"> & { error?: string };

export async function checkFile(file: File): Promise<Check> {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const kind: "csv" | "zip" = ext === "zip" ? "zip" : "csv";
  const base = { kind, warnings: [] as string[] };
  if (!EXTENSIONS.includes(ext)) return { ...base, error: ext === "xlsx" || ext === "xls" ? "Excel files aren’t supported yet. Save each sheet as CSV." : "Only .csv, .tsv, .txt and .zip files can be uploaded." };
  if (file.size === 0) return { ...base, error: "This file is empty." };
  if (file.size > MAX_FILE_BYTES) return { ...base, error: `This file is larger than ${formatBytes(MAX_FILE_BYTES)}.` };

  const head = new Uint8Array(await file.slice(0, SAMPLE_BYTES).arrayBuffer());
  const isZip = head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04;
  if (kind === "zip") {
    return isZip ? { ...base, warnings: ["Unpacked and checked on the server."] } : { ...base, error: "This isn’t a valid zip file." };
  }
  if (isZip) return { ...base, error: "This looks like an Excel or zip file renamed to .csv." };

  // Encoding
  let text: string;
  const warnings: string[] = [];
  if ((head[0] === 0xff && head[1] === 0xfe) || (head[0] === 0xfe && head[1] === 0xff)) {
    text = new TextDecoder(head[0] === 0xff ? "utf-16le" : "utf-16be").decode(head);
    warnings.push("Saved as UTF-16. It will be converted to UTF-8.");
  } else {
    if (head.subarray(0, 4096).includes(0)) return { ...base, error: "This looks like a binary file, not text." };
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(trimPartialUtf8(head, file.size > SAMPLE_BYTES));
    } catch {
      text = new TextDecoder("windows-1252").decode(head);
      warnings.push("Not UTF-8. It will be read as Windows-1252 (common for Excel exports). Check £ signs and accents.");
    }
  }
  text = text.replace(/^﻿/, "");

  const firstLine = text.split(/\r?\n/, 1)[0] ?? "";
  const delimiter = detectDelimiter(firstLine, ext);
  const columns = splitRow(firstLine, delimiter).map((c) => c.trim());

  if (columns.length <= 1) warnings.push("Only one column found. Check the delimiter.");
  if (columns.some((c) => c === "")) warnings.push("Some columns have no name.");
  const dupes = columns.filter((c, i) => c && columns.indexOf(c) !== i);
  if (dupes.length) warnings.push(`Repeated column names: ${Array.from(new Set(dupes)).slice(0, 3).join(", ")}.`);
  if (columns.length > 1 && columns.every((c) => /^[\d.,\-/: ]+$/.test(c) || c === "")) warnings.push("The first row looks like data, not column names.");

  // Rows: exact for small files, estimated from the sample for big ones
  const lines = text.split(/\r?\n/);
  let rows: number, rowsExact: boolean;
  if (file.size <= SAMPLE_BYTES) {
    rows = Math.max(0, lines.filter((l) => l.length).length - 1);
    rowsExact = true;
  } else {
    const sampleLines = Math.max(1, lines.length - 1); // last line is probably cut off
    rows = Math.max(0, Math.round((file.size / head.length) * sampleLines) - 1);
    rowsExact = false;
  }
  if (rowsExact && rows === 0) warnings.push("Only a header row, no data.");

  return { kind, columns, delimiter, rows, rowsExact, warnings };
}

/** Drop a multi-byte character cut in half at the end of the sample. */
function trimPartialUtf8(bytes: Uint8Array, truncated: boolean) {
  if (!truncated) return bytes;
  let end = bytes.length;
  for (let i = 1; i <= 3 && end - i >= 0; i++) {
    const b = bytes[end - i];
    if ((b & 0xc0) === 0xc0) return bytes.subarray(0, end - i); // lead byte of a cut character
    if ((b & 0x80) === 0) break;
  }
  return bytes;
}

function detectDelimiter(line: string, ext: string) {
  if (ext === "tsv") return "\t";
  const counts = [",", ";", "\t", "|"].map((d) => [d, splitRow(line, d).length] as const);
  counts.sort((a, b) => b[1] - a[1]);
  return counts[0][1] > 1 ? counts[0][0] : ",";
}

function splitRow(line: string, delimiter: string) {
  const out: string[] = [];
  let cur = "", quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === delimiter) { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out;
}

// ---- uploading ----

type Progress = (fraction: number) => void;

export type StartedFile = { token: string; part_size: number; part_count: number };

/** Ask the API to start uploads for many files at once. Demo mode skips this. */
export async function startUploads(projectId: string, items: UploadItem[]): Promise<Map<string, StartedFile | { error: string }>> {
  const result = new Map<string, StartedFile | { error: string }>();
  if (MODE !== "api") return result;
  for (let i = 0; i < items.length; i += 1000) {
    const chunk = items.slice(i, i + 1000);
    const res = await fetch(`${API}/projects/${encodeURIComponent(projectId)}/uploads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ files: chunk.map((it) => ({ name: it.name, size: it.size, relative_path: it.path })) }),
    });
    if (!res.ok) throw new Error(`Couldn’t start upload (${res.status})`);
    const body = await res.json();
    for (const a of body.accepted) result.set(chunk[a.client_index].id, a);
    for (const r of body.rejected) result.set(chunk[r.client_index].id, { error: r.reason });
  }
  return result;
}

export async function uploadOne(projectId: string, item: UploadItem, started: StartedFile | undefined, onProgress: Progress, signal: AbortSignal) {
  if (!item.file) throw new Error("File is no longer available. Add it again.");
  if (MODE === "demo") return simulate(item.size, onProgress, signal);
  if (MODE === "local") return postLocal(projectId, item.file, onProgress, signal);
  if (!started) throw new Error("Upload was not started");

  const { token, part_size, part_count } = started;
  const post = async (path: string, body: unknown) => {
    const res = await fetch(`${API}/projects/${encodeURIComponent(projectId)}/uploads/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify(body), signal,
    });
    if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? `Upload failed (${res.status})`);
    return res.status === 204 ? null : res.json();
  };

  const sent = new Array<number>(part_count).fill(0);
  const report = () => onProgress(sent.reduce((a, b) => a + b, 0) / item.size);
  const etags: { part_number: number; etag: string }[] = [];
  const numbers = Array.from({ length: part_count }, (_, i) => i + 1);

  try {
    for (let i = 0; i < numbers.length; i += 100) {
      const batch = numbers.slice(i, i + 100);
      const { urls } = await post("parts", { token, part_numbers: batch });
      // 3 parts in flight per file
      let next = 0;
      const worker = async () => {
        while (next < batch.length) {
          const n = batch[next++];
          const blob = item.file!.slice((n - 1) * part_size, n * part_size);
          const etag = await withRetry(() => putPart(urls[n], blob, (b) => { sent[n - 1] = b; report(); }, signal), signal);
          etags.push({ part_number: n, etag });
        }
      };
      await Promise.all([worker(), worker(), worker()]);
    }
    await post("complete", { token, parts: etags });
  } catch (e) {
    if (signal.aborted) post("abort", { token }).catch(() => {});
    throw e;
  }
}

/** Local mode: one multipart POST per file, with upload progress. */
function postLocal(projectId: string, file: File, onProgress: Progress, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}/projects/${encodeURIComponent(projectId)}/files`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        let detail = `Upload failed (${xhr.status})`;
        try { detail = JSON.parse(xhr.responseText).detail ?? detail; } catch { /* keep default */ }
        return reject(new Error(detail));
      }
      const body = JSON.parse(xhr.responseText || "{}");
      if (body.rejected?.length && !body.saved?.length) return reject(new Error(body.rejected[0].reason));
      onProgress(1);
      resolve();
    };
    xhr.onerror = () => reject(new Error("Couldn’t reach the API. Is it running on " + API + "?"));
    xhr.onabort = () => reject(new DOMException("Cancelled", "AbortError"));
    signal.addEventListener("abort", () => xhr.abort(), { once: true });
    const form = new FormData();
    form.append("files", file, file.name);
    xhr.send(form);
  });
}

/** Files already stored for the project (local mode), shown as uploaded. */
export type StoredFile = { name: string; size: number; rows: number; columns: string[]; delimiter: string; table: string };

export async function listStored(projectId: string): Promise<UploadItem[]> {
  if (MODE !== "local") return [];
  const res = await fetch(`${API}/projects/${encodeURIComponent(projectId)}/files`);
  if (!res.ok) throw new Error(`Couldn’t list files (${res.status})`);
  const files: StoredFile[] = await res.json();
  return files.map((f) => ({
    id: `stored-${f.name}`, name: f.name, path: f.name, size: f.size, kind: "csv", status: "uploaded", progress: 1,
    warnings: [], columns: f.columns, delimiter: f.delimiter, rows: f.rows, rowsExact: true,
  }));
}

export async function deleteStored(projectId: string, name: string) {
  if (MODE !== "local") return;
  await fetch(`${API}/projects/${encodeURIComponent(projectId)}/files/${encodeURIComponent(name)}`, { method: "DELETE" });
}

function putPart(url: string, blob: Blob, onBytes: (n: number) => void, signal: AbortSignal) {
  // XHR rather than fetch: fetch can't report upload progress
  return new Promise<string>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => onBytes(e.loaded);
    xhr.onload = () => {
      const etag = xhr.getResponseHeader("ETag");
      if (xhr.status >= 200 && xhr.status < 300 && etag) { onBytes(blob.size); resolve(etag); }
      else reject(new Error(etag ? `Storage returned ${xhr.status}` : "Storage didn’t return an ETag (check bucket CORS)"));
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.onabort = () => reject(new DOMException("Cancelled", "AbortError"));
    signal.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(blob);
  });
}

async function withRetry<T>(fn: () => Promise<T>, signal: AbortSignal, attempts = 4): Promise<T> {
  for (let i = 1; ; i++) {
    try { return await fn(); }
    catch (e) {
      if (signal.aborted || i >= attempts) throw e;
      await new Promise((r) => setTimeout(r, 500 * 2 ** (i - 1))); // 0.5s, 1s, 2s
    }
  }
}

function simulate(size: number, onProgress: Progress, signal: AbortSignal) {
  // ~25 MB/s, at least 0.8s so small files still show progress
  const duration = Math.max(800, (size / (25 * 1024 * 1024)) * 1000);
  const start = performance.now();
  return new Promise<void>((resolve, reject) => {
    const tick = () => {
      if (signal.aborted) return reject(new DOMException("Cancelled", "AbortError"));
      const f = Math.min(1, (performance.now() - start) / duration);
      onProgress(f);
      if (f >= 1) resolve(); else setTimeout(tick, 120);
    };
    tick();
  });
}
