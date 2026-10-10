import { Link } from "react-router-dom";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";

export function NotFoundPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-5 py-12 text-ink">
      <section className="w-full max-w-xl border border-line bg-white p-7 sm:p-10">
        <div className="flex items-center justify-between gap-4"><Brand /><ThemeToggle /></div>
        <p className="mt-12 text-xs font-bold uppercase tracking-[.16em] text-coral">Error 404</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-[-.045em]">This page is outside the review queue.</h1>
        <p className="mt-4 text-sm leading-6 text-muted">The address may be incorrect, or the page may have moved. Return to the authenticated TalentGuard workspace.</p>
        <Link to="/" className="mt-7 inline-flex h-11 items-center bg-brand px-5 text-sm font-semibold text-white hover:bg-brand-light">Return to TalentGuard</Link>
      </section>
    </main>
  );
}
