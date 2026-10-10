import { AnimatePresence, motion } from "motion/react";
import {
  Activity,
  BarChart3,
  Database,
  LayoutDashboard,
  LogOut,
  Menu,
  ShieldCheck,
  UsersRound,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "../auth/AuthProvider";

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/watchlist", label: "Watchlist", icon: UsersRound },
  { to: "/live-review", label: "Live review", icon: Activity },
  { to: "/governance", label: "Model evidence", icon: BarChart3 },
  { to: "/data-sync", label: "Data sync", icon: Database },
];

function Navigation({ close }: { close?: () => void }) {
  return (
    <nav className="mt-9 space-y-1.5" aria-label="Primary navigation">
      {navItems.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={close}
          className={({ isActive }) =>
            `group flex items-center gap-3 border-l-2 px-3.5 py-3 text-sm font-semibold transition ${
              isActive ? "border-coral bg-brand text-white" : "border-transparent text-muted hover:border-line hover:bg-surface hover:text-ink"
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon size={17} strokeWidth={isActive ? 2.4 : 1.8} />
              <span>{label}</span>
              {isActive && <motion.span layoutId="active-nav" className="ml-auto h-px w-5 bg-coral" />}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[256px] border-r border-line bg-[#f3f5ef] p-5 lg:flex lg:flex-col">
      <Brand />
      <Navigation />
      <div className="mt-auto border-y border-forest/15 bg-surface/60 py-4">
        <div className="flex items-center gap-2 text-forest">
          <ShieldCheck size={16} />
          <span className="text-xs font-bold">Human review required</span>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-muted">Risk scores support prioritization. They never automate employment decisions.</p>
      </div>
    </aside>
  );
}

export function AppLayout() {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, signOut } = useAuth();

  useEffect(() => setMobileOpen(false), [location.pathname]);

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <Sidebar />
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.button
              aria-label="Close navigation"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-40 bg-ink/35 backdrop-blur-sm lg:hidden"
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 360, damping: 34 }}
              className="fixed inset-y-0 left-0 z-50 w-[280px] border-r border-line bg-[#f3f5ef] p-5 lg:hidden"
            >
              <div className="flex items-center justify-between">
                <Brand />
                <button onClick={() => setMobileOpen(false)} className="grid size-9 place-items-center border border-line bg-white" aria-label="Close menu"><X size={17} /></button>
              </div>
              <Navigation close={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="lg:pl-[256px]">
        <header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-line/80 bg-canvas/85 px-4 backdrop-blur-xl sm:px-7 lg:px-10">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="grid size-10 place-items-center border border-line bg-white lg:hidden" aria-label="Open menu"><Menu size={18} /></button>
            <div className="hidden items-center gap-2 border border-forest/10 bg-white px-3 py-1.5 text-[11px] font-semibold text-forest sm:flex">
              <span className="size-2 bg-emerald-600" />
              Analysis ready
            </div>
            <div className="hidden h-4 w-px bg-line sm:block" />
            <p className="hidden text-xs text-muted sm:block">Synthetic workforce · historical validation</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 border border-line bg-white px-3 py-2 text-xs font-semibold text-ink sm:flex"><Activity size={15} className="text-coral" /> Approved model</div>
            <div className="hidden sm:block"><ThemeToggle /></div>
            <div className="sm:hidden"><ThemeToggle compact /></div>
            <div className="hidden text-right md:block"><p className="max-w-48 truncate text-[11px] font-semibold text-ink">{user?.email}</p><p className="text-[9px] uppercase tracking-wider text-muted">Authenticated</p></div>
            <div className="grid size-10 place-items-center bg-brand text-xs font-bold text-white">{(user?.email?.slice(0, 2) ?? "HR").toUpperCase()}</div>
            <button onClick={() => void signOut()} className="grid size-10 place-items-center border border-line bg-white text-muted transition hover:border-coral/30 hover:text-coral" aria-label="Sign out"><LogOut size={16} /></button>
          </div>
        </header>

        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto min-h-[calc(100vh-72px)] max-w-[1500px] px-4 py-7 sm:px-7 lg:px-10 lg:py-9"
          >
            <Outlet />
          </motion.main>
        </AnimatePresence>
        <footer className="mx-auto flex max-w-[1500px] flex-col gap-3 border-t border-line px-4 py-5 text-[11px] text-muted sm:flex-row sm:items-center sm:justify-between sm:px-7 lg:px-10">
          <p>TalentGuard prototype. Human review is required for every action.</p>
          <div className="flex flex-wrap gap-4">
            <a href="/privacy" className="font-semibold text-forest hover:underline">Privacy</a>
            <a href="/terms" className="font-semibold text-forest hover:underline">Terms</a>
            <button type="button" onClick={() => window.dispatchEvent(new Event("talentguard:privacy-settings"))} className="font-semibold text-forest hover:underline">Privacy settings</button>
          </div>
        </footer>
      </div>
    </div>
  );
}
