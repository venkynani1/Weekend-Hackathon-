import { Moon, Sun } from "lucide-react";
import { useTheme } from "../theme/ThemeProvider";

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === "dark";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label={`Switch to ${dark ? "light" : "dark"} mode`}
      title={`Switch to ${dark ? "light" : "dark"} mode`}
      onClick={toggleTheme}
      className="inline-flex h-10 items-center gap-2 border border-line bg-surface px-2 text-ink transition-colors hover:border-forest"
    >
      <span className="relative h-5 w-9 border border-line bg-subtle" aria-hidden="true">
        <span className={`absolute top-0.5 grid size-4 place-items-center bg-brand text-white transition-transform ${dark ? "translate-x-[17px]" : "translate-x-0.5"}`}>
          {dark ? <Moon size={10} /> : <Sun size={10} />}
        </span>
      </span>
      {!compact && <span className="pr-1 text-[10px] font-bold uppercase tracking-[.12em]">{dark ? "Dark" : "Light"}</span>}
    </button>
  );
}
