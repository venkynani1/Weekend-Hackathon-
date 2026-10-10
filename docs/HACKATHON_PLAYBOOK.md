# TalentGuard hackathon playbook

## One-sentence positioning

TalentGuard turns an imbalanced attrition model into a capacity-bounded HR review
workflow: 50 people, three reasons each, a proposed supportive action, and an
auditable human decision.

## Three-minute pitch

### 0:00 to 0:35: business decision

TechNova loses 16% of 12,000 employees each year. That is roughly 1,920 exits.
If each exit costs 6 to 9 months of salary, the decision is not "who will quit?"
in isolation. The decision is which 50 cases HR should review this cycle and what
supportive action to test while there is still time.

Business success metric: retained payroll-cost exposure per 50 completed reviews,
measured against a randomized or policy-based comparison group. Model AUC is not
the business outcome.

### 0:35 to 1:10: data evidence and traps

- 1,470 rows, 35 source columns, 237 exits, and no missing cells.
- An all-retained prediction is 83.9% accurate and catches zero exits.
- `EmployeeNumber` is an ID. `EmployeeCount`, `StandardHours`, and `Over18` are constants.
- Historical attrition is 30.5% with overtime versus 10.4% without it.
- Sales representatives have the highest role rate at about 39.8%.
- These are associations, not causal effects.

### 1:10 to 1:45: honest model choice

We compare balanced logistic regression, random forest, and gradient boosted trees
using five-fold out-of-fold predictions. Preprocessing is inside the pipeline and
fits on each training fold only. Logistic regression wins on average precision
and reaches 0.821 ROC-AUC. The Top 50 contains 44 historical exits, which is 88%
precision and 5.46 times the base rate. The simpler baseline wins honestly.

### 1:45 to 2:35: live demo

1. Open **Live review**.
2. Enter employee number `1` and run the evidence review.
3. Explain that the ID retrieves a persisted score and never enters the model.
4. Show score, rank, three reasons, and the proposed first action.
5. Open the intervention workflow.
6. Show the rule-based note marked `PENDING_APPROVAL`.
7. Save an intervention, close the drawer, refresh, and show the audit history.
8. Open **Model evidence** and point to candidate comparison, calibration, fairness, and leakage controls.

Do not call the live lookup fresh inference. It retrieves a score from the approved
run. That distinction demonstrates model governance rather than weakness.

### 2:35 to 3:00: value and close

TalentGuard does not automate a job decision. It makes a limited HR review queue
more evidence-based, explains why each case is present, drafts but never sends the
next action, and records what humans actually did. The next production test is a
measured retention intervention with temporal validation, not a larger model.

## Suggested team handoff

- Speaker 1: client problem, HR capacity, and business metric.
- Speaker 2: EDA traps, leakage prevention, and model comparison.
- Speaker 3: live score review, intervention save, and agent draft.
- Speaker 4: governance, privacy, deployment architecture, and close.

If the team has three members, Speaker 1 also delivers the closing value statement.

## Judge questions

### Why not accuracy?

Attrition is 16.1%. Predicting retention for everyone is 83.9% accurate while
finding no exits. Average precision, ROC-AUC, and precision within HR's 50-person
capacity measure the actual ranking problem.

### What was fitted on training data only?

Imputation, scaling, one-hot encoding, feature transformations, and the estimator
are one scikit-learn pipeline. Each cross-validation fold fits that entire pipeline
only on its training rows.

### Is overtime causal?

No. It is an observed association and a predictive feature. A workload conversation
is an intervention hypothesis that must be tested, consented to, and measured.

### Why did the baseline win?

Balanced logistic regression has the best out-of-fold average precision and Top-50
precision. The tree models did not add enough value to justify lower transparency.

### Why is recall only 18.6%?

HR can review only 50 of 1,470 people. Recall is therefore capacity constrained.
Within that constraint, the queue contains 44 of the 237 historical exits and has
5.46 times the base rate. Increasing recall requires more review capacity or a
different operating policy.

### What does the risk score mean?

It is a ranking signal from this benchmark, not a guaranteed resignation probability.
The calibration page reports probability error and clearly marks the prototype as
not recalibrated.

### How do you address fairness?

Age, gender, and marital status are excluded from training. We still report group
selection and true-positive coverage because proxy effects can remain. Production
use would require impact thresholds, escalation rules, and ongoing monitoring.

### Where are the secrets?

The browser receives only the Supabase publishable key. The secret key and hosted
database connection live only in trusted Render jobs. Supabase RLS isolates rows by
organization, and a test scans frontend source for backend secret markers.

## Submission checklist

- GitHub link points to the complete branch with no `.env` or database credentials.
- `output/top_50_watchlist.csv` is attached as the required artifact.
- App URL opens on mobile and desktop.
- Render health endpoint returns 200.
- First admin can sign in and see the Supabase-backed dashboard.
- Save intervention, refresh, and show the audit event.
- Vercel Web Analytics is enabled; analytics remains opt-in.
- Social preview, favicon, sitemap, robots, privacy, terms, and 404 are reachable.
- MLflow UI shows four runs: parent selection plus three candidates.
- Every team member rehearses their section under the three-minute limit.

## Industry follow-ons after the hackathon

1. Measure intervention uplift with a controlled rollout rather than assuming that a risk factor is a treatment lever.
2. Add outcome taxonomy such as accepted support, declined support, role move, manager change, and voluntary exit.
3. Track queue saturation and time-to-first-review as operational service levels.
4. Add model and data drift alerts by snapshot date, department, and job role.
5. Build an employee-facing transparency and appeal process before any production use.
6. Integrate an HRIS through least-privilege, read-only views and an approved identity mapping layer.
