import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const metadata: Record<string, { title: string; description: string; robots?: string }> = {
  "/": { title: "TalentGuard | Retention intelligence", description: "Capacity-ranked employee attrition signals, evidence, and auditable retention interventions for HR teams." },
  "/watchlist": { title: "Top-50 watchlist | TalentGuard", description: "Review the ranked Top-50 attrition watchlist with three risk reasons and recommended actions.", robots: "noindex,nofollow" },
  "/live-review": { title: "Live score review | TalentGuard", description: "Look up an employee's approved risk score, evidence, and recommended human review action.", robots: "noindex,nofollow" },
  "/governance": { title: "Model evidence | TalentGuard", description: "Inspect validation, calibration, fairness, leakage controls, and the Top-50 operating point.", robots: "noindex,nofollow" },
  "/data-sync": { title: "Data pipeline | TalentGuard", description: "Inspect the hosted-source ingestion history and immutable Supabase snapshot pipeline.", robots: "noindex,nofollow" },
  "/privacy": { title: "Privacy notice | TalentGuard", description: "How the TalentGuard prototype handles authentication, workforce records, analytics, and retention review data." },
  "/terms": { title: "Terms of use | TalentGuard", description: "Responsible-use terms for the TalentGuard employee attrition decision-support prototype." },
  "/404": { title: "Page not found | TalentGuard", description: "The requested TalentGuard page could not be found.", robots: "noindex,nofollow" },
};

function upsertMeta(name: string, content: string, property = false) {
  const attribute = property ? "property" : "name";
  let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${name}"]`);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attribute, name);
    document.head.appendChild(element);
  }
  element.content = content;
}

export function RouteMetadata() {
  const location = useLocation();
  useEffect(() => {
    const current = metadata[location.pathname] ?? metadata["/404"];
    document.title = current.title;
    upsertMeta("description", current.description);
    upsertMeta("robots", current.robots ?? "index,follow");
    upsertMeta("og:title", current.title, true);
    upsertMeta("og:description", current.description, true);
    upsertMeta("og:url", `${window.location.origin}${location.pathname}`, true);
    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.appendChild(canonical);
    }
    canonical.href = `${window.location.origin}${location.pathname}`;
  }, [location.pathname]);
  return null;
}
