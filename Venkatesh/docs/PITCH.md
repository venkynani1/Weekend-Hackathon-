# TalentGuard pitch kit

Three minutes, four speakers, one live prediction. If the team has three people, Speaker D's part goes to Speaker C.

## The numbers to memorise

| What | Number |
|---|---|
| Employees / leavers in data | 1,470 / 237 (16.1%) |
| Accuracy of "nobody leaves" | 83.9%, finds 0 leavers |
| Real leavers in our top 50 | **44** (precision 88%, lift 5.5x) |
| Random 50 / HR rule of thumb | 8 / 39 |
| PR-AUC / ROC-AUC (out-of-fold) | 0.587 / 0.821 |
| Net savings per 50-talk cycle | about $285k (save rate 30%, 7.5 months per exit) |
| Per year (4 cycles) | about $1.1M |
| Value mode vs headcount mode | +32% replacement cost reached, half the people |
| TechNova attrition bill | about $71M a year |

## Script (3:00)

**Speaker A, 0:00 to 0:40. The problem and the decision.**
"TechNova loses 16% of 12,000 people a year. Every exit costs six to nine months of salary: about 71 million dollars a year. HR can hold 50 retention conversations per cycle. So the real question is not 'who will leave', it is: which 50 people get one of those conversations? Our success metric is replacement cost avoided per cycle. Accuracy is useless here: a model that says nobody leaves is 84% accurate and saves nobody."

**Speaker B, 0:40 to 1:20. Data and model.**
"We found four traps: an ID column, three constant columns, the accuracy trap, and protected attributes. We dropped age, gender and marital status from the model and used them only to audit it. Every score is out-of-fold, so no employee is scored by a model that saw them. We compared against two baselines: a random list catches 8 leavers, a hand-written HR rule catches 39. Our class-weighted logistic regression catches 44 of 50. It also beat random forest and gradient boosting, so we kept the simple model, and we can explain every coefficient."

**Speaker C, 1:20 to 2:20. Live demo.** (Open the Live scoring page before the pitch starts.)
1. "This is employee 622, rank 1: a lab technician, first year, on overtime. 93% chance of leaving, and here are the three reasons." Press **Score this employee**.
2. "Now the what-if table. Removing overtime drops the risk 17 points and pays for itself. A 10% raise does almost nothing for this person. That is money HR would have wasted."
3. Change **Overtime** to *No*, press score again, show the new number.
4. Switch to **Approval queue**: "The agent already drafted a manager brief and a neutral invite. It never mentions a score. It stays PENDING_APPROVAL until a named reviewer approves it, and every decision is logged."

**Speaker D, 2:20 to 3:00. Business value and close.**
"One cycle of 50 conversations reaches 44 real leavers. If talks keep 30% of them, that is about 285 thousand dollars net per cycle, 1.1 million a year, a 4.6x return on HR time. And leadership can switch to value mode, which protects 32% more replacement cost by focusing on expensive knowledge. We also tell you what we do not know: overtime is predictive, not proven causal, so we built in a randomised timing test to measure it. TalentGuard: the right 50 conversations, with the reason and the script ready."

## Judge questions

**Why not accuracy?** 84% of people stay. Predicting "nobody leaves" scores 84% and is worthless. We use PR-AUC to choose the model and precision at 50 because HR has 50 slots.

**What did you fit on train only?** Everything. Scaling, one-hot encoding and imputation live inside the scikit-learn Pipeline, so `cross_val_predict` refits them inside each training fold. The final watch list uses those out-of-fold scores. The calibration step (Platt scaling, two parameters) is also fitted on out-of-fold scores.

**Is OverTime causal?** No claim. It is a strong predictor (30% vs 10% attrition). To prove it we propose randomising the timing of the talks inside the 50 (weeks 1 vs 6) and comparing 90-day exits, plus comparing ranks 45 to 50 with 51 to 56.

**Your AUC is 0.82. Why not higher?** Above 0.95 on this dataset is a leakage red flag. Our leakage audit shows no single column above 0.68 AUC.

**Why did logistic beat boosting?** 1,470 rows with 237 positives is small. Regularised linear models generalise better there; the trees overfit. The brief says honest teams admit the baseline is competitive.

**Why is the score 93% and not 99%?** Class weighting inflates raw scores. We calibrate them with Platt scaling on out-of-fold data so the number means "how often people with this score actually left".

**How are the three reasons computed?** For each actionable feature we replace the employee's value with the company median (or most common value) and measure how much the score drops. The three biggest drops are the reasons. It is local and model-agnostic, like a simple SHAP.

**Is this fair?** The model never sees age, gender or marital status. The audit shows gender is balanced; under-30 and single employees are over-represented beyond their share of real leavers because tenure and stock options act as proxies. We flag that for reviewers rather than hide it.

**What stops misuse?** No automated decisions, approval gate, audit trail, neutral invites, terms of use that ban adverse actions, protected attributes excluded.

**Why 7.5 months and 30% save rate?** 7.5 is the midpoint of the brief's 6 to 9 months. 30% is an assumption, and the calculator on the Insights page shows the result at any value; it still pays at 10%.

## Who explains which file

| File | What it does | Owner |
|---|---|---|
| `services.py` | Load data, drop traps, pipelines, 5-fold out-of-fold comparison, top 50, reasons, actions | B |
| `insights.py` | EDA findings, baselines, capacity curve, leakage and bias audit, calibration, money | B / D |
| `scoring.py` | Validation, live scoring, what-if interventions | C |
| `agent.py` | Rule-based drafts, PENDING_APPROVAL, audit trail | C |
| `app.py` | Flask routes, CSRF, honeypot, rate limit, security headers, sitemap | A |
| `tracking.py` | MLflow runs for every model and baseline | B |
| `streamlit_app.py` | Streamlit Community Cloud version | A |

## Before going on stage

- `python train.py --mlflow`, then `mlflow ui --port 5001`, select all runs, press **Compare**, take a screenshot.
- Open the deployed URL on the presenting laptop and on one phone.
- Load `/simulator` and `/queue` in two tabs.
- Reset any test approvals: `python train.py` regenerates a clean queue.
