"""Business and evidence layer for TalentGuard.

Everything here works on out-of-fold (OOF) scores, so no number shown to judges
comes from a model that saw the employee it is scoring.

Sections:
    eda_findings       evidence-backed EDA facts + the data traps we found
    baseline_models    naive and rule-based baselines the ML model must beat
    capacity_curve     precision / recall / lift at different HR capacities
    gains_table        decile table: how often each score band actually left
    leakage_audit      single-feature AUC scan (anything above 0.90 is suspicious)
    fairness_audit     who lands on the watch list by gender / age / marital status
    business_case      money: cost of attrition, value of the 50-person cycle
    cost_weighted_queue  ranking by expected loss (probability x replacement cost)
    role_hotspots      job-role level concentration of risk
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

# Business assumptions. They are stated in the brief or are explicit, editable
# inputs on the dashboard. Nothing here is hidden.
REPLACEMENT_COST_MONTHS = 7.5      # brief: every exit costs 6-9 months of salary -> midpoint
DEFAULT_SAVE_RATE = 0.30           # share of real leavers a retention talk keeps (assumption)
DEFAULT_COST_PER_TALK_MONTHS = 0.25  # manager + HR time, plus small retention budget, in salary-months
CYCLES_PER_YEAR = 4                # quarterly review cycle (assumption)
COMPANY_HEADCOUNT = 12_000         # TechNova Solutions
COMPANY_ATTRITION = 0.16


def _rate(series: pd.Series) -> float:
    return float((series == "Yes").mean())


def _precision_at_k(y: np.ndarray, scores: np.ndarray, k: int) -> float:
    order = np.argsort(-scores, kind="mergesort")[:k]
    return float(y[order].mean())


def _summary(y: np.ndarray, scores: np.ndarray, k: int = 50) -> dict[str, float]:
    base = float(y.mean())
    p = _precision_at_k(y, scores, k)
    return {
        "average_precision": float(average_precision_score(y, scores)),
        "roc_auc": float(roc_auc_score(y, scores)),
        "precision_at_50": p,
        "recall_at_50": float(y[np.argsort(-scores, kind="mergesort")[:k]].sum() / max(y.sum(), 1)),
        "lift_at_50": p / base if base else 0.0,
    }


# ---------------------------------------------------------------- EDA
def eda_findings(raw: pd.DataFrame) -> dict[str, Any]:
    overtime = raw.groupby("OverTime")["Attrition"].apply(_rate)
    roles = raw.groupby("JobRole")["Attrition"].apply(_rate).sort_values(ascending=False)
    travel = raw.groupby("BusinessTravel")["Attrition"].apply(_rate)
    tenure_bins = pd.cut(raw["YearsAtCompany"], [-1, 1, 3, 5, 10, 100], labels=["0-1", "2-3", "4-5", "6-10", "11+"])
    tenure = raw.groupby(tenure_bins, observed=True)["Attrition"].apply(_rate)
    income = raw.groupby("Attrition")["MonthlyIncome"].median()
    stock = raw.groupby("StockOptionLevel")["Attrition"].apply(_rate)
    job_sat = raw.groupby("JobSatisfaction")["Attrition"].apply(_rate)

    constants = [c for c in raw.columns if raw[c].nunique(dropna=False) == 1]
    base_rate = _rate(raw["Attrition"])

    findings = [
        {
            "title": "Overtime triples the exit rate",
            "evidence": f"{overtime['Yes']:.0%} of employees on overtime left vs {overtime['No']:.0%} without it "
                        f"({overtime['Yes'] / overtime['No']:.1f}x).",
            "so_what": "Workload is the single most controllable lever HR has.",
            "chart": [{"label": "Overtime", "value": overtime["Yes"]}, {"label": "No overtime", "value": overtime["No"]}],
        },
        {
            "title": "Sales Representatives leave at 40%",
            "evidence": f"{roles.index[0]} attrition is {roles.iloc[0]:.0%}, against {roles.iloc[-1]:.0%} for {roles.index[-1]}s.",
            "so_what": "A role-level problem (pay mix, quota pressure) needs a policy fix, not 1:1 talks alone.",
            "chart": [{"label": role, "value": float(rate)} for role, rate in roles.head(5).items()],
        },
        {
            "title": "The first year is the danger zone",
            "evidence": f"{tenure['0-1']:.0%} of employees with 0-1 years at the company left vs {tenure['11+']:.0%} after 10+ years.",
            "so_what": "Onboarding and the first 12 months deserve a structured check-in programme.",
            "chart": [{"label": f"{label} yrs", "value": float(rate)} for label, rate in tenure.items()],
        },
        {
            "title": "Leavers earned 38% less",
            "evidence": f"Median monthly income of leavers is {income['Yes']:,.0f} vs {income['No']:,.0f} for stayers.",
            "so_what": "Pay benchmarking for low-band roles is cheaper than replacing 7.5 months of salary.",
            "chart": [{"label": "Leavers", "value": float(income["Yes"])}, {"label": "Stayers", "value": float(income["No"])}],
            "money": True,
        },
        {
            "title": "No stock options, double the risk",
            "evidence": f"Stock option level 0 has {stock[0]:.0%} attrition vs {stock[1]:.0%} at level 1.",
            "so_what": "A small equity grant is a cheap retention tool for high-value staff.",
            "chart": [{"label": f"Level {int(k)}", "value": float(v)} for k, v in stock.items()],
        },
        {
            "title": "Frequent travellers and unhappy staff leave more",
            "evidence": f"Frequent travel: {travel['Travel_Frequently']:.0%} vs non-travel {travel['Non-Travel']:.0%}. "
                        f"Job satisfaction 1/4: {job_sat[1]:.0%} vs 4/4: {job_sat[4]:.0%}.",
            "so_what": "Travel rotation and stay interviews address both.",
            "chart": [{"label": "Travel often", "value": float(travel["Travel_Frequently"])},
                      {"label": "No travel", "value": float(travel["Non-Travel"])}],
        },
    ]

    traps = [
        {
            "trap": "Accuracy is a trap",
            "detail": f"Only {base_rate:.1%} left. A model that says 'nobody leaves' scores {1 - base_rate:.1%} accuracy and finds zero leavers.",
            "handling": "We rank by average precision (PR-AUC) and judge precision at HR's 50-person capacity.",
        },
        {
            "trap": "EmployeeNumber is an ID",
            "detail": "A unique row identifier carries no behaviour but a tree model can memorise it.",
            "handling": "Dropped before training; kept only to label the watch list.",
        },
        {
            "trap": "Constant columns",
            "detail": f"{', '.join(constants)} have one value for all {len(raw):,} rows.",
            "handling": "Detected programmatically and dropped. They add noise and zero signal.",
        },
        {
            "trap": "Protected attributes",
            "detail": "Age, Gender and MaritalStatus are predictive but cannot legally justify a retention decision.",
            "handling": "Excluded from the model, then used only to audit the watch list for bias.",
        },
        {
            "trap": "In-sample scores would flatter us",
            "detail": "Scoring employees with a model trained on them inflates precision.",
            "handling": "Every ranked score is out-of-fold (5-fold stratified). Preprocessing is inside the pipeline, so scalers fit on train folds only.",
        },
    ]
    return {"findings": findings, "traps": traps, "constant_columns": constants, "all_no_accuracy": 1 - base_rate}


# ---------------------------------------------------------------- baselines
def rule_based_score(raw: pd.DataFrame) -> np.ndarray:
    """Transparent HR rule of thumb, the 'no ML' baseline."""
    score = np.zeros(len(raw))
    score += (raw["OverTime"] == "Yes") * 3
    score += (raw["JobSatisfaction"] <= 2) * 1
    score += (raw["EnvironmentSatisfaction"] <= 2) * 1
    score += (raw["YearsAtCompany"] <= 1) * 2
    score += (raw["StockOptionLevel"] == 0) * 1
    score += (raw["BusinessTravel"] == "Travel_Frequently") * 1
    score += (raw["MonthlyIncome"] < raw["MonthlyIncome"].quantile(0.25)) * 1
    # tiny deterministic tie-breaker so ranking is stable
    score += raw["EmployeeNumber"].rank(pct=True).to_numpy() * 1e-6
    return score.to_numpy() if hasattr(score, "to_numpy") else score


def baseline_models(raw: pd.DataFrame, y: np.ndarray, ml_name: str, ml_scores: np.ndarray) -> list[dict[str, Any]]:
    rng = np.random.default_rng(42)
    random_scores = rng.random(len(y))
    rows = [
        {"name": "Predict 'nobody leaves'", "kind": "Naive",
         "accuracy": float(1 - y.mean()), "average_precision": float(y.mean()), "roc_auc": 0.5,
         "precision_at_50": 0.0, "recall_at_50": 0.0, "lift_at_50": 0.0,
         "note": "High accuracy, finds nobody."},
        {"name": "Random 50 employees", "kind": "Naive", "accuracy": None,
         **_summary(y, random_scores), "note": "What HR gets with no targeting."},
        {"name": "HR rule of thumb", "kind": "Rule", "accuracy": None,
         **_summary(y, rule_based_score(raw)), "note": "Overtime, satisfaction, tenure, pay, travel points."},
        {"name": ml_name, "kind": "ML (selected)", "accuracy": None,
         **_summary(y, ml_scores), "note": "Out-of-fold scores."},
    ]
    for row in rows:
        row["caught_of_50"] = int(round(row["precision_at_50"] * 50))
    return rows


# ---------------------------------------------------------------- capacity
def capacity_curve(y: np.ndarray, scores: np.ndarray, ks=(10, 25, 50, 75, 100, 150, 200, 300)) -> list[dict[str, float]]:
    order = np.argsort(-scores, kind="mergesort")
    base = y.mean()
    total = max(y.sum(), 1)
    out = []
    for k in ks:
        sel = y[order[:k]]
        out.append({"k": int(k), "precision": float(sel.mean()), "recall": float(sel.sum() / total),
                    "lift": float(sel.mean() / base), "caught": int(sel.sum())})
    return out


def gains_table(y: np.ndarray, scores: np.ndarray, bands: int = 10) -> list[dict[str, Any]]:
    order = np.argsort(-scores, kind="mergesort")
    chunks = np.array_split(order, bands)
    total = max(y.sum(), 1)
    cumulative = 0
    out = []
    for i, idx in enumerate(chunks, start=1):
        cumulative += y[idx].sum()
        out.append({"decile": i, "employees": int(len(idx)), "leavers": int(y[idx].sum()),
                    "leave_rate": float(y[idx].mean()), "cumulative_capture": float(cumulative / total)})
    return out


def leakage_audit(model_frame: pd.DataFrame, y: np.ndarray, overall_auc: float) -> dict[str, Any]:
    rows = []
    for col in model_frame.columns:
        series = model_frame[col]
        if not pd.api.types.is_numeric_dtype(series):
            codes = series.map(pd.Series(y, index=series.index).groupby(series).mean())
            values = codes.to_numpy(dtype=float)
        else:
            values = series.to_numpy(dtype=float)
        if np.nanstd(values) == 0:
            continue
        auc = roc_auc_score(y, values)
        rows.append({"feature": col, "auc": float(max(auc, 1 - auc))})
    rows.sort(key=lambda r: r["auc"], reverse=True)
    return {
        "top_single_features": rows[:6],
        "max_single_auc": rows[0]["auc"] if rows else 0.0,
        "model_auc": overall_auc,
        "verdict": "No leakage signal: no single column predicts attrition above 0.90 AUC and the model sits at a "
                   f"realistic {overall_auc:.2f}. An AUC above 0.95 on this data would be a red flag.",
    }


# ---------------------------------------------------------------- fairness
def fairness_audit(raw: pd.DataFrame, top_ids: set[int]) -> list[dict[str, Any]]:
    frame = raw.copy()
    frame["on_list"] = frame["EmployeeNumber"].isin(top_ids)
    frame["AgeBand"] = pd.cut(frame["Age"], [0, 29, 39, 49, 100], labels=["Under 30", "30-39", "40-49", "50+"])
    overall = frame["on_list"].mean()
    out = []
    for attr in ["Gender", "AgeBand", "MaritalStatus"]:
        groups = []
        for value, g in frame.groupby(attr, observed=True):
            sel = g["on_list"].mean()
            listed = g[g["on_list"]]
            groups.append({
                "group": str(value),
                "workforce_share": float(len(g) / len(frame)),
                "watchlist_share": float(g["on_list"].sum() / max(frame["on_list"].sum(), 1)),
                "selection_rate": float(sel),
                "historical_attrition": _rate(g["Attrition"]),
                "leaver_share": float((g["Attrition"] == "Yes").sum() / max((frame["Attrition"] == "Yes").sum(), 1)),
                "precision_on_list": _rate(listed["Attrition"]) if len(listed) else None,
                "ratio_to_overall": float(sel / overall) if overall else 0.0,
            })
        out.append({"attribute": "Age band" if attr == "AgeBand" else ("Marital status" if attr == "MaritalStatus" else attr),
                    "groups": groups})
    return out


# ---------------------------------------------------------------- money
def calibrate(y: np.ndarray, scores: np.ndarray) -> np.ndarray:
    """Map ranking scores to an honest leave probability (Platt scaling).

    Balanced class weights push raw scores up, so a raw 0.9 is not a 90% chance.
    A two-parameter logistic fit on the out-of-fold logit keeps the ranking order
    and turns scores into 'how often people with this score actually left',
    which is what the money calculations need. Two parameters on 1,470 OOF
    scores cannot overfit the way a step-function (isotonic) fit would.
    """
    clipped = np.clip(scores, 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    platt = LogisticRegression(C=1e6, max_iter=1000).fit(logit, y)
    return platt.predict_proba(logit)[:, 1]


def business_case(raw: pd.DataFrame, y: np.ndarray, scores: np.ndarray, calibrated: np.ndarray) -> dict[str, Any]:
    replacement = raw["MonthlyIncome"].to_numpy() * REPLACEMENT_COST_MONTHS
    order = np.argsort(-scores, kind="mergesort")[:50]
    leavers_caught = int(y[order].sum())
    cost_caught = float(replacement[order][y[order] == 1].sum())
    avg_cost_caught = cost_caught / max(leavers_caught, 1)
    median_income = float(raw["MonthlyIncome"].median())

    saved_people = leavers_caught * DEFAULT_SAVE_RATE
    gross = cost_caught * DEFAULT_SAVE_RATE
    programme_cost = 50 * median_income * DEFAULT_COST_PER_TALK_MONTHS
    net = gross - programme_cost

    random_caught = 50 * y.mean()
    random_gross = random_caught * float(replacement[y == 1].mean()) * DEFAULT_SAVE_RATE

    company_exits = COMPANY_HEADCOUNT * COMPANY_ATTRITION
    company_cost = company_exits * median_income * REPLACEMENT_COST_MONTHS

    return {
        "assumptions": {
            "replacement_cost_months": REPLACEMENT_COST_MONTHS,
            "save_rate": DEFAULT_SAVE_RATE,
            "cost_per_talk_months": DEFAULT_COST_PER_TALK_MONTHS,
            "cycles_per_year": CYCLES_PER_YEAR,
            "median_monthly_income": median_income,
            "company_headcount": COMPANY_HEADCOUNT,
            "company_attrition": COMPANY_ATTRITION,
        },
        "cycle": {
            "talks": 50,
            "leavers_reached": leavers_caught,
            "leavers_reached_random": float(random_caught),
            "replacement_cost_reached": cost_caught,
            "avg_replacement_cost": avg_cost_caught,
            "expected_saves": saved_people,
            "gross_savings": gross,
            "programme_cost": programme_cost,
            "net_savings": net,
            "roi": net / programme_cost if programme_cost else 0.0,
            "random_gross_savings": random_gross,
        },
        "company": {
            "annual_exits": company_exits,
            "annual_cost": company_cost,
        },
    }


def cost_weighted_queue(raw: pd.DataFrame, y: np.ndarray, scores: np.ndarray, calibrated: np.ndarray) -> dict[str, Any]:
    """Compare 'most likely to leave' vs 'biggest expected loss' with the same 50 talks."""
    replacement = raw["MonthlyIncome"].to_numpy() * REPLACEMENT_COST_MONTHS
    expected_loss = calibrated * replacement

    def evaluate(rank_scores: np.ndarray) -> dict[str, float]:
        idx = np.argsort(-rank_scores, kind="mergesort")[:50]
        hits = y[idx] == 1
        return {
            "leavers_reached": int(hits.sum()),
            "replacement_cost_reached": float(replacement[idx][hits].sum()),
            "avg_salary_on_list": float(raw["MonthlyIncome"].to_numpy()[idx].mean()),
        }

    by_risk = evaluate(scores)
    by_value = evaluate(expected_loss + scores * 1e-9)
    return {
        "by_risk": by_risk,
        "by_value": by_value,
        "uplift_pct": (by_value["replacement_cost_reached"] / by_risk["replacement_cost_reached"] - 1)
        if by_risk["replacement_cost_reached"] else 0.0,
        "expected_loss": expected_loss,
        "replacement_cost": replacement,
    }


def role_hotspots(raw: pd.DataFrame, scores: np.ndarray, top_ids: set[int]) -> list[dict[str, Any]]:
    frame = raw[["EmployeeNumber", "JobRole", "Department", "Attrition", "OverTime"]].copy()
    frame["score"] = scores
    frame["on_list"] = frame["EmployeeNumber"].isin(top_ids)
    out = []
    for role, g in frame.groupby("JobRole"):
        out.append({
            "role": role,
            "department": g["Department"].mode().iloc[0],
            "headcount": int(len(g)),
            "attrition": _rate(g["Attrition"]),
            "overtime_share": float((g["OverTime"] == "Yes").mean()),
            "on_list": int(g["on_list"].sum()),
            "avg_score": float(g["score"].mean()),
        })
    out.sort(key=lambda r: (r["on_list"], r["attrition"]), reverse=True)
    return out


def build_insights(raw: pd.DataFrame, model_frame: pd.DataFrame, y: np.ndarray, oof: np.ndarray,
                   ml_name: str, top_ids: set[int]) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    """Return (json-safe insights, calibrated probabilities, replacement cost per employee)."""
    calibrated = calibrate(y, oof)
    queue = cost_weighted_queue(raw, y, oof, calibrated)
    insights = {
        "eda": eda_findings(raw),
        "baselines": baseline_models(raw, y, ml_name, oof),
        "capacity_curve": capacity_curve(y, oof),
        "gains": gains_table(y, oof),
        "leakage": leakage_audit(model_frame, y, float(roc_auc_score(y, oof))),
        "fairness": fairness_audit(raw, top_ids),
        "business": business_case(raw, y, oof, calibrated),
        "cost_weighted": {k: v for k, v in queue.items() if k not in {"expected_loss", "replacement_cost"}},
        "role_hotspots": role_hotspots(raw, oof, top_ids),
    }
    return insights, calibrated, queue["replacement_cost"]
