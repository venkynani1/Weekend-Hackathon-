import { motion } from "motion/react";
import { ArrowRight, CheckCircle2, LockKeyhole, ShieldCheck } from "lucide-react";
import { FormEvent, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";

export function LoginPage() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [website, setWebsite] = useState("");
  const startedAt = useRef(Date.now());
  const lastAttemptAt = useRef(0);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (website) {
        setMessage("Request received.");
        return;
      }
      if (Date.now() - startedAt.current < 700) throw new Error("Please review the form and try again.");
      if (Date.now() - lastAttemptAt.current < 1200) throw new Error("Please wait a moment before trying again.");
      const normalizedEmail = email.trim().toLowerCase();
      if (normalizedEmail.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) throw new Error("Enter a valid work email address.");
      if (password.length < 8 || password.length > 128) throw new Error("Use a password between 8 and 128 characters.");
      lastAttemptAt.current = Date.now();
      if (mode === "signin") await signIn(normalizedEmail, password);
      else setMessage(await signUp(normalizedEmail, password));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell relative grid min-h-[100dvh] overflow-hidden bg-canvas lg:grid-cols-[1.08fr_.92fr]">
      <section className="relative hidden min-h-[100dvh] flex-col justify-between bg-brand p-12 text-white lg:flex xl:p-16">
        <Brand inverse />
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .65 }} className="max-w-xl">
          <p className="text-[11px] font-bold uppercase tracking-[.2em] text-mint">Retention intelligence</p>
          <h1 className="mt-5 max-w-2xl text-5xl font-semibold leading-[1.01] tracking-[-.07em] xl:text-[4.5rem]">Focus attention where human action can matter.</h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-white/62">A capacity-ranked, auditable workflow for reviewing attrition signals and tracking supportive interventions.</p>
          <div className="mt-10 grid gap-3 sm:grid-cols-3">
            {["Tenant-isolated data", "Human review required", "Persistent audit trail"].map((item) => <div key={item} className="flex items-center gap-2 border-y border-white/10 bg-white/5 px-3 py-3 text-[11px] text-white/70"><CheckCircle2 size={14} className="text-mint" />{item}</div>)}
          </div>
        </motion.div>
        <p className="max-w-lg text-[11px] leading-5 text-white/40">Risk estimates are decision-support signals. They are not causal findings and never automate employment decisions.</p>
      </section>

      <section className="relative grid min-h-[100dvh] place-items-center px-5 py-10 sm:px-10">
        <div className="absolute right-5 top-5 sm:right-8 sm:top-7"><ThemeToggle /></div>
        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .08, duration: .5 }} className="w-full max-w-[460px]">
          <div className="mb-10 lg:hidden"><Brand /></div>
          <div className="mb-7 grid size-12 place-items-center rounded-xl bg-brand text-white shadow-[0_10px_25px_rgba(18,60,48,.15)]"><LockKeyhole size={21} /></div>
          <p className="text-[10px] font-bold uppercase tracking-[.2em] text-coral">Secure workspace</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-.05em]">{mode === "signin" ? "Welcome back." : "Create your account."}</h2>
          <p className="mt-3 text-sm leading-6 text-muted">{mode === "signin" ? "Sign in with your approved HR account." : "The first registered user securely bootstraps the workspace administrator role."}</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <label className="block"><span className="mb-2 block text-[11px] font-bold text-ink">Work email</span><input required maxLength={254} type="email" inputMode="email" autoCapitalize="none" spellCheck={false} autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="h-12 w-full border border-line bg-white px-4 text-sm outline-none transition focus:border-forest focus:ring-2 focus:ring-mint" placeholder="you@company.com" /></label>
            <label className="block"><span className="mb-2 block text-[11px] font-bold text-ink">Password</span><input required minLength={8} maxLength={128} type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} className="h-12 w-full border border-line bg-white px-4 text-sm outline-none transition focus:border-forest focus:ring-2 focus:ring-mint" placeholder="At least 8 characters" /></label>
            <label className="absolute -left-[10000px] top-auto size-px overflow-hidden" aria-hidden="true"><span>Website</span><input tabIndex={-1} autoComplete="off" name="website" value={website} onChange={(event) => setWebsite(event.target.value)} /></label>
            {error && <p role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">{error}</p>}
            {message && <p className="border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs leading-5 text-emerald-800">{message}</p>}
            <button disabled={busy} className="flex h-12 w-full items-center justify-center gap-2 bg-brand text-sm font-bold text-white transition hover:bg-brand-light disabled:cursor-wait disabled:opacity-60">{busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}<ArrowRight size={16} /></button>
          </form>

          <button onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setMessage(""); }} className="mt-5 text-xs font-semibold text-coral">{mode === "signin" ? "Need an account? Register" : "Already registered? Sign in"}</button>
          <div className="mt-10 flex items-start gap-3 border-t border-line pt-5 text-[11px] leading-5 text-muted"><ShieldCheck size={16} className="mt-0.5 shrink-0 text-forest" />Supabase Auth protects the session; database row-level security enforces organization access.</div>
          <p className="mt-4 text-[10px] leading-5 text-muted">By continuing, you agree to the <Link to="/terms" className="font-semibold text-forest underline">terms</Link> and acknowledge the <Link to="/privacy" className="font-semibold text-forest underline">privacy notice</Link>.</p>
        </motion.div>
      </section>
    </main>
  );
}
