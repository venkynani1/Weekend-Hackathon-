import { motion } from "motion/react";
import { ErrorState, PageHeader, SkeletonPage } from "../components/ui";
import { useDashboard } from "../hooks/useDashboard";
import { percent } from "../lib/format";

export function GovernancePage() {
  const query = useDashboard();
  if (query.isLoading) return <SkeletonPage />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? "No data was returned."} retry={() => query.refetch()} />;

  const { metrics } = query.data;
  const calibration = metrics.calibration_report;
  const genderGroups = metrics.fairness_report?.attributes?.Gender ?? [];
  const safeguards = [
    ["01", "Train-only fitting", "Imputation, scaling, and one-hot encoding live inside the pipeline and fit independently within each training fold."],
    ["02", "Leakage controls", `Identifier, target, constants, and sensitive fields are excluded. ${metrics.methodology.excluded_columns.length} source columns are blocked from training.`],
    ["03", "Human decision", "Scores prioritize review. Explanations are predictive associations and never evidence for automatic employment action."],
  ];

  return (
    <>
      <PageHeader eyebrow="Model evidence" title="Evidence before confidence." description="Honest baselines, out-of-fold estimates, holdout performance, calibration, and fairness evidence for the current approved model." />

      <section className="border-y border-line bg-white xl:grid xl:grid-cols-[1.25fr_.75fr]">
        <article className="p-5 sm:p-7 xl:border-r xl:border-line">
          <div className="flex flex-col justify-between gap-3 border-b border-line pb-5 sm:flex-row sm:items-end">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Candidate comparison</p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">Five-fold out-of-fold results</h2>
            </div>
            <p className="text-[10px] uppercase tracking-[.12em] text-muted">Ranked by average precision</p>
          </div>

          <div className="divide-y divide-line">
            {metrics.candidate_scores.map((candidate, index) => (
              <div key={candidate.name} className="grid gap-3 py-5 sm:grid-cols-[1fr_110px_110px] sm:items-center">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-ink">{candidate.name}</span>
                    {index === 0 && <span className="border border-coral/35 bg-coral-soft px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-coral-deep">Selected</span>}
                  </div>
                  <div className="mt-3 h-1.5 bg-slate-100">
                    <motion.div initial={{ width: 0 }} animate={{ width: `${candidate.average_precision * 100}%` }} transition={{ delay: .12 + index * .08, duration: .7 }} className={`h-full ${index === 0 ? "bg-coral" : "bg-slate-400"}`} />
                  </div>
                </div>
                <div className="sm:text-right"><p className="text-[9px] uppercase tracking-wider text-muted">Average precision</p><strong className="mt-1 block text-sm">{candidate.average_precision.toFixed(3)}</strong></div>
                <div className="sm:text-right"><p className="text-[9px] uppercase tracking-wider text-muted">Precision at 50</p><strong className="mt-1 block text-sm">{percent(candidate.precision_at_50)}</strong></div>
              </div>
            ))}
          </div>
        </article>

        <article className="bg-brand p-6 text-white sm:p-8">
          <p className="text-[10px] font-bold uppercase tracking-[.18em] text-mint">Why not accuracy?</p>
          <p className="mt-6 text-6xl font-semibold tracking-[-.065em]">{percent(metrics.dataset.all_no_accuracy, 1)}</p>
          <p className="mt-4 max-w-md text-sm leading-6 text-white/65">An all-"No" model reaches this accuracy while identifying zero exits. Ranking quality and capacity precision are the meaningful tests.</p>
          <dl className="mt-8 divide-y divide-white/15 border-y border-white/15 text-xs">
            <div className="flex items-center justify-between py-4"><dt className="text-white/55">Selected ROC-AUC</dt><dd className="font-semibold">{metrics.selected_model_score.roc_auc.toFixed(3)}</dd></div>
            <div className="flex items-center justify-between py-4"><dt className="text-white/55">Leakage audit trigger</dt><dd className="font-semibold">Above 0.95</dd></div>
          </dl>
        </article>
      </section>

      <section className="mt-10 border-t border-line">
        <div className="grid gap-4 border-b border-line py-5 lg:grid-cols-[.42fr_1fr] lg:items-end">
          <div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Review controls</p><h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">What makes the evidence usable</h2></div>
          <p className="max-w-2xl text-xs leading-5 text-muted">The control framework is part of the model evidence, not a separate marketing layer.</p>
        </div>
        <div className="divide-y divide-line">
          {safeguards.map(([number, title, copy]) => (
            <article key={title} className="grid gap-3 py-5 sm:grid-cols-[64px_190px_1fr] sm:items-start">
              <span className="font-mono text-xs text-coral">{number}</span>
              <h3 className="text-sm font-semibold">{title}</h3>
              <p className="max-w-3xl text-xs leading-5 text-muted">{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-10 border-y border-line bg-white xl:grid xl:grid-cols-2">
        <article className="p-5 sm:p-7 xl:border-r xl:border-line">
          <p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Holdout check</p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">Unseen records keep the claim honest</h2>
          <dl className="mt-6 grid grid-cols-2 border-l border-t border-line sm:grid-cols-4">
            {[["Records", metrics.holdout.test_records], ["ROC-AUC", metrics.holdout.roc_auc.toFixed(3)], ["Precision", percent(metrics.holdout.precision_at_capacity)], ["Lift", `${metrics.holdout.lift_at_capacity.toFixed(2)}×`]].map(([label, value]) => (
              <div key={label} className="border-b border-r border-line p-4"><dt className="text-[9px] uppercase tracking-wider text-muted">{label}</dt><dd className="mt-2 text-lg font-semibold text-forest">{value}</dd></div>
            ))}
          </dl>
        </article>

        <article className="bg-mint/45 p-5 sm:p-7">
          <p className="text-[10px] font-bold uppercase tracking-[.18em] text-forest/60">Calibration report</p>
          <div className="mt-5 grid gap-6 sm:grid-cols-[1fr_auto] sm:items-end">
            <div><h2 className="text-xl font-semibold tracking-[-.035em] text-forest">Out-of-fold reliability</h2><p className="mt-2 max-w-lg text-xs leading-5 text-forest/70">Brier score measures probability error; lower is better. Scores remain prioritization signals, not guaranteed forecasts.</p></div>
            <div className="border-l border-forest/20 pl-5"><p className="text-[9px] uppercase tracking-wider text-forest/55">Brier score</p><p className="mt-1 text-4xl font-semibold tracking-[-.05em] text-forest">{calibration?.brier_score?.toFixed(3) ?? "N/A"}</p></div>
          </div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 border-t border-forest/15 pt-4 text-[10px] font-bold uppercase tracking-wider text-forest"><span>{calibration?.bins?.length ?? 0} reliability bins</span><span className="text-amber-800">Not recalibrated</span></div>
        </article>
      </section>

      <section className="mt-10 border-t border-line">
        <div className="grid gap-3 border-b border-line py-5 lg:grid-cols-[.42fr_1fr] lg:items-end">
          <div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Fairness audit</p><h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">Group performance stays visible</h2></div>
          <p className="max-w-2xl text-xs leading-5 text-muted">Sensitive fields are excluded from training, but proxy effects can remain. Selection rate and observed true-positive coverage are reviewed by group.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="border-b border-line text-[9px] uppercase tracking-[.14em] text-muted"><tr><th className="py-3 pr-4 font-semibold">Group</th><th className="px-4 py-3 font-semibold">Selection rate</th><th className="px-4 py-3 font-semibold">Observed TPR</th><th className="py-3 pl-4 text-right font-semibold">Review status</th></tr></thead>
            <tbody className="divide-y divide-line">{genderGroups.map((group) => <tr key={group.group}><th className="py-4 pr-4 font-semibold text-ink">{group.group}</th><td className="px-4 py-4 text-muted">{percent(group.selection_rate, 1)}</td><td className="px-4 py-4 font-semibold text-forest">{group.true_positive_rate == null ? "Not available" : percent(group.true_positive_rate, 1)}</td><td className="py-4 pl-4 text-right text-muted">Human review</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </>
  );
}
