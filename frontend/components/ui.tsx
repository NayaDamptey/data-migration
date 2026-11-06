"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { isDemo } from "../lib/demo";
import { useStore } from "../lib/store";
import { ENTITIES, type FieldStatus } from "../lib/mock";

// Neutral placeholder mark: two stacked arrows (source -> target). Shown white on dark backgrounds.
export function LogoMark({ size = 26, dark = false }: { size?: number; dark?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden className={`shrink-0 ${dark ? "text-white" : "text-ink"}`} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8h14M13 4l4 4-4 4" />
      <path d="M21 16H7M11 12l-4 4 4 4" opacity={0.55} />
    </svg>
  );
}

export function Logo({ dark = false, height = 26 }: { dark?: boolean; height?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark size={height} dark={dark} />
      <span className={`font-semibold tracking-tight ${dark ? "text-white" : "text-ink"}`} style={{ fontSize: Math.round(height * 0.62) }}>Migryr</span>
    </div>
  );
}

// Fictional systems with made-up logos (public/logos): no real vendor names or marks are used.
const SYSTEM_LOGOS: Record<string, string> = {
  Larkspur: "/logos/larkspur.svg",
  Quillhire: "/logos/quillhire.svg",
  Beaconfield: "/logos/beaconfield.svg",
  Ninefold: "/logos/ninefold.svg",
  Vantora: "/logos/vantora.svg",
  Cobaltdesk: "/logos/cobaltdesk.svg",
};

export function SystemTile({ name, size = 36 }: { name: string; size?: number }) {
  const logo = SYSTEM_LOGOS[name];
  if (logo) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={logo} alt="" aria-hidden width={size} height={size} className="shrink-0 object-contain" style={{ width: size, height: size }} />;
  }
  const letters = name === "Custom schema" ? "{ }" : name.replace(/[^A-Za-z0-9]/g, "").slice(0, 2);
  return (
    <span
      className="grid place-items-center border border-ink text-ink font-bold shrink-0 bg-white"
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      aria-hidden
    >
      {letters}
    </span>
  );
}

const TABS = [
  { href: "/", label: "Source upload" },
  { href: "/quality", label: "Data quality" },
  { href: "/workspace", label: "Setup" },
  { href: "/canonical", label: "Schema mapping" },
  { href: "/target", label: "Destination data" },
  { href: "/versions", label: "Version review" },
];

const icons = {
  dupes: <><rect x="2.5" y="3" width="8" height="9" fill="none" stroke="currentColor" strokeWidth="1.4" /><rect x="7.5" y="6" width="8" height="9" fill="none" stroke="currentColor" strokeWidth="1.4" /></>,
  quality: <><path d="M3 14.5h12" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /><path d="M4.5 12V8.5M8 12V5M11.5 12V7M15 3.5l-2.2 2.2-1.6-1.2" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></>,
  upload: <><path d="M9 11.5V3.5M5.8 6.7 9 3.5l3.2 3.2" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /><path d="M3 11v2.5a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V11" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></>,
  pipeline: <path d="M3 5h4v4H3zM11 11h4v4h-4zM7 7h2a2 2 0 0 1 2 2v2" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />,
  setup: <><circle cx="9" cy="9" r="2.2" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M9 2.5v2M9 13.5v2M2.5 9h2M13.5 9h2M4.4 4.4l1.4 1.4M12.2 12.2l1.4 1.4M4.4 13.6l1.4-1.4M12.2 5.8l1.4-1.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></>,
  schema: <path d="M3 4h5v3H3zM10 11h5v3h-5zM10 4h5v3h-5zM5.5 7v5.5H10M12.5 7v4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />,
  versions: <><circle cx="5" cy="4.5" r="1.8" fill="none" stroke="currentColor" strokeWidth="1.4" /><circle cx="5" cy="13.5" r="1.8" fill="none" stroke="currentColor" strokeWidth="1.4" /><circle cx="13" cy="7" r="1.8" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M5 6.3v5.4M13 8.8c0 2.2-2 3-4.5 3H6.8" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></>,
  data: <><ellipse cx="9" cy="4.5" rx="5.5" ry="2" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M3.5 4.5v9c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2v-9M3.5 9c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2" fill="none" stroke="currentColor" strokeWidth="1.4" /></>,
};
const Icon = ({ name }: { name: keyof typeof icons }) => <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>{icons[name]}</svg>;

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { setup, steps, runStep, fieldStatus, pendingChanges, runs, uploads, uploadsReady } = useStore();
  const uploadedCount = uploads.filter((u) => u.status === "uploaded").length;
  // the pipeline order: upload source first, then data quality
  const locked = (href: string) => href === "/quality" && uploadsReady && uploadedCount === 0;
  const LOCK_HINT = "Upload the source data first";
  const review = ENTITIES.reduce((n, e) => n + e.fields.filter((f) => fieldStatus(e.key, f.name) === "review").length, 0);
  const running = Object.values(steps).includes("running");
  const pending = pendingChanges.length;
  const tabs = TABS;
  const nav = [
    { href: "/", label: "Source upload", icon: "upload" as const, badge: uploadedCount || undefined },
    { href: "/quality", label: "Data quality", icon: "quality" as const },
    { href: "/workspace", label: "Setup", icon: "setup" as const },
    { href: "/canonical", label: "Schema mapping", icon: "schema" as const, badge: review || undefined },
    { href: "/target", label: "Destination data", icon: "data" as const },
    { href: "/versions", label: "Version review", icon: "versions" as const, badge: pending || undefined },
  ];

  const runAll = async () => {
    await runStep("quality");
    await runStep("canonical");
    await runStep("target");
  };

  return (
    <div className="min-h-screen lg:pl-[232px]">
      {/* Sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[232px] flex-col bg-nav text-nav-text z-40">
        <div className="h-14 flex items-center px-4 border-b border-nav-line">
          <Link href="/"><Logo dark /></Link>
        </div>
        <div className="px-3 pt-5">
          <p className="px-2 text-[12px] font-medium text-nav-text mb-2">Migration</p>
          <div className="rounded-xl bg-nav-hover px-3 py-2.5 mb-3 flex items-center gap-2.5">
            <span className="grid place-items-center w-7 h-7 bg-white shrink-0"><SystemTile name={setup.sourceSystem} size={20} /></span>
            <div className="min-w-0">
              <p className="text-[12.5px] text-white font-medium leading-snug">Harrow & Finch Recruitment</p>
              <p className="text-[11px] truncate">{setup.sourceSystem} → {setup.targetSystem}</p>
            </div>
          </div>
          <nav className="space-y-0.5" aria-label="Migration">
            {nav.map((n) => {
              const active = path === n.href;
              if (locked(n.href)) return (
                <span key={n.href} aria-disabled="true" title={LOCK_HINT}
                  className="flex items-center gap-2.5 h-10 px-3 rounded-full text-[14px] font-medium opacity-40 cursor-not-allowed">
                  <Icon name={n.icon} />
                  <span className="flex-1">{n.label}</span>
                  <LockGlyph />
                </span>
              );
              return (
                <Link key={n.href} href={n.href} aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-2.5 h-10 px-3 rounded-full text-[14px] font-medium transition-colors ${active ? "bg-white text-nav" : "hover:bg-nav-hover hover:text-white"}`}>
                  <Icon name={n.icon} />
                  <span className="flex-1">{n.label}</span>
                  {n.badge && <span className={`text-[11px] font-semibold rounded-full px-2 ${active ? "bg-nav text-white" : "bg-white/15 text-white"}`}>{n.badge}</span>}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="mt-auto border-t border-nav-line p-3 flex items-center gap-2.5">
          <span className="grid place-items-center w-8 h-8 rounded-full bg-white text-nav text-[12px] font-bold">ND</span>
          <div className="min-w-0 flex-1">
            <p className="text-[12.5px] text-white font-medium truncate">Naya Damptey</p>
            <p className="text-[11px] truncate">Harrow & Finch Recruitment</p>
          </div>
          <Link href="/signin" className="text-[11px] hover:text-white" title="Sign out">Sign out</Link>
        </div>
      </aside>

      {/* Top bar */}
      <header className="sticky top-0 z-30 h-14 bg-nav text-white flex items-center gap-3 px-4 sm:px-6">
        <Link href="/" className="lg:hidden"><LogoMark dark /></Link>
        <span className="text-[14px] text-white font-medium truncate">{TABS.find((t) => t.href === path)?.label}</span>
        {isDemo && <span className="pill bg-white/15 text-white" title="A demo with generated sample data: nothing is sent anywhere">Demo · sample data</span>}
        <div className="ml-auto flex items-center gap-3">
          {pending > 0 && path !== "/versions" && (
            <Link href="/versions" className="hidden md:inline-flex pill bg-white text-nav hover:bg-sunken">{pending} unsaved change{pending > 1 ? "s" : ""} · Review</Link>
          )}
          <span className="lg:hidden grid place-items-center w-8 h-8 rounded-full bg-white text-nav text-[12px] font-bold">ND</span>
        </div>
      </header>

      {/* Connector header */}
      <div className="bg-surface border-b border-line">
        <div className="max-w-[1360px] mx-auto px-4 sm:px-8 pt-8">
          <div className="flex flex-wrap items-center gap-4 justify-between">
            <div className="flex items-center gap-4 min-w-0">
              <div className="flex items-center gap-1.5">
                <SystemTile name={setup.sourceSystem} />
                <FlowArrow />
                <span className="grid place-items-center w-9 h-9 rounded-lg bg-sunken" title="Canonical model"><LogoMark size={20} /></span>
                <FlowArrow />
                <SystemTile name={setup.targetSystem} />
              </div>
              <div className="min-w-0">
                <h1 className="text-[28px] leading-tight font-bold tracking-tight truncate">{setup.sourceSystem} to {setup.targetSystem}</h1>
                <p className="text-[13px] text-muted flex items-center gap-1.5 mt-0.5">
                  {running && <><span className="w-2 h-2 rounded-full bg-accent animate-pulse" />Running…<span className="text-faint">·</span></>}
                  Version v{runs[0]?.version} · {runs[0]?.when}{pending > 0 && <> <span className="text-faint">·</span> {pending} unsaved</>}
                  <span className="text-faint hidden sm:inline">·</span><span className="hidden sm:inline">{setup.sourceFormat} → {setup.output === "SQL inserts" ? `${setup.targetDatabase} inserts` : setup.output}</span>
                </p>
              </div>
            </div>
            <button className="btn-primary" onClick={runAll} disabled={running || uploadedCount === 0} title={uploadedCount === 0 ? LOCK_HINT : undefined}>
              {running ? <><Spinner /> Running</> : <><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M3 2v8l7-4z" fill="currentColor" /></svg> Run migration</>}
            </button>
          </div>
          <nav className="flex gap-7 mt-6 -mb-px overflow-x-auto" aria-label="Sections">
            {tabs.map((t) => {
              const active = path === t.href;
              if (locked(t.href)) return (
                <span key={t.href} aria-disabled="true" title={LOCK_HINT}
                  className="pb-3 text-[15px] border-b-[3px] border-transparent whitespace-nowrap text-faint cursor-not-allowed inline-flex items-center gap-1.5">
                  {t.label} <LockGlyph />
                </span>
              );
              return (
                <Link key={t.href} href={t.href} aria-current={active ? "page" : undefined}
                  className={`pb-3 text-[15px] border-b-[3px] whitespace-nowrap transition-colors ${active ? "border-ink text-ink font-medium" : "border-transparent text-muted hover:text-ink"}`}>
                  {t.label}
                  {t.href === "/canonical" && review > 0 && <span className="ml-1.5 pill bg-warn-soft text-warn py-0">{review}</span>}
                  {t.href === "/versions" && pending > 0 && <span className="ml-1.5 pill bg-accent text-white py-0">{pending}</span>}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <main className="max-w-[1360px] mx-auto px-4 sm:px-8 py-8">{children}</main>
    </div>
  );
}

function LockGlyph() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden className="shrink-0">
      <rect x="2.5" y="5.5" width="7" height="5" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M4 5.5V4a2 2 0 0 1 4 0v1.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function FlowArrow() {
  return <svg width="16" height="10" viewBox="0 0 16 10" className="text-faint" aria-hidden><path d="M1 5h13M10 1l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-4">
      <div>
        <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
        {sub && <p className="text-muted mt-0.5 text-[13px]">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Select({ label, value, options, onChange, hint }: { label: string; value: string; options: string[]; onChange: (v: string) => void; hint?: string }) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <div className="relative">
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="field appearance-none pr-8 cursor-pointer">
          {options.map((o) => <option key={o}>{o}</option>)}
        </select>
        <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-faint" width="12" height="12" viewBox="0 0 12 12" aria-hidden>
          <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
      {hint && <p className="text-[12px] text-faint mt-1">{hint}</p>}
    </div>
  );
}

const STATUS_STYLE: Record<FieldStatus, { cls: string; label: string }> = {
  mapped: { cls: "bg-ok-soft text-ok", label: "Mapped" },
  review: { cls: "bg-warn-soft text-warn", label: "Needs review" },
  unmapped: { cls: "bg-sunken text-muted", label: "Unmapped" },
};

export function StatusPill({ status }: { status: FieldStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={`pill ${s.cls}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {s.label}
    </span>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return <span className={`inline-block w-3.5 h-3.5 rounded-full border-2 border-current border-r-transparent animate-spin ${className}`} />;
}

export function Check({ className = "" }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 14 14" aria-hidden>
      <path d="M3 7.5 5.8 10 11 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Modal({ open, onClose, title, children, footer, wide = false }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label={title} className={`relative w-full ${wide ? "max-w-[1180px]" : "max-w-[560px]"} card shadow-pop`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <h2 className="font-semibold text-[16px]">{title}</h2>
          <button onClick={onClose} className="btn-ghost h-8 w-8 px-0" aria-label="Close">✕</button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 px-5 py-4 border-t border-line bg-[#F5F8FF] rounded-b-xl">{footer}</div>}
      </div>
    </div>
  );
}

export function Toast({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 card shadow-pop px-4 py-2.5 text-[13px] flex items-center gap-2">
      <Check className="text-ok" /> {message}
    </div>
  );
}
