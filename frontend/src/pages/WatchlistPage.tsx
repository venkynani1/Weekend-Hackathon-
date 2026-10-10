import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, Download, Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { EmployeeDrawer } from "../components/EmployeeDrawer";
import { ErrorState, PageHeader, RiskBadge, SkeletonPage } from "../components/ui";
import { useDashboard } from "../hooks/useDashboard";
import { downloadFile } from "../lib/api";
import { compact, percent } from "../lib/format";
import type { EmployeeRisk } from "../types";

export function WatchlistPage() {
  const query = useDashboard();
  const [search, setSearch] = useState("");
  const [capacity, setCapacity] = useState(50);
  const [department, setDepartment] = useState("");
  const [band, setBand] = useState("");
  const [selected, setSelected] = useState<EmployeeRisk | null>(null);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (query.data?.watchlist ?? []).filter((employee) => {
      const text = `${employee.EmployeeNumber} ${employee.JobRole} ${employee.Department} ${employee.PrimaryAction}`.toLowerCase();
      return employee.Rank <= capacity && (!term || text.includes(term)) && (!department || employee.Department === department) && (!band || employee.RiskBand === band);
    });
  }, [query.data, search, capacity, department, band]);

  if (query.isLoading) return <SkeletonPage />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? "No data was returned."} retry={() => query.refetch()} />;

  const exits = filtered.filter((item) => item.HistoricalOutcome === "Yes").length;
  const exposure = filtered.reduce((sum, item) => sum + item.MonthlyIncome * 6, 0);

  return (
    <>
      <PageHeader
        eyebrow="Capacity-ranked review"
        title="A watchlist built around the work HR can actually do."
        description="Search, filter and review the highest out-of-fold risk scores. Open any employee to see the evidence and proposed intervention."
        action={<button onClick={() => void downloadFile("/downloads/watchlist.csv", "TalentGuard_Top_50_Watchlist.csv")} className="inline-flex h-11 items-center gap-2 bg-brand px-4 text-xs font-bold text-white transition hover:bg-brand-light"><Download size={15} /> Export CSV</button>}
      />

      <section className="border-y border-line bg-white p-4">
        <div className="grid gap-3 lg:grid-cols-[1fr_160px_210px_170px]">
          <label className="relative"><span className="sr-only">Search employees</span><Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" /><input value={search} onChange={(event) => setSearch(event.target.value)} className="h-11 w-full border border-line bg-[#f8f9f6] pl-10 pr-4 text-xs outline-none transition placeholder:text-muted/70 focus:border-forest/40 focus:ring-2 focus:ring-mint" placeholder="Search employee, role, or action" /></label>
          <label><span className="sr-only">Capacity</span><select value={capacity} onChange={(event) => setCapacity(Number(event.target.value))} className="h-11 w-full border border-line bg-[#f8f9f6] px-3 text-xs font-semibold outline-none focus:border-forest/40"><option value={10}>Priority 10</option><option value={25}>Top 25</option><option value={50}>Full Top 50</option></select></label>
          <label><span className="sr-only">Department</span><select value={department} onChange={(event) => setDepartment(event.target.value)} className="h-11 w-full border border-line bg-[#f8f9f6] px-3 text-xs font-semibold outline-none focus:border-forest/40"><option value="">All departments</option>{query.data.departments.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label><span className="sr-only">Risk band</span><select value={band} onChange={(event) => setBand(event.target.value)} className="h-11 w-full border border-line bg-[#f8f9f6] px-3 text-xs font-semibold outline-none focus:border-forest/40"><option value="">All risk bands</option><option>Priority</option><option>High</option><option>Elevated</option></select></label>
        </div>
      </section>

      <section className="my-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Records shown", String(filtered.length)],
          ["Historical exits", String(exits)],
          ["Observed precision", percent(filtered.length ? exits / filtered.length : 0)],
          ["Cost exposure", `${compact(exposure)} units`],
        ].map(([label, value]) => <div key={label} className="border-l border-line bg-[#f4f6f1] px-4 py-3"><p className="text-[10px] font-semibold text-muted">{label}</p><motion.p key={value} initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} className="mt-1 text-lg font-semibold tracking-[-.03em] text-forest">{value}</motion.p></div>)}
      </section>

      <section className="overflow-hidden border-y border-line bg-white">
        <div className="flex items-center justify-between border-b border-line px-5 py-4"><div className="flex items-center gap-2 text-xs font-bold text-ink"><SlidersHorizontal size={15} className="text-coral" /> Ranked intervention queue</div><p className="text-[11px] text-muted">{filtered.length} of {capacity}</p></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-left">
            <thead><tr className="bg-brand text-[9px] uppercase tracking-[.14em] text-white/65"><th className="px-5 py-3.5">Rank</th><th className="px-4 py-3.5">Employee</th><th className="px-4 py-3.5">Risk</th><th className="px-4 py-3.5">Department</th><th className="px-4 py-3.5">Leading signal</th><th className="px-4 py-3.5">First action</th><th className="px-5 py-3.5" /></tr></thead>
            <motion.tbody layout>
              <AnimatePresence initial={false}>
                {filtered.map((employee) => (
                  <motion.tr layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }} key={employee.EmployeeNumber} className="group border-b border-line/80 last:border-0 hover:bg-[#f8faf6]">
                    <td className="px-5 py-4 text-sm font-bold text-coral">{String(employee.Rank).padStart(2, "0")}</td>
                    <td className="px-4 py-4"><p className="text-xs font-bold">Employee {employee.EmployeeNumber}</p><p className="mt-1 text-[10px] text-muted">{employee.JobRole}</p></td>
                    <td className="px-4 py-4"><div className="flex items-center gap-2"><strong className="text-xs">{percent(employee.RiskScore)}</strong><RiskBadge band={employee.RiskBand} /></div></td>
                    <td className="px-4 py-4 text-xs text-muted">{employee.Department}</td>
                    <td className="max-w-[250px] px-4 py-4 text-[11px] leading-5 text-ink/75">{employee.RiskReason1}</td>
                    <td className="px-4 py-4"><span className="border border-forest/10 bg-mint px-2.5 py-1.5 text-[10px] font-bold text-forest">{employee.PrimaryAction}</span></td>
                    <td className="px-5 py-4 text-right"><button onClick={() => setSelected(employee)} aria-label={`Review employee ${employee.EmployeeNumber}`} className="grid size-8 place-items-center border border-line text-forest transition group-hover:border-forest group-hover:bg-brand group-hover:text-white"><ArrowUpRight size={14} /></button></td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </motion.tbody>
          </table>
        </div>
        {!filtered.length && <div className="py-16 text-center"><p className="text-sm font-semibold">No employees match these filters.</p><button onClick={() => { setSearch(""); setDepartment(""); setBand(""); }} className="mt-3 text-xs font-bold text-coral">Reset filters</button></div>}
      </section>

      <EmployeeDrawer employee={selected} close={() => setSelected(null)} />
    </>
  );
}
