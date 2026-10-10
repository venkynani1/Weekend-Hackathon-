# TalentGuard

TalentGuard is a historical retention-risk prototype built from the IBM HR Employee Attrition dataset. It compares three classification pipelines, ranks the 50 records with the highest out-of-fold risk scores, explains three local risk drivers per employee, and creates a focused action plan for the first 10.

## What it produces

- Responsive Flask dashboard with search and filters
- Ranked Top-50 watch list
- Detailed Top-10 intervention plan
- Three employee-level risk reasons
- Model comparison and holdout evidence
- Department and common-driver summaries
- Downloadable CSV outputs

## What this branch adds (`2faced-winning`)

Built on top of the `2faced` base without changing its model or outputs contract.

| Rubric item | Where |
|---|---|
| T1 business framing: decision, capacity, money metric | Insights page, "Business framing" and "Business case" |
| T2 six evidence-backed findings + five data traps | `insights.py` `eda_findings`, Insights page |
| T3 naive + rule baselines, capacity curve, deciles, leakage audit, calibration | `insights.py`, Insights page |
| T4 watch list with leave probability, replacement cost and value at risk | `output/top_50_watchlist.csv` |
| T5 live prediction on stage + what-if interventions with net value | `/simulator`, `scoring.py` |
| Bonus: MLflow run comparison | `python train.py --mlflow`, `tracking.py` |
| Bonus: free public deployment | `streamlit_app.py` (Streamlit Cloud) and `render.yaml` (Flask on Render) |
| Bonus: agent drafts marked PENDING_APPROVAL with audit trail | `agent.py`, `/queue`, `output/action_queue.json` |

Beyond the brief:

- **Value mode**: ranking by expected loss (leave probability x replacement cost) reaches 32% more replacement cost with the same 50 talks. Shown next to the default headcount mode as a leadership choice.
- **Intervention ROI per employee**: the simulator ranks overtime removal, pay rise, stock grant, promotion, travel cut and internal move by risk reduction minus cost.
- **Bias audit** of the watch list by gender, age band and marital status (never used by the model).
- **Role hotspots**: where a whole role needs a policy fix rather than individual talks.
- **Causal test design**: randomised talk timing and a ranks 45 to 56 comparison to measure whether interventions work.
- Pitch script and judge Q&A: [`docs/PITCH.md`](docs/PITCH.md).

Website launch checklist: privacy policy (`/privacy`), terms (`/terms`), secrets only from environment (`.env.example`), cookie consent banner, per-page meta titles and descriptions, social preview image, favicon set and web manifest, `sitemap.xml` and `robots.txt`, alt text on charts, compressed images and gzip, mobile layouts, custom 404, link checker test, client and server form validation, CSRF token + honeypot + rate limiting, cookie-free first-party analytics plus optional GoatCounter after consent, security headers (CSP, frame, referrer).

## Run locally

From PowerShell in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python train.py
python app.py
```

Open `http://127.0.0.1:5000`.

The app automatically creates missing outputs on startup. Set `TALENTGUARD_AUTO_TRAIN=0` to disable that behavior.

Streamlit version:

```powershell
streamlit run streamlit_app.py
```

MLflow (optional, heavier install):

```powershell
python -m pip install -r requirements-dev.txt
python train.py --mlflow
mlflow ui --port 5001
```

Open `http://127.0.0.1:5001`, tick all runs under "TalentGuard attrition" and press Compare.

## Deploy for free

- **Streamlit Community Cloud**: share.streamlit.io, New app, pick this repo and branch, main file `streamlit_app.py`.
- **Render (Flask app)**: render.com, New, Blueprint, pick this repo. `render.yaml` sets the build, start command, health check and a generated secret key. Set `TALENTGUARD_SITE_URL` to the public URL so the sitemap and social preview use it.

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
- `output/model_metrics.json`
- `output/action_queue.json` (agent drafts, all PENDING_APPROVAL)
- `output/oof_scores.csv` (out-of-fold scores used for calibration and percentiles)
- `artifacts/talentguard_pipeline.joblib`

## Modeling approach

The pipeline excludes the target, employee identifier, constant columns, age, gender, and marital status. It adds transparent satisfaction and tenure-ratio features, one-hot encodes categorical columns, and standardizes numeric columns.

Three candidates are compared with five-fold stratified out-of-fold predictions:

1. Logistic regression
2. Random forest
3. Histogram gradient-boosted trees

The highest average precision wins. Precision, recall, F1, ROC-AUC, lift, and recall within the 50-person capacity are retained as supporting evidence. A separate stratified 20% holdout check is also reported.

Local explanations use counterfactual feature replacement. Each actionable feature is replaced with its workforce median or mode, and the change in predicted risk is measured. This is a compact local contribution method, not causal evidence.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Important limitations

The supplied IBM dataset is synthetic, cross-sectional, and already contains historical outcomes. The watch list demonstrates the workflow and should not be used for live employment decisions. Model scores support relative ranking in this dataset and are not calibrated future probabilities.

Production use would require current pre-decision data, temporal validation, probability calibration, privacy and access controls, fairness testing, monitoring, employee-context review, and an approved human decision process. TalentGuard must never be used to automate adverse employment actions.
