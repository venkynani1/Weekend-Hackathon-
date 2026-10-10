import { Analytics, type BeforeSendEvent } from "@vercel/analytics/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

type Consent = "analytics" | "necessary" | null;
const STORAGE_KEY = "talentguard-cookie-consent-v1";

function readConsent(): Consent {
  const value = window.localStorage.getItem(STORAGE_KEY);
  return value === "analytics" || value === "necessary" ? value : null;
}

function redactAnalyticsEvent(event: BeforeSendEvent): BeforeSendEvent | null {
  try {
    const url = new URL(event.url);
    url.search = "";
    url.hash = "";
    return { ...event, url: url.toString() };
  } catch {
    return null;
  }
}

export function CookieConsent() {
  const [consent, setConsent] = useState<Consent>(() => readConsent());
  useEffect(() => {
    const reopen = () => setConsent(null);
    window.addEventListener("talentguard:privacy-settings", reopen);
    return () => window.removeEventListener("talentguard:privacy-settings", reopen);
  }, []);
  function choose(next: Exclude<Consent, null>) {
    window.localStorage.setItem(STORAGE_KEY, next);
    setConsent(next);
  }
  return (
    <>
      {consent === "analytics" && <Analytics beforeSend={redactAnalyticsEvent} />}
      {consent === null && (
        <aside className="fixed inset-x-3 bottom-3 z-[80] mx-auto max-w-3xl border border-line bg-white p-4 sm:bottom-5 sm:flex sm:items-center sm:gap-5 sm:p-5" role="dialog" aria-label="Analytics preferences" aria-live="polite">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">Privacy choice</p>
            <p className="mt-1 text-xs leading-5 text-muted">TalentGuard uses essential browser storage for authentication. Optional Vercel Analytics loads only with your permission and never receives employee IDs, emails, notes, query strings, or form values. Read the <Link to="/privacy" className="font-semibold text-forest underline underline-offset-2">privacy notice</Link>.</p>
          </div>
          <div className="mt-4 flex shrink-0 flex-wrap gap-2 sm:mt-0">
            <button type="button" onClick={() => choose("necessary")} className="h-10 border border-line bg-white px-4 text-xs font-semibold text-ink hover:border-forest">Necessary only</button>
            <button type="button" onClick={() => choose("analytics")} className="h-10 bg-brand px-4 text-xs font-semibold text-white hover:bg-brand-light">Accept analytics</button>
          </div>
        </aside>
      )}
    </>
  );
}
