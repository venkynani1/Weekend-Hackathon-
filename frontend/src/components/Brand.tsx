export function Brand({ compact = false, inverse = false }: { compact?: boolean; inverse?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative grid size-10 place-items-center overflow-hidden rounded-xl bg-coral text-white shadow-[0_8px_20px_rgba(215,104,79,.22)]">
        <span className="absolute left-2.5 top-3 h-4 w-1 bg-white/55" />
        <span className="absolute left-[17px] top-2 h-5 w-1 bg-white" />
        <span className="absolute right-2.5 top-4 h-3 w-1 bg-white/70" />
      </div>
      {!compact && (
        <div>
          <p className={`text-[15px] font-extrabold tracking-[-0.025em] ${inverse ? "text-white" : "text-ink"}`}>TalentGuard</p>
          <p className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${inverse ? "text-white/50" : "text-muted"}`}>Retention intelligence</p>
        </div>
      )}
    </div>
  );
}
