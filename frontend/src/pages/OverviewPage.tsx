import { motion } from "motion/react";
import { ArrowRight, Target, TrendingUp, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EmployeeDrawer } from "../components/EmployeeDrawer";
import { ErrorState, MetricCard, PageHeader, RiskBadge, SkeletonPage } from "../components/ui";
import { useDashboard } from "../hooks/useDashboard";
import { compact, number, percent } from "../lib/format";
import type { EmployeeRisk } from "../types";

const capacities = [10, 25, 50] as const;

export function OverviewPage() {
  const query = useDashboard();
  const [capacity, setCapacity] = useState<(typeof capacities)[number]>(50);
  const [selected, setSelected] = useState<EmployeeRisk | null>(null);

  const scenario = useMemo(() => {
    const records = query.data?.watchlist.slice(0, capacity) ?? [];
    const exits = records.filter((item) => item.HistoricalOutcome === "Yes").length;
    const exposure = records.reduce((total, item) => total + item.MonthlyIncome * 6, 0);
    return { records, exits, exposure, precision: records.length ? exits / records.length : 0 };
  }, [query.data, capacity]);

  if (query.isLoading) return <SkeletonPage />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? "No data was returned."} retry={() => query.refetch()} />;

  const { metrics, top_ten } = query.data;
  const eda = metrics.historical_eda;

  return (
    <>
      <PageHeader
        eyebrow="Retention command center"
        title="Turn attrition signals into focused, human decisions."
        description="A capacity-aware view of historical employee risk, transparent evidence, and the next best action for HR teams."
        action={
          <Link to="/live-review" className="inline-flex h-11 items-center justify-center bg-brand px-5 text-xs font-bold text-white hover:bg-brand-light">Run live review <ArrowRight size={15} /></Link>
        }
      />

      <section className="grid gap-px border-y border-line bg-line sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Employees reviewed" value={number(metrics.dataset.records)} detail={`${metrics.dataset.columns} columns · no missing cells`} />
        <MetricCard label="Historical attrition" value={percent(metrics.dataset.attrition_rate, 1)} detail={`${metrics.dataset.attrition_count} observed exits`} delay={0.05} />
        <MetricCard label="Precision in Top 50" value={percent(metrics.selected_model_score.precision_at_50)} detail={`${metrics.selected_model_score.lift_at_50.toFixed(2)}× lift over base rate`} accent delay={0.1} />
        <MetricCard label="ROC-AUC" value={metrics.selected_model_score.roc_auc.toFixed(3)} detail={metrics.selected_model} delay={0.15} />
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
        <motion.article initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .16, duration: .5 }} className="relative overflow-hidden border border-brand bg-brand p-6 text-white sm:p-8">
          <div className="relative">
            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[.18em] text-mint">Capacity scenario</p>
                <h2 className="mt-3 max-w-xl text-2xl font-semibold tracking-[-.04em] sm:text-3xl">What happens when HR can review only {capacity} employees?</h2>
              </div>
              <div className="flex border border-white/15 bg-white/5 p-1">
                {capacities.map((item) => (
                  <button key={item} onClick={() => setCapacity(item)} className={`relative px-3 py-2 text-xs font-bold transition ${capacity === item ? "text-forest" : "text-white/65 hover:text-white"}`}>
                    {capacity === item && <motion.span layoutId="capacity-active" className="absolute inset-0 bg-white" transition={{ type: "spring", stiffness: 420, damping: 32 }} />}
                    <span className="relative">Top {item}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-10 grid grid-cols-2 gap-px border border-white/15 bg-white/15 lg:grid-cols-4">
              {[
                ["Review capacity", String(scenario.records.length), "employees"],
                ["Historical exits", String(scenario.exits), "inside selection"],
                ["Precision", percent(scenario.precision), "historical check"],
                ["Cost exposure", compact(scenario.exposure), "6× income proxy"],
              ].map(([label, value, detail]) => (
                <div key={label} className="bg-brand/90 p-4 sm:p-5"><p className="text-[10px] font-semibold text-white/50">{label}</p><motion.p key={value} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="mt-2 text-2xl font-semibold tracking-[-.04em]">{value}</motion.p><p className="mt-1 text-[10px] text-white/45">{detail}</p></div>
              ))}
            </div>
          </div>
        </motion.article>

        <article className="border border-line bg-white p-6 sm:p-7">
          <div className="flex items-start justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Operating point</p><h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">High signal, bounded queue</h2></div><div className="grid size-10 place-items-center border border-forest/15 bg-mint text-forest"><Target size={18} /></div></div>
          <div className="mt-7 space-y-5">
            <div><div className="flex justify-between text-xs"><span className="text-muted">Base attrition</span><strong>{percent(metrics.dataset.attrition_rate, 1)}</strong></div><div className="mt-2 h-1.5 overflow-hidden bg-slate-100"><motion.div initial={{ width: 0 }} animate={{ width: `${metrics.dataset.attrition_rate * 100}%` }} transition={{ delay: .35, duration: .7 }} className="h-full bg-slate-400" /></div></div>
            <div><div className="flex justify-between text-xs"><span className="text-muted">Top-50 precision</span><strong>{percent(metrics.selected_model_score.precision_at_50)}</strong></div><div className="mt-2 h-1.5 overflow-hidden bg-coral-soft"><motion.div initial={{ width: 0 }} animate={{ width: `${metrics.selected_model_score.precision_at_50 * 100}%` }} transition={{ delay: .45, duration: .8 }} className="h-full bg-coral" /></div></div>
          </div>
          <div className="mt-7 border-y border-line bg-[#f4f6f1] py-4"><p className="text-xs leading-5 text-muted">The ranking captures <strong className="text-ink">{percent(metrics.selected_model_score.recall_at_50, 1)}</strong> of all exits within a 50-person intervention limit.</p></div>
        </article>
      </section>

      <section className="mt-10">
        <div className="mb-5 flex items-end justify-between gap-5"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Priority queue</p><h2 className="mt-2 text-2xl font-semibold tracking-[-.04em]">The first five reviews</h2></div><Link to="/watchlist" className="flex items-center gap-2 text-xs font-bold text-forest">View all 50 <ArrowRight size={14} /></Link></div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {top_ten.slice(0, 5).map((employee, index) => (
            <motion.button key={employee.EmployeeNumber} onClick={() => setSelected(employee)} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: index * .04 }} className="group min-h-56 border border-line bg-white p-5 text-left transition hover:border-forest/40">
              <div className="flex items-start justify-between"><span className="text-lg font-semibold text-coral">{String(employee.Rank).padStart(2, "0")}</span><RiskBadge band={employee.RiskBand} /></div>
              <p className="mt-6 text-sm font-semibold">Employee {employee.EmployeeNumber}</p><p className="mt-1 min-h-9 text-[11px] leading-4 text-muted">{employee.JobRole} · {employee.Department}</p>
              <p className="mt-4 line-clamp-2 text-xs leading-5 text-ink/75">{employee.RiskReason1}</p>
              <div className="mt-4 flex items-center justify-between border-t border-line pt-3"><span className="text-[10px] font-bold uppercase tracking-wide text-muted">{employee.PrimaryAction}</span><ArrowRight size={14} className="text-coral transition group-hover:translate-x-1" /></div>
            </motion.button>
          ))}
        </div>
      </section>

      <section className="mt-10 grid gap-5 xl:grid-cols-[.9fr_1.1fr]">
        <article className="border-y border-line bg-white p-6 sm:p-7">
          <div className="flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Historical EDA</p><h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">Signals worth investigating</h2></div><TrendingUp size={20} className="text-coral" /></div>
          <div className="mt-6 grid grid-cols-2 border-l border-t border-line">
            {[
              [percent(eda.overtime_yes_rate, 1), "With overtime", `vs ${percent(eda.overtime_no_rate, 1)} without`],
              [percent(eda.sales_representative_rate, 1), "Sales representative", "highest role rate"],
              [percent(eda.frequent_travel_rate, 1), "Frequent travel", `vs ${percent(eda.rare_travel_rate, 1)} rare`],
              [percent(eda.low_satisfaction_rate, 1), "Low satisfaction", `vs ${percent(eda.high_satisfaction_rate, 1)} high`],
            ].map(([value, label, detail]) => <div key={label} className="border-b border-r border-line bg-[#f4f6f1] p-4"><p className="text-xl font-semibold tracking-[-.04em] text-forest">{value}</p><p className="mt-2 text-xs font-semibold">{label}</p><p className="mt-1 text-[10px] text-muted">{detail}</p></div>)}
          </div>
          <p className="mt-4 text-[10px] leading-5 text-muted">Associations are descriptive, not causal. Interventions should be tested and measured.</p>
        </article>

        <article className="border-y border-line bg-white p-6 sm:p-7">
          <div className="flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Explanation mix</p><h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">Common Top-50 drivers</h2></div><Users size={20} className="text-forest" /></div>
          <div className="mt-6 space-y-4">
            {metrics.driver_summary.slice(0, 6).map((driver, index) => {
              const max = metrics.driver_summary[0]?.count || 1;
              return <div key={driver.feature} className="grid grid-cols-[145px_1fr_30px] items-center gap-3 text-xs"><span className="truncate font-medium text-ink">{driver.label}</span><div className="h-1.5 overflow-hidden bg-slate-100"><motion.div initial={{ width: 0 }} whileInView={{ width: `${driver.count / max * 100}%` }} viewport={{ once: true }} transition={{ delay: index * .05, duration: .6 }} className="h-full bg-brand" /></div><strong className="text-right text-coral">{driver.count}</strong></div>;
            })}
          </div>
        </article>
      </section>

      <EmployeeDrawer employee={selected} close={() => setSelected(null)} />
    </>
  );
}
