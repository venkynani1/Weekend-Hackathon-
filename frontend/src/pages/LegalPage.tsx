import { Link } from "react-router-dom";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";

const notices = {
  privacy: {
    eyebrow: "Privacy notice",
    title: "How TalentGuard handles workforce data.",
    intro: "This hackathon prototype processes synthetic workforce records and authenticated reviewer activity to demonstrate responsible retention decision support.",
    sections: [
      ["Data we process", "Supabase Auth stores account identifiers and session information. The application stores synthetic employee snapshots, persisted model scores, intervention status, reviewer notes, follow-up dates, and an append-only audit history."],
      ["Why we process it", "Data is used to rank a fixed HR review queue, explain predictive signals, record supportive interventions, and demonstrate model governance. TalentGuard must not be used to make automated employment decisions."],
      ["Access controls", "Authenticated users can access only organizations to which they are assigned. Supabase Row Level Security enforces tenant boundaries. Backend ingestion credentials and the Supabase secret key are never shipped to the browser."],
      ["Analytics and browser storage", "Authentication requires essential local browser storage. Optional Vercel Web Analytics is disabled until you consent. Analytics events are stripped of query strings and do not include employee identifiers, account emails, intervention notes, or form values."],
      ["Retention and deletion", "Prototype data remains until the project administrator removes it. In a production deployment, the customer must define retention periods, employee access rights, deletion procedures, and lawful bases with its privacy and legal teams."],
      ["Contact", "For this prototype, privacy questions and deletion requests should be directed to the project owner through the repository contact channel."],
    ],
  },
  terms: {
    eyebrow: "Terms of use",
    title: "Responsible use comes before a score.",
    intro: "By using this prototype, you agree to treat every output as a review signal that requires human context, not as a decision about an employee.",
    sections: [
      ["Permitted use", "TalentGuard may be used for demonstration, model evaluation, capacity planning, and supportive retention workflow testing with authorized data."],
      ["Prohibited use", "Do not use the application to terminate, discipline, deny opportunity, surveil, or otherwise disadvantage a person. Do not connect production HR data without organizational approval, a lawful basis, access controls, and a documented impact assessment."],
      ["Model limitations", "Scores are trained on a small historical benchmark dataset. Associations such as overtime and attrition are predictive, not causal. Scores can be wrong, drift over time, and differ across groups."],
      ["Human review", "A qualified HR reviewer must verify context, minimize disclosure, document consent where appropriate, and measure whether an intervention is helpful. Draft communications remain PENDING_APPROVAL until a reviewer edits and approves them."],
      ["Security", "Users must protect their credentials and may access only their assigned organization. Attempts to bypass authentication, tenant isolation, rate limits, or audit controls are prohibited."],
      ["Prototype status", "The software is provided for hackathon evaluation without warranties. A production rollout requires legal review, security testing, accessibility review, monitoring, incident response, and customer-specific policies."],
    ],
  },
} as const;

export function LegalPage({ kind }: { kind: keyof typeof notices }) {
  const notice = notices[kind];
  return (
    <main className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 py-5 sm:px-8">
          <Brand />
          <div className="flex items-center gap-3"><ThemeToggle compact /><Link to="/" className="text-xs font-semibold text-forest underline underline-offset-4">Return to application</Link></div>
        </div>
      </header>
      <article className="mx-auto max-w-4xl px-5 py-12 sm:px-8 sm:py-16">
        <p className="text-xs font-bold uppercase tracking-[.16em] text-coral">{notice.eyebrow}</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-[-.045em] sm:text-5xl">{notice.title}</h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-muted">{notice.intro}</p>
        <p className="mt-5 text-xs text-muted">Effective 10 October 2026</p>
        <div className="mt-12 divide-y divide-line border-y border-line">
          {notice.sections.map(([title, body]) => (
            <section key={title} className="grid gap-3 py-6 md:grid-cols-[180px_1fr] md:gap-8">
              <h2 className="text-sm font-semibold text-forest">{title}</h2>
              <p className="text-sm leading-7 text-muted">{body}</p>
            </section>
          ))}
        </div>
        <p className="mt-8 text-xs leading-5 text-muted">This prototype notice is a product transparency document and is not legal advice.</p>
      </article>
    </main>
  );
}
