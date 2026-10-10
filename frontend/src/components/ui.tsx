import type { ReactNode } from "react";
import { motion } from "motion/react";

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="eyebrow mb-2 text-[10px] font-bold uppercase text-coral">{children}</p>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-9 flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h1 className="max-w-4xl text-3xl font-semibold leading-[1.04] tracking-[-0.055em] text-ink sm:text-[2.7rem]">{title}</h1>
        <p className="mt-4 max-w-2xl text-[13px] leading-6 text-muted">{description}</p>
      </div>
      {action}
    </div>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  accent = false,
  delay = 0,
}: {
  label: string;
  value: string;
  detail: string;
  accent?: boolean;
  delay?: number;
}) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: [0.22, 1, 0.36, 1] }}
      className={`surface-panel border-0 p-5 ${
        accent ? "bg-brand text-white" : "bg-surface text-ink"
      }`}
    >
      <p className={`text-xs font-semibold ${accent ? "text-white/75" : "text-muted"}`}>{label}</p>
      <p className="mt-5 text-3xl font-semibold tracking-[-0.05em]">{value}</p>
      <p className={`mt-2 text-xs ${accent ? "text-white/75" : "text-muted"}`}>{detail}</p>
    </motion.article>
  );
}

export function RiskBadge({ band }: { band: string }) {
  const styles =
    band === "Priority"
      ? "bg-coral-soft text-coral-deep"
      : band === "High"
        ? "bg-amber-100 text-amber-800"
        : "bg-mint text-forest";
  return <span className={`status-chip inline-flex border border-current/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${styles}`}>{band}</span>;
}

export function SkeletonPage() {
  return (
    <div className="animate-pulse">
      <div className="h-2.5 w-28 rounded-full bg-slate-200" />
      <div className="mt-5 h-10 w-2/3 rounded-lg bg-slate-200" />
      <div className="mt-4 h-4 w-1/2 rounded-lg bg-slate-200" />
      <div className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => <div key={item} className="surface-panel h-40" />)}
      </div>
      <div className="surface-panel mt-6 h-96" />
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <div className="surface-panel max-w-md border-red-200 p-8 text-center">
        <p className="text-lg font-semibold text-ink">The dashboard API is unavailable</p>
        <p className="mt-2 text-sm leading-6 text-muted">{message}</p>
        <button onClick={retry} className="mt-5 bg-brand px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-light">Try again</button>
      </div>
    </div>
  );
}
