import { FormEvent, useState } from "react";
import { EmployeeDrawer } from "../components/EmployeeDrawer";
import { PageHeader, RiskBadge } from "../components/ui";
import { fetchEmployee } from "../lib/api";
import { percent } from "../lib/format";
import type { EmployeeRisk } from "../types";

export function LiveReviewPage() {
  const [employeeNumber, setEmployeeNumber] = useState("1");
  const [result, setResult] = useState<EmployeeRisk | null>(null);
  const [selected, setSelected] = useState<EmployeeRisk | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = Number(employeeNumber);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 999999) {
      setError("Enter a valid positive employee number.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await fetchEmployee(parsed));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The score could not be loaded.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Live judging demo" title="Retrieve one approved score and explain the decision path." description="Enter an employee number from the benchmark dataset. TalentGuard retrieves the persisted score from the approved model run, then exposes evidence and a human review action." />
      <section className="grid gap-5 xl:grid-cols-[.72fr_1.28fr]">
        <form onSubmit={submit} className="border border-line bg-white p-5 sm:p-7" noValidate>
          <label htmlFor="employee-number" className="text-sm font-semibold text-ink">Employee number</label>
          <p className="mt-2 text-xs leading-5 text-muted">Use a source employee ID such as 1, 2, or 4.</p>
          <input id="employee-number" name="employee-number" value={employeeNumber} onChange={(event) => setEmployeeNumber(event.target.value.replace(/[^0-9]/g, "").slice(0, 6))} inputMode="numeric" autoComplete="off" className="mt-5 h-12 w-full border border-line bg-[#f8f9f6] px-4 text-base outline-none focus:border-forest" aria-describedby={error ? "live-review-error" : undefined} />
          {error && <p id="live-review-error" role="alert" className="mt-3 border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-800">{error}</p>}
          <button disabled={busy} className="mt-4 h-12 w-full bg-brand px-5 text-sm font-semibold text-white hover:bg-brand-light disabled:cursor-wait disabled:opacity-60">{busy ? "Loading approved score..." : "Run evidence review"}</button>
          <p className="mt-4 text-[11px] leading-5 text-muted">This is a live API lookup against the current scoring run. It is intentionally not described as fresh model inference.</p>
        </form>
        <article className="min-h-80 border border-line bg-[#f3f5ef] p-5 sm:p-7" aria-live="polite">
          {!result ? (
            <div className="flex min-h-64 items-center justify-center text-center"><div><p className="text-sm font-semibold text-ink">Ready for a live review</p><p className="mt-2 max-w-sm text-xs leading-5 text-muted">The result will show rank, score, three predictive reasons, and the first recommended action.</p></div></div>
          ) : (
            <div>
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-5">
                <div><p className="text-xs font-bold uppercase tracking-[.14em] text-coral">Employee {result.EmployeeNumber}</p><h2 className="mt-2 text-2xl font-semibold tracking-[-.04em]">{result.JobRole}</h2><p className="mt-1 text-xs text-muted">{result.Department}</p></div>
                <div className="text-right"><p className="text-3xl font-semibold tracking-[-.04em] text-forest">{percent(result.RiskScore)}</p><div className="mt-2"><RiskBadge band={result.RiskBand} /></div></div>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                {[result.RiskReason1, result.RiskReason2, result.RiskReason3].map((reason, index) => <div key={`${reason}-${index}`} className="border border-line bg-white p-4"><p className="text-[10px] font-bold text-coral">Reason {index + 1}</p><p className="mt-2 text-xs leading-5 text-ink/80">{reason}</p></div>)}
              </div>
              <div className="mt-4 border border-forest/20 bg-mint p-4"><p className="text-[10px] font-bold uppercase tracking-[.14em] text-forest/70">Recommended first action</p><p className="mt-2 text-sm font-semibold text-forest">{result.PrimaryAction}</p><p className="mt-2 text-xs leading-5 text-forest/75">{result.Recommendation}</p></div>
              <button type="button" onClick={() => setSelected(result)} className="mt-4 h-11 bg-coral px-5 text-xs font-semibold text-white hover:bg-coral-deep">Open intervention workflow</button>
            </div>
          )}
        </article>
      </section>
      <section className="mt-5 border border-amber-200 bg-amber-50 p-5 text-xs leading-6 text-amber-950/80"><strong className="text-amber-950">Judge-ready explanation:</strong> The employee identifier is excluded from training and used only to retrieve the record. The score is predictive, not causal. No employment action is automated.</section>
      <EmployeeDrawer employee={selected} close={() => setSelected(null)} />
    </>
  );
}
