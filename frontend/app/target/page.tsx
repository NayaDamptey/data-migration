"use client";

// Screen 4: Target values + delivery. Sketch: docs/sketches/4-target-values.jpeg
// Left: entity → target file. Right: preview rows, ready / warnings / rejected, issues.
// Get data: list of output files with download links, plus rejected rows.
// API (later): GET /runs/:id/target/:entity, GET /runs/:id/outputs
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Modal, PageHeader, Shell, Toast } from "../../components/ui";
import { TARGET, type TargetEntity } from "../../lib/mock";
import { useStore } from "../../lib/store";

export default function TargetPage() {
  const router = useRouter();
  const { setup, steps } = useStore();
  const [active, setActive] = useState("candidates");
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("get") === "1") setOpen(true);
  }, []);

  const t = TARGET.find((x) => x.key === active)!;
  const total = t.ready + t.warnings + t.rejected;
  const sum = (k: "ready" | "warnings" | "rejected") => TARGET.reduce((n, x) => n + x[k], 0);

  return (
    <Shell>
      <PageHeader
        title="Target values"
        sub={`Your data in ${setup.targetSystem} format, checked and ready to load.`}
        actions={
          <div className="flex gap-4 text-[13px]">
            <Kpi label="Ready" value={sum("ready")} cls="text-ok" />
            <Kpi label="Warnings" value={sum("warnings")} cls="text-warn" />
            <Kpi label="Rejected" value={sum("rejected")} cls="text-bad" />
          </div>
        }
      />

      {steps.target !== "done" && (
        <div className="mb-4 rounded-lg bg-accent-soft text-accent-ink px-4 py-2.5 text-[13px]">
          Showing the last target run (v3). Run target again from Set up to include your latest review.
        </div>
      )}

      <div className="card overflow-hidden grid md:grid-cols-[250px_1fr] min-h-[620px]">
        <nav aria-label="Entities" className="border-b md:border-b-0 md:border-r border-line bg-[#F5F8FF]">
          <p className="px-4 pt-4 pb-2 text-[12px] font-medium text-muted">Entities</p>
          <ul className="flex md:block overflow-x-auto pb-2 md:pb-4 px-2 gap-1">
            {TARGET.map((e) => {
              const on = e.key === active;
              return (
                <li key={e.key} className="shrink-0">
                  <button
                    onClick={() => setActive(e.key)}
                    className={`w-full rounded-lg px-3 py-2 text-left transition-colors ${on ? "bg-surface shadow-card border border-line" : "border border-transparent hover:bg-sunken"}`}
                  >
                    <span className="flex items-center gap-2 text-[13px]">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${e.rejected ? "bg-bad" : e.warnings ? "bg-warn" : "bg-ok"}`} />
                      <span className={`flex-1 ${on ? "font-medium" : ""}`}>{e.label}</span>
                    </span>
                    <span className="block pl-4 text-[11px] font-mono text-muted">→ {e.file}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <section className="flex flex-col min-w-0">
          <div className="px-5 pt-4 pb-4 border-b border-line">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <h2 className="text-[17px] font-semibold">{t.label}</h2>
              <span className="font-mono text-[12px] text-muted">{t.file}</span>
            </div>

            <div className="grid grid-cols-3 gap-3 mt-3 max-w-[520px]">
              <Count label="Ready" n={t.ready} cls="bg-ok-soft text-ok" />
              <Count label="Warnings" n={t.warnings} cls="bg-warn-soft text-warn" />
              <Count label="Rejected" n={t.rejected} cls="bg-bad-soft text-bad" />
            </div>
            <div className="mt-3 h-1.5 rounded-full bg-sunken overflow-hidden flex max-w-[520px]" aria-hidden>
              <span className="bg-ok" style={{ width: `${(t.ready / total) * 100}%` }} />
              <span className="bg-warn" style={{ width: `${(t.warnings / total) * 100}%` }} />
              <span className="bg-bad" style={{ width: `${(t.rejected / total) * 100}%` }} />
            </div>

            {t.issues.length > 0 && (
              <ul className="mt-4 space-y-1.5">
                {t.issues.map((i) => (
                  <li key={i.text} className="flex items-center gap-2 text-[13px]">
                    <span className={`pill ${i.level === "rejected" ? "bg-bad-soft text-bad" : "bg-warn-soft text-warn"}`}>{i.count.toLocaleString()}</span>
                    {i.text}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="px-5 pt-4 pb-2 flex items-baseline justify-between">
            <h3 className="text-[13px] font-medium">Preview</h3>
            <span className="text-[12px] text-muted">First {t.preview.length} of {t.ready.toLocaleString()} rows</span>
          </div>
          <div className="flex-1 overflow-x-auto px-5 pb-5">
            <table className="text-[12px] border border-line rounded-lg border-separate border-spacing-0 overflow-hidden">
              <thead>
                <tr>{t.columns.map((c) => <th key={c} className="th font-mono text-[11px]">{c}</th>)}</tr>
              </thead>
              <tbody>
                {t.preview.map((row, i) => (
                  <tr key={i} className="hover:bg-[#F5F8FF]">
                    {row.map((v, j) => (
                      <td key={j} className={`td whitespace-nowrap ${v === null ? "bg-warn-soft/40" : ""}`}>
                        {v === null ? <span className="text-faint italic">empty</span> : v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end gap-2 px-5 py-4 border-t border-line bg-[#F5F8FF]">
            <button className="btn-secondary" onClick={() => router.push("/workspace")}>Cancel</button>
            <button className="btn-primary" onClick={() => setOpen(true)}>Get data</button>
          </div>
        </section>
      </div>

      <GetData open={open} onClose={() => setOpen(false)} onDownload={(m) => { setToast(m); setTimeout(() => setToast(null), 2200); }} />
      <Toast message={toast} />
    </Shell>
  );
}

function Kpi({ label, value, cls }: { label: string; value: number; cls: string }) {
  return (
    <div className="text-right">
      <div className={`text-[18px] font-semibold tabular-nums leading-tight ${cls}`}>{value.toLocaleString()}</div>
      <div className="text-[12px] text-muted">{label}</div>
    </div>
  );
}

function Count({ label, n, cls }: { label: string; n: number; cls: string }) {
  return (
    <div className={`rounded-lg px-3 py-2 ${cls}`}>
      <div className="text-[17px] font-semibold tabular-nums leading-tight">{n.toLocaleString()}</div>
      <div className="text-[12px] opacity-80">{label}</div>
    </div>
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
  const sql = setup.output === "SQL inserts";
  const api = setup.output === "API push";
  const files = TARGET.map((t) => ({ t, name: sql ? t.file.replace(".csv", ".sql") : t.file }));
  const rejected = TARGET.reduce((n, t) => n + t.rejected, 0);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Get data"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          {api ? (
            <button className="btn-primary" onClick={() => { onDownload(`Sent to ${setup.targetSystem}`); onClose(); }}>Push to {setup.targetSystem}</button>
          ) : (
            <button className="btn-primary" onClick={() => { files.forEach(({ t, name }) => save(name, sql ? sqlOf(t, setup.targetDatabase) : csvOf(t))); onDownload(`${files.length} files downloaded`); }}>Download all</button>
          )}
        </>
      }
    >
      <p className="text-[13px] text-muted mb-4">
        Version 3 · {setup.sourceSystem} → {setup.targetSystem} · {api ? "API push" : sql ? `${setup.targetDatabase} inserts` : "CSV files"}
      </p>
      {api ? (
        <p className="text-[13px]">Records will be sent to {setup.targetSystem} in batches of 500. Rejected rows stay here for you to fix.</p>
      ) : (
        <ul className="divide-y divide-line border border-line rounded-lg">
          {files.map(({ t, name }) => (
            <li key={name} className="flex items-center gap-3 px-3 py-2.5">
              <span className="grid place-items-center w-8 h-8 rounded-md bg-sunken text-[10px] font-semibold text-muted uppercase">{sql ? "sql" : "csv"}</span>
              <div className="flex-1 min-w-0">
                <p className="font-mono text-[12px] truncate">{name}</p>
                <p className="text-[11px] text-muted">{(t.ready + t.warnings).toLocaleString()} rows</p>
              </div>
              <button className="btn-ghost h-8 px-3 text-[12px]" onClick={() => { save(name, sql ? sqlOf(t, setup.targetDatabase) : csvOf(t)); onDownload(`${name} downloaded`); }}>Download</button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2 mt-4">
        <button className="btn-secondary h-8 text-[12px]" onClick={() => { save("data_dictionary.csv", "file,column\n" + TARGET.flatMap((t) => t.columns.map((c) => `${t.file},${c}`)).join("\n")); onDownload("Data dictionary downloaded"); }}>Data dictionary</button>
        <button className="btn-secondary h-8 text-[12px]" onClick={() => { save("rejected_rows.csv", "file,reason,count\n" + TARGET.flatMap((t) => t.issues.filter((i) => i.level === "rejected").map((i) => `${t.file},"${i.text}",${i.count}`)).join("\n")); onDownload("Rejected rows downloaded"); }}>
          Rejected rows ({rejected.toLocaleString()})
        </button>
      </div>
    </Modal>
  );
}
