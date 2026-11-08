"use client";

// Destination data: the target layer, middle tier -> RecruitPlatform_Target.dbo.<Table>.
//   Target data: the loaded target tables. Developer view: each table's INSERT script (editable fields).
//   Get data: the target tables as CSV files or SQL inserts.
import { useEffect, useState } from "react";
import { LayerData, LayerScripts, ViewToggle, useView, type LayerDetail } from "../../components/LayerView";
import { Modal, PageHeader, Shell, Toast } from "../../components/ui";
import { api } from "../../lib/api";
import { useStore } from "../../lib/store";

type TargetEntity = { file: string; columns: string[]; preview: (string | null)[][] };

async function loadTarget(): Promise<TargetEntity[]> {
  const d = await api<LayerDetail>("/layers/target");
  return Promise.all(d.entities.map(async (e) => {
    const r = await api<{ rows: Record<string, string | null>[] }>(`/layers/target/${encodeURIComponent(e.key)}/rows?limit=2000`);
    const columns = e.inserts[0].fields.map((f) => f.column);
    return { file: `${e.key}.csv`, columns, preview: r.rows.map((row) => columns.map((c) => row[c] ?? null)) };
  }));
}

export default function TargetPage() {
  const [view, setView] = useView("target-view");
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("get") === "1") setOpen(true);
  }, []);

  return (
    <Shell>
      <PageHeader title="Destination data" actions={
        <div className="flex items-center gap-3">
          <ViewToggle view={view} onChange={setView} dataLabel="Target data" />
          <button className="btn-primary h-9" onClick={() => setOpen(true)}>Get data</button>
        </div>
      } />

      {view === "developer" ? <LayerScripts layer="target" initial="Applicant" /> : <LayerData layer="target" initial="Applicant" />}
      <Rejects />

      <GetData open={open} onClose={() => setOpen(false)} onDownload={(m) => { setToast(m); setTimeout(() => setToast(null), 2200); }} />
      <Toast message={toast} />
    </Shell>
  );
}

// ---- Rejected and flagged rows (dbo.MigrationRejects) ----

type Reject = { table: string; key: string | null; action: "rejected" | "flagged"; reason: string };

function Rejects() {
  const [rows, setRows] = useState<Reject[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { api<Reject[]>("/layers/target/rejects").then(setRows).catch(() => setRows([])); }, []);
  if (!rows || rows.length === 0) return null;
  const groups = new Map<string, Reject[]>();
  for (const r of rows) groups.set(`${r.action}|${r.reason}`, [...(groups.get(`${r.action}|${r.reason}`) ?? []), r]);
  const n = (a: string) => rows.filter((r) => r.action === a).length;
  return (
    <section className="card mt-5">
      <div className="px-5 pt-4 pb-3 border-b border-line flex flex-wrap items-baseline gap-x-4">
        <h2 className="font-semibold">Not loaded or flagged</h2>
        <span className="text-[12.5px] text-muted">{n("rejected")} rejected (not loaded) · {n("flagged")} flagged (loaded)</span>
      </div>
      <ul className="divide-y divide-line">
        {[...groups.entries()].map(([k, list]) => {
          const [action, reason] = k.split("|");
          const tables = [...new Set(list.map((r) => r.table))];
          return (
            <li key={k}>
              <button className="w-full flex items-center gap-3 px-5 py-2.5 text-left text-[13px] hover:bg-[#F5F8FF]" onClick={() => setOpen(open === k ? null : k)}>
                <span className={`pill py-0 ${action === "rejected" ? "bg-bad-soft text-bad" : "bg-warn-soft text-warn"}`}>{action}</span>
                <span className="flex-1">{reason}</span>
                <span className="text-[12px] text-muted font-mono">{tables.join(", ")}</span>
                <span className="tabular-nums font-semibold w-10 text-right">{list.length}</span>
              </button>
              {open === k && (
                <p className="px-5 pb-3 text-[12px] font-mono text-muted">{list.map((r) => `${r.table} ${r.key ?? "?"}`).join(" · ")}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// ---- Get data ----

function csvOf(t: TargetEntity) {
  const esc = (v: string | null) => (v === null ? "" : /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return [t.columns.join(","), ...t.preview.map((r) => r.map(esc).join(","))].join("\n");
}

// Same rules as pipeline/deliver/sql_inserts.py: no character from the data is
// written as SQL text. Values are hex-encoded; names must match a strict pattern.
const IDENT = /^[A-Za-z_][A-Za-z0-9_.]{0,62}$/;
const hex = (bytes: Iterable<number>) => Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");

function sqlLiteral(v: string | null, dialect: string) {
  if (v === null) return "NULL";
  if (v === "") return dialect.startsWith("SQL Server") ? "N''" : "''";
  if (dialect.startsWith("MySQL")) return `CONVERT(X'${hex(new TextEncoder().encode(v))}' USING utf8mb4)`;
  if (dialect.startsWith("SQL Server")) {
    // NVARCHAR is UTF-16LE: each JS code unit becomes low byte, high byte
    const utf16le = [...Array(v.length).keys()].flatMap((i) => [v.charCodeAt(i) & 0xff, v.charCodeAt(i) >> 8]);
    return `CAST(0x${hex(utf16le)} AS NVARCHAR(MAX))`;
  }
  if (v.includes("\0")) throw new Error("Postgres cannot store NUL characters");
  return `convert_from(decode('${hex(new TextEncoder().encode(v))}', 'hex'), 'UTF8')`;
}

function sqlOf(t: TargetEntity, dialect: string) {
  const q = (s: string) => {
    if (!IDENT.test(s)) throw new Error(`Unsafe identifier: ${s}`);
    return dialect.startsWith("MySQL") ? `\`${s}\`` : dialect.startsWith("SQL Server") ? `[${s}]` : `"${s}"`;
  };
  const table = q(t.file.replace(".csv", ""));
  const [begin, commit] = dialect.startsWith("MySQL")
    ? ["SET NAMES utf8mb4;\nSTART TRANSACTION;", "COMMIT;"]
    : dialect.startsWith("SQL Server")
      ? ["SET XACT_ABORT ON;\nBEGIN TRANSACTION;", "COMMIT TRANSACTION;"]
      : ["SET client_encoding = 'UTF8';\nSET standard_conforming_strings = on;\nBEGIN;", "COMMIT;"];
  const rows = t.preview.map((r) => `(${r.map((v) => sqlLiteral(v, dialect)).join(", ")})`).join(",\n");
  return `${begin}\nINSERT INTO ${table} (${t.columns.map(q).join(", ")}) VALUES\n${rows};\n${commit}\n`;
}

function save(name: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

function GetData({ open, onClose, onDownload }: { open: boolean; onClose: () => void; onDownload: (m: string) => void }) {
  const { setup } = useStore();
  const [tables, setTables] = useState<TargetEntity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sql = setup.output === "SQL inserts";
  useEffect(() => { if (open && !tables) loadTarget().then(setTables).catch((e: Error) => setError(e.message)); }, [open, tables]);
  const files = (tables ?? []).map((t) => ({ t, name: sql ? t.file.replace(".csv", ".sql") : t.file }));

  return (
    <Modal open={open} onClose={onClose} title="Get data" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={!tables} onClick={() => { files.forEach(({ t, name }) => save(name, sql ? sqlOf(t, setup.targetDatabase) : csvOf(t))); onDownload(`${files.length} files downloaded`); }}>Download all</button>
      </>
    }>
      {error ? <p className="text-[13px] text-bad">{error}</p> : !tables ? <p className="text-[13px] text-muted">Loading…</p> : (
        <ul className="divide-y divide-line border border-line rounded-lg">
          {files.map(({ t, name }) => (
            <li key={name} className="flex items-center gap-3 px-3 py-2.5">
              <span className="grid place-items-center w-8 h-8 rounded-md bg-sunken text-[10px] font-semibold text-muted uppercase">{sql ? "sql" : "csv"}</span>
              <div className="flex-1 min-w-0">
                <p className="font-mono text-[12px] truncate">{name}</p>
                <p className="text-[11px] text-muted">{t.preview.length.toLocaleString()} rows</p>
              </div>
              <button className="btn-ghost h-8 px-3 text-[12px]" onClick={() => { save(name, sql ? sqlOf(t, setup.targetDatabase) : csvOf(t)); onDownload(`${name} downloaded`); }}>Download</button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
