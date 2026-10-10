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
