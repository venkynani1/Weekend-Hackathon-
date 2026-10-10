import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Check, CircleDashed } from "lucide-react";
import { PageHeader } from "../components/ui";
import { fetchIngestionRuns } from "../lib/api";

const stages = [
  ["01", "Hosted source", "Read-only database connection"],
  ["02", "Render ingestion", "Incremental validation and sync"],
  ["03", "Supabase", "Immutable snapshots and scores"],
];

const contract = [
  "Fetch records after the last cursor",
  "Validate schema and allowed values",
  "Upsert identity; append snapshots",
  "Score only completed snapshots",
  "Persist run counts and failures",
  "Publish the latest approved run",
];

export function DataSyncPage() {
  const runs = useQuery({ queryKey: ["ingestion-runs"], queryFn: fetchIngestionRuns, staleTime: 30_000 });
  const latest = runs.data?.[0];
  const isCompleted = latest?.status === "completed";

  return (
    <>
      <PageHeader eyebrow="Data operations" title="A visible, auditable path from source to score." description="This screen is ready for the hosted-database connector. It deliberately shows the current packaged-output state instead of pretending a production source is connected." />

      <section className="border-y border-line bg-white xl:grid xl:grid-cols-[.72fr_1.28fr]">
        <article className={`p-6 sm:p-7 xl:border-r ${isCompleted ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
          <div className={`flex items-center gap-2 ${isCompleted ? "text-emerald-800" : "text-amber-800"}`}>{isCompleted ? <Check size={18} /> : <CircleDashed size={18} />}<span className="text-[10px] font-bold uppercase tracking-[.16em]">{latest ? `Latest run: ${latest.status}` : "Connector pending"}</span></div>
          <h2 className="mt-5 text-2xl font-semibold tracking-[-.04em] text-ink">{latest ? latest.source_name : "Hosted source not connected"}</h2>
          <p className={`mt-3 text-sm leading-6 ${isCompleted ? "text-emerald-950/65" : "text-amber-950/65"}`}>{latest ? `${latest.records_written.toLocaleString()} records written from ${latest.records_read.toLocaleString()} read. Started ${new Date(latest.started_at).toLocaleString()}.` : "Configure the read-only hosted database connector to begin incremental snapshots."}</p>
          <div className={`mt-7 border-y py-4 ${isCompleted ? "border-emerald-200" : "border-amber-200"}`}>
            <p className={`text-[10px] font-bold uppercase tracking-wider ${isCompleted ? "text-emerald-800" : "text-amber-800"}`}>Pipeline contract</p>
            <ul className="mt-3 divide-y divide-black/10 text-xs text-ink/70">{["Read-only source connection", "Schema and duplicate validation", "Immutable dated snapshots", "Scoring after completed ingestion"].map((item) => <li key={item} className="flex gap-2 py-2"><Check size={14} /> {item}</li>)}</ul>
          </div>
        </article>

        <article className="p-6 sm:p-7">
          <p className="text-[10px] font-bold uppercase tracking-[.18em] text-coral">Pipeline sequence</p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-.035em]">One direction, traceable at every stage</h2>
          <div className="mt-7 divide-y divide-line border-y border-line">
            {stages.map(([number, title, detail], index) => (
              <motion.div key={title} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * .08 }} className="grid grid-cols-[52px_1fr] gap-3 py-5 sm:grid-cols-[52px_180px_1fr] sm:items-center">
                <span className="font-mono text-xs text-coral">{number}</span>
                <p className="text-sm font-semibold">{title}</p>
                <p className="text-xs text-muted">{detail}</p>
              </motion.div>
            ))}
          </div>
          <dl className="mt-6 grid border-l border-t border-line sm:grid-cols-3">{[["Idempotent", "Checksums prevent duplicate ingestion"], ["Point in time", "Snapshots are appended, never overwritten"], ["Observable", "Every sync records counts and errors"]].map(([title, detail]) => <div key={title} className="border-b border-r border-line p-4"><dt className="text-xs font-bold text-forest">{title}</dt><dd className="mt-1 text-[10px] leading-4 text-muted">{detail}</dd></div>)}</dl>
        </article>
      </section>

      <section className="mt-8 bg-brand p-6 text-white sm:p-8">
        <div className="grid gap-8 lg:grid-cols-[.72fr_1.28fr]">
          <div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-mint">Sync contract</p><h2 className="mt-3 text-2xl font-semibold tracking-[-.04em]">The API stays stable while the source changes.</h2></div>
          <ol className="grid border-l border-t border-white/15 sm:grid-cols-2">{contract.map((item, index) => <motion.li initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ delay: index * .04 }} key={item} className="grid grid-cols-[32px_1fr] gap-2 border-b border-r border-white/15 p-4 text-xs text-white/70"><span className="font-mono text-coral">{String(index + 1).padStart(2, "0")}</span>{item}</motion.li>)}</ol>
        </div>
      </section>
    </>
  );
}
