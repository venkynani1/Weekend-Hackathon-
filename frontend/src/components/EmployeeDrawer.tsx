import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, BriefcaseBusiness, CalendarClock, Check, Clipboard, Clock3, History, LoaderCircle, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useIntervention } from "../hooks/useIntervention";
import { percent } from "../lib/format";
import type { EmployeeRisk, InterventionPayload, InterventionStatus } from "../types";
import { RiskBadge } from "./ui";

const statuses: Array<{ value: InterventionStatus; label: string }> = [
  { value: "not_reviewed", label: "Not reviewed" },
  { value: "reviewed", label: "Reviewed" },
  { value: "intervention_planned", label: "Intervention planned" },
  { value: "follow_up_scheduled", label: "Follow-up scheduled" },
  { value: "closed", label: "Closed" },
];

function statusLabel(status: InterventionStatus) {
  return statuses.find((item) => item.value === status)?.label ?? status;
}

export function EmployeeDrawer({ employee, close }: { employee: EmployeeRisk | null; close: () => void }) {
  const intervention = useIntervention(employee?.EmployeeNumber ?? null);
  const [status, setStatus] = useState<InterventionStatus>("not_reviewed");
  const [type, setType] = useState("");
  const [notes, setNotes] = useState("");
  const [owner, setOwner] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [saved, setSaved] = useState(false);
  const [draftCopied, setDraftCopied] = useState(false);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    if (!employee) return;
    const record = intervention.data?.case;
    setStatus(record?.status ?? "not_reviewed");
    setType(record?.intervention_type ?? employee.PrimaryAction);
    setNotes(record?.notes ?? "");
    setOwner(record?.assigned_to_name ?? "");
    setFollowUp(record?.follow_up_at?.slice(0, 10) ?? "");
  }, [employee, intervention.data?.case]);

  useEffect(() => {
    if (!employee) return;
    const handleKey = (event: KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [employee, close]);

  async function saveIntervention() {
    if (!employee) return;
    if (type.trim().length > 120 || owner.trim().length > 120 || notes.trim().length > 1000) {
      setValidationError("Intervention and owner must be under 120 characters; notes must be under 1,000 characters.");
      return;
    }
    setValidationError("");
    setSaved(false);
    const payload: InterventionPayload = {
      source_employee_id: employee.EmployeeNumber,
      status,
      intervention_type: type.trim() || null,
      notes: notes.trim() || null,
      assigned_to_name: owner.trim() || null,
      follow_up_at: followUp ? new Date(`${followUp}T12:00:00Z`).toISOString() : null,
    };
    await intervention.save(payload);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
  }

  const pendingDraft = employee ? [
    "PENDING_APPROVAL",
    "Subject: Supportive career check-in",
    "",
    "Hello,",
    "",
    `I would like to schedule a confidential check-in focused on your experience in the ${employee.JobRole} role. The goal is to understand what is working, where support may help, and whether there are practical changes we should explore together.`,
    "",
    `Suggested discussion focus: ${employee.PrimaryAction}.`,
    "",
    "No decision has been made. Please edit this draft for context, tone, consent, and local HR policy before sending.",
  ].join("\n") : "";

  async function copyDraft() {
    await navigator.clipboard.writeText(pendingDraft);
    setDraftCopied(true);
    window.setTimeout(() => setDraftCopied(false), 1800);
  }

  return (
    <AnimatePresence>
      {employee && (
        <>
          <motion.button aria-label="Close employee review" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={close} className="fixed inset-0 z-40 bg-ink/35 backdrop-blur-[3px]" />
          <motion.aside role="dialog" aria-modal="true" aria-labelledby="employee-review-title" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 330, damping: 34 }} className="fixed inset-y-0 right-0 z-50 w-full max-w-[610px] overflow-y-auto border-l border-line bg-[#fbfcf8]">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-[#fbfcf8]/90 px-6 py-5 backdrop-blur-xl sm:px-8">
              <div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-coral">Employee review</p><h2 id="employee-review-title" className="mt-1 text-2xl font-semibold tracking-[-.04em]">Employee {employee.EmployeeNumber}</h2></div>
              <button onClick={close} className="grid size-10 place-items-center border border-line bg-white transition hover:border-forest/30" aria-label="Close"><X size={18} /></button>
            </div>

            <div className="space-y-7 p-6 sm:p-8">
              <div className="grid grid-cols-3 overflow-hidden bg-brand text-white">
                {[["Rank", `#${String(employee.Rank).padStart(2, "0")}`], ["Risk score", percent(employee.RiskScore)], ["Outcome", employee.HistoricalOutcome]].map(([label, value], index) => <div key={label} className={`p-4 ${index < 2 ? "border-r border-white/10" : ""}`}><p className="text-[9px] font-semibold uppercase tracking-wider text-white/55">{label}</p><p className="mt-2 text-lg font-semibold">{value}</p></div>)}
              </div>

              <section>
                <div className="flex items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-wider text-coral">{employee.Department}</p><h3 className="mt-1 text-xl font-semibold">{employee.JobRole}</h3></div><RiskBadge band={employee.RiskBand} /></div>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted"><span className="flex items-center gap-1.5 border border-line bg-white px-2.5 py-2"><BriefcaseBusiness size={13} /> {employee.YearsAtCompany} years at company</span><span className="flex items-center gap-1.5 border border-line bg-white px-2.5 py-2"><Clock3 size={13} /> {employee.YearsInCurrentRole} years in role</span><span className="flex items-center gap-1.5 border border-line bg-white px-2.5 py-2"><CalendarClock size={13} /> Overtime: {employee.OverTime}</span></div>
              </section>

              <section>
                <p className="mb-3 text-[10px] font-bold uppercase tracking-[.16em] text-muted">Leading risk signals</p>
                <div className="divide-y divide-line border-y border-line">{[employee.RiskReason1, employee.RiskReason2, employee.RiskReason3].map((reason, index) => <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .1 + index * .06 }} key={`${reason}-${index}`} className="flex gap-3 bg-white py-3.5 text-sm leading-5"><span className="grid size-6 shrink-0 place-items-center bg-coral-soft text-[10px] font-bold text-coral-deep">{index + 1}</span>{reason}</motion.div>)}</div>
              </section>

              <section className="border-y border-forest/15 bg-mint p-5"><p className="text-[10px] font-bold uppercase tracking-[.16em] text-forest/60">Recommended intervention</p><div className="mt-2 flex items-center gap-2"><strong className="text-base text-forest">{employee.PrimaryAction}</strong><ArrowUpRight size={16} className="text-forest" /></div><p className="mt-3 text-sm leading-6 text-forest/75">{employee.Recommendation}</p></section>

              <section className="border border-amber-200 bg-amber-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-amber-900">Agent-assisted draft</p><h3 className="mt-1 text-sm font-semibold text-ink">PENDING_APPROVAL</h3></div><button type="button" onClick={() => void copyDraft()} className="inline-flex h-9 items-center gap-2 border border-amber-300 bg-white px-3 text-[11px] font-semibold text-amber-950 hover:border-amber-500">{draftCopied ? <Check size={14} /> : <Clipboard size={14} />}{draftCopied ? "Copied" : "Copy draft"}</button></div>
                <pre className="mt-4 whitespace-pre-wrap font-sans text-xs leading-5 text-amber-950/80">{pendingDraft}</pre>
                <p className="mt-3 border-t border-amber-200 pt-3 text-[10px] leading-4 text-amber-900/75">Rule-based draft. It omits the risk score and must be reviewed, edited, and approved by a qualified person before use.</p>
              </section>

              <section className="border-y border-line bg-white p-5">
                <div className="mb-4 flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-muted">Persistent intervention</p><p className="mt-1 text-xs text-muted">Every save is added to the audit history.</p></div><span className="border border-forest/10 bg-mint px-2.5 py-1 text-[10px] font-bold text-forest">{statusLabel(status)}</span></div>
                {intervention.isLoading ? <div className="flex items-center gap-2 py-5 text-xs text-muted"><LoaderCircle size={15} className="animate-spin" /> Loading intervention…</div> : (
                  <div className="space-y-4">
                    <div className="grid gap-2 sm:grid-cols-2">{statuses.map((item) => <button key={item.value} onClick={() => setStatus(item.value)} className={`flex items-center justify-between border px-3.5 py-3 text-left text-xs font-semibold transition ${status === item.value ? "border-brand bg-brand text-white" : "border-line bg-[#f8f9f6] text-ink hover:border-forest/30"}`}>{item.label}{status === item.value && <Check size={14} />}</button>)}</div>
                    <div className="grid gap-3 sm:grid-cols-2"><label><span className="mb-1.5 block text-[10px] font-bold text-muted">Intervention</span><input maxLength={120} value={type} onChange={(event) => setType(event.target.value)} className="h-10 w-full border border-line bg-[#f8f9f6] px-3 text-xs outline-none focus:border-forest/40" /></label><label><span className="mb-1.5 block text-[10px] font-bold text-muted">Owner</span><input maxLength={120} value={owner} onChange={(event) => setOwner(event.target.value)} className="h-10 w-full border border-line bg-[#f8f9f6] px-3 text-xs outline-none focus:border-forest/40" placeholder="HR partner" /></label></div>
                    <label className="block"><span className="mb-1.5 block text-[10px] font-bold text-muted">Follow-up date</span><input type="date" min={new Date().toISOString().slice(0, 10)} value={followUp} onChange={(event) => setFollowUp(event.target.value)} className="h-10 w-full border border-line bg-[#f8f9f6] px-3 text-xs outline-none focus:border-forest/40" /></label>
                    <label className="block"><span className="mb-1.5 block text-[10px] font-bold text-muted">Reviewer notes</span><textarea maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} className="w-full resize-none border border-line bg-[#f8f9f6] px-3 py-2.5 text-xs leading-5 outline-none focus:border-forest/40" placeholder="Record context, consent, and next steps." /><span className="mt-1 block text-right text-[9px] text-muted">{notes.length}/1000</span></label>
                    {validationError && <p role="alert" className="text-xs text-red-700">{validationError}</p>}
                    {intervention.saveError && <p role="alert" className="text-xs text-red-700">{intervention.saveError.message}</p>}
                    <button onClick={() => void saveIntervention()} disabled={intervention.isSaving} className="flex h-11 w-full items-center justify-center gap-2 bg-coral text-xs font-bold text-white transition hover:bg-coral-deep disabled:cursor-wait disabled:opacity-60">{intervention.isSaving ? <LoaderCircle size={15} className="animate-spin" /> : saved ? <Check size={15} /> : <Save size={15} />}{intervention.isSaving ? "Saving…" : saved ? "Saved to Supabase" : "Save intervention"}</button>
                  </div>
                )}
              </section>

              {intervention.data?.events.length ? <section><p className="mb-3 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[.16em] text-muted"><History size={14} /> Recent audit history</p><div className="divide-y divide-line border-y border-line">{intervention.data.events.slice(0, 4).map((event) => <div key={event.id} className="bg-white py-3"><div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold">{statusLabel(event.to_status)}</p><time className="text-[9px] text-muted">{new Date(event.created_at).toLocaleString()}</time></div>{event.notes && <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">{event.notes}</p>}</div>)}</div></section> : null}

              <p className="border-t border-line pt-5 text-[11px] leading-5 text-muted">Predictive signals are not causal findings. Confirm context with the employee and a qualified HR reviewer before taking action.</p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
