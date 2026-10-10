# TalentGuard

TalentGuard is a historical retention-risk prototype built from the IBM HR Employee Attrition dataset. It compares three classification pipelines, ranks the 50 records with the highest out-of-fold risk scores, explains three local risk drivers per employee, and creates a focused action plan for the first 10.

## What it produces

- Smooth responsive React and Tailwind dashboard backed by Flask
- Interactive Top-10, Top-25, and Top-50 capacity views
- Demo turnover-cost exposure using a clearly labelled assumption
- Supabase-authenticated, persistent intervention tracking with audit history
- Ranked Top-50 watch list
- Detailed Top-10 intervention plan
- Three employee-level risk reasons
- Model comparison and holdout evidence
- Department and common-driver summaries
- Authenticated CSV exports
- Calibration, fairness, and temporal-readiness reporting
- Hosted PostgreSQL ingestion and model-publication jobs
- Live approved-score lookup for the on-stage demo
- Rule-based retention note marked `PENDING_APPROVAL`
- Privacy notice, terms, consent-gated analytics, sitemap, robots file, favicon, social card, and custom 404
- Optional local MLflow model comparison

## Run locally

From PowerShell in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-ml.txt
python train.py
python app.py
```

Open `http://127.0.0.1:5000`.

For the React application, copy `frontend/.env.example` to `frontend/.env.local`, fill in the Supabase publishable values, and run:

```powershell
cd frontend
npm install
npm run dev
```

Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the Flask environment to use the hosted database. Without them, Flask intentionally falls back to packaged outputs for local tests.

## Rebuild the analysis

```powershell
python train.py
```

Optional paths:

```powershell
python train.py --dataset dataset\WA_Fn-UseC_-HR-Employee-Attrition.csv --output-dir output --artifact-dir artifacts
```

Generated files:

- `output/top_50_watchlist.csv`
- `output/top_10_action_plan.csv`
- `output/all_risk_scores.csv`
- `output/model_metrics.json`
- `artifacts/talentguard_pipeline.joblib`

## MLflow bonus

MLflow is optional and stays out of the production Flask dependency set. Run a
local comparison with one parent selection run and one nested run per candidate:

```powershell
python -m pip install -r requirements-mlflow.txt
python train.py --mlflow
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Open `http://127.0.0.1:5000` to compare logistic regression, random forest, and
gradient boosted trees. The local SQLite store is ignored by Git.

## Modeling approach

The pipeline excludes the target, employee identifier, constant columns, age, gender, and marital status. It adds transparent satisfaction and tenure-ratio features, one-hot encodes categorical columns, and standardizes numeric columns.

Three candidates are compared with five-fold stratified out-of-fold predictions:

1. Logistic regression
2. Random forest
3. Histogram gradient-boosted trees

The highest average precision wins. Precision, recall, F1, ROC-AUC, lift, and recall within the 50-person capacity are retained as supporting evidence. A separate stratified 20% holdout check is also reported.

Local explanations use counterfactual feature replacement. Each actionable feature is replaced with its workforce median or mode, and the change in predicted risk is measured. This is a compact local contribution method, not causal evidence.

## Judge-ready answers

- **Why not accuracy?** Attrition is only 16.1%, so predicting “No” for everyone is 83.9% accurate while catching zero exits. The selected balanced logistic model is judged with ROC-AUC, average precision, and capacity metrics instead.
- **What was fit on train only?** The imputer, scaler, one-hot encoder, and model are inside one scikit-learn pipeline. Cross-validation fits that complete pipeline independently on each training fold. Validation rows never fit preprocessing.
- **Is overtime causal?** No. Overtime is associated with 30.5% historical attrition versus 10.4% without overtime in this dataset. A workload reset is an intervention hypothesis that must be tested and measured.
- **Why Top 50?** It converts scores into an HR capacity decision. The current out-of-fold Top 50 contains 44 historical exits: 88% precision, 18.6% recall, and 5.46× lift over the base rate.
- **Why logistic regression?** It is the honest competitive baseline here: ROC-AUC 0.821 and average precision 0.587. More complex candidates did not justify replacing it. AUC above 0.95 would prompt a leakage audit.
- **What was removed?** `EmployeeNumber` is retained only for reporting, never modeling. `EmployeeCount`, `StandardHours`, and `Over18` are constants and are excluded. Age, gender, and marital status are also excluded from the model as a prototype safeguard.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Authentication bootstrap

The first user who registers through the React login screen is automatically
assigned `org_admin` access to the `talentguard-demo` organization. The database
uses a serialized trigger so concurrent sign-ups cannot create multiple bootstrap
admins. Later users require an explicit `organization_members` assignment; RLS
continues to return no tenant data until that membership exists.

## Hosted database ingestion

There is no CSV upload route. `jobs/ingest_postgres.py` reads incrementally from an existing hosted PostgreSQL view using a read-only source account and writes immutable snapshots to Supabase. The source view must expose the snake_case employee fields listed in the job plus a monotonic ISO-8601 or zero-padded cursor.

```powershell
python -m pip install -r requirements-worker.txt
python -m jobs.ingest_postgres
python train.py
python -m jobs.publish_model_run --model-version 2026-10-10-v1 --snapshot-date 2026-10-10
```

The jobs require `SOURCE_DATABASE_URL`, `SOURCE_EMPLOYEE_VIEW`, `SOURCE_CURSOR_COLUMN`, `SUPABASE_URL`, and backend-only `SUPABASE_SECRET_KEY`. Never place the secret key in a `VITE_` variable.

## Deploy: Render + Vercel

Deploy the Flask API from the root `render.yaml`. Configure `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `CORS_ORIGINS` in Render.

Deploy `frontend/` to Vercel and configure:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`
- `VITE_API_BASE_URL` pointing at the Render URL
- `VITE_SITE_URL` set to the final Vercel production URL

Set Render `CORS_ORIGINS` to the exact Vercel production and preview origins you approve.
Enable Web Analytics in the Vercel project dashboard. The analytics component is
loaded only after the visitor accepts optional analytics, and query strings are
removed before an event is sent.

Generate and verify the committed outputs before deployment:

```powershell
python train.py
python -m unittest discover -s tests -v
node --check public\app.js
```

Then deploy the frontend preview and production version from `frontend/`:

```powershell
npx vercel
npx vercel --prod
```

The production React app never receives a secret/service-role key. Flask forwards each user access token to Supabase, which applies row-level security for the user's organization.

The Supabase publishable key is expected in the browser and is protected by RLS.
The Supabase secret key and hosted source database connection remain backend-only.
An automated test fails if backend secret markers appear in frontend source.

See `docs/HACKATHON_PLAYBOOK.md` for the three-minute pitch, live-demo sequence,
business value calculation, team handoffs, and judge-question answers.

## Important limitations

The supplied IBM dataset is synthetic, cross-sectional, and already contains historical outcomes. The watch list demonstrates the workflow and should not be used for live employment decisions. Model scores support relative ranking in this dataset and are not calibrated future probabilities.

Production use would require current pre-decision data, temporal validation, probability calibration, privacy and access controls, fairness testing, monitoring, employee-context review, and an approved human decision process. TalentGuard must never be used to automate adverse employment actions.
