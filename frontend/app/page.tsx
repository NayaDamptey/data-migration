"use client";

// Screen 1: Sign in. Sketch: docs/sketches/1-login.jpeg
// Auth will come from Clerk/Auth0; this form is a placeholder that accepts anything.
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Check, Logo, Spinner, SystemTile } from "../components/ui";

export default function SignInPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("Enter your username and password.");
      return;
    }
    setError(null);
    setBusy(true);
    setTimeout(() => router.push("/workspace"), 600);
  }

  return (
    <main className="min-h-screen grid lg:grid-cols-[1fr_minmax(460px,40%)]">
      {/* Brand panel */}
      <section className="hidden lg:flex flex-col justify-between bg-nav text-nav-text p-12 relative overflow-hidden">
        <Logo dark height={40} />
        <div className="max-w-[540px] relative z-10">
          <h2 className="text-white text-[52px] leading-[1.05] font-bold tracking-tight">Move every record. Miss nothing.</h2>
          <p className="text-[16px] text-white/80 mt-5 max-w-[440px]">From the old CRM to the new one: checked, mapped and ready to load.</p>
          <ul className="mt-8 space-y-3 text-[15px] text-white">
            {["Bulk upload CSVs, folders or zips", "AI-suggested mappings that a person approves", "Multi-table joins, value maps and clean-up rules", "Validated CSV, SQL or API output"].map((t) => (
              <li key={t} className="flex items-center gap-3"><span className="grid place-items-center w-6 h-6 rounded-full bg-white text-nav"><Check /></span>{t}</li>
            ))}
          </ul>
        </div>
        <div className="flex items-center gap-2 text-[12px] relative z-10">
          {["Tracker", "JobAdder", "Bullhorn", "Vincere", "Seven20"].map((s) => <span key={s} className="grid place-items-center w-9 h-9 bg-white"><SystemTile name={s} size={24} /></span>)}
          <span className="ml-1">and more</span>
        </div>
        {/* Decorative flow lines */}
        <svg className="absolute -right-24 top-1/4 opacity-[0.07]" width="520" height="520" viewBox="0 0 520 520" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => <path key={i} d={`M0 ${100 + i * 70} C 180 ${100 + i * 70}, 260 ${260}, 520 ${260}`} stroke="white" strokeWidth="2" fill="none" />)}
        </svg>
      </section>

      <div className="grid place-items-center px-4 py-10 bg-surface">
      <div className="w-full max-w-[380px]">
        <div className="flex mb-8 lg:hidden"><Logo height={32} /></div>
        <form onSubmit={submit} noValidate>
          <h1 className="text-[32px] leading-tight font-bold tracking-tight">Sign in</h1>
          <p className="text-muted mt-1.5 mb-8 text-[15px]">Welcome back. Pick up where your migration left off.</p>

          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="label">Username</label>
              <input id="username" className="field h-12" autoComplete="username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="you@agency.co.uk" />
            </div>
            <div>
              <label htmlFor="password" className="label">Password</label>
              <input id="password" type="password" className="field h-12" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-[13px] text-muted cursor-pointer select-none">
              <input type="checkbox" className="w-4 h-4 accent-[#0A1F44]" defaultChecked />
              Keep me signed in
            </label>
          </div>

          {error && <p role="alert" className="mt-4 text-[13px] text-bad bg-bad-soft rounded-lg px-3 py-2">{error}</p>}

          <div className="flex flex-col gap-2 mt-8">
            <button type="submit" className="btn-primary h-12 text-[16px] w-full" disabled={busy}>
              {busy ? <Spinner /> : "Sign in"}
            </button>
            <button type="button" className="btn-secondary h-12 text-[16px] w-full" onClick={() => { setUsername(""); setPassword(""); setError(null); }}>Cancel</button>
          </div>
        </form>
      </div>
      </div>
    </main>
  );
}
