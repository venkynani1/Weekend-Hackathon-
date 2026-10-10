import { Database, Settings2 } from "lucide-react";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";

export function ConfigurationPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas p-6">
      <section className="w-full max-w-xl border border-line bg-white p-8 sm:p-10">
        <div className="flex items-center justify-between gap-4"><Brand /><ThemeToggle /></div>
        <div className="mt-10 grid size-12 place-items-center border border-forest/15 bg-mint text-forest"><Settings2 size={21} /></div>
        <h1 className="mt-6 text-3xl font-semibold tracking-[-.05em]">Connect the frontend to Supabase.</h1>
        <p className="mt-3 text-sm leading-6 text-muted">Set these Vercel or local Vite environment variables, then rebuild the app.</p>
        <div className="mt-6 space-y-2 border-y border-brand bg-brand p-5 font-mono text-xs text-mint"><p>VITE_SUPABASE_URL</p><p>VITE_SUPABASE_PUBLISHABLE_KEY</p><p>VITE_API_BASE_URL</p></div>
        <p className="mt-5 flex gap-2 text-[11px] leading-5 text-muted"><Database size={15} className="mt-0.5 shrink-0 text-coral" />Use only a publishable key here. Secret and service-role keys belong only in trusted backend jobs.</p>
      </section>
    </main>
  );
}
