"""Training, scoring, explanations, and dashboard data services."""

from __future__ import annotations

import json
import os
import warnings
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
warnings.filterwarnings(
    "ignore",
    message=r"Could not find the number of physical cores.*",
    category=UserWarning,
    module=r"joblib\.externals\.loky\.backend\.context",
)

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from models import ModelScore, RiskReason


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = PROJECT_ROOT / "dataset" / "WA_Fn-UseC_-HR-Employee-Attrition.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts"

TARGET = "Attrition"
IDENTIFIER = "EmployeeNumber"
CONSTANT_COLUMNS = ["EmployeeCount", "Over18", "StandardHours"]
SENSITIVE_COLUMNS = ["Age", "Gender", "MaritalStatus"]
MODEL_EXCLUDED_COLUMNS = [TARGET, IDENTIFIER, *CONSTANT_COLUMNS, *SENSITIVE_COLUMNS]

ACTIONABLE_FEATURES = [
    "OverTime",
    "JobSatisfaction",
    "EnvironmentSatisfaction",
    "JobInvolvement",
    "WorkLifeBalance",
    "RelationshipSatisfaction",
    "MonthlyIncome",
    "StockOptionLevel",
    "YearsSinceLastPromotion",
    "YearsInCurrentRole",
    "YearsWithCurrManager",
    "TrainingTimesLastYear",
    "BusinessTravel",
    "DistanceFromHome",
    "YearsAtCompany",
    "TotalWorkingYears",
    "NumCompaniesWorked",
]


def load_dataset(path: str | Path = DEFAULT_DATASET) -> pd.DataFrame:
    """Load and validate the IBM HR dataset used by the project."""
    frame = pd.read_csv(path)
    required = {TARGET, IDENTIFIER, "Department", "JobRole", "OverTime"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Dataset contains no employee records.")
    if frame[IDENTIFIER].duplicated().any():
        raise ValueError("EmployeeNumber must be unique.")
    invalid_targets = set(frame[TARGET].dropna().unique()).difference({"Yes", "No"})
    if invalid_targets:
        raise ValueError(f"Unexpected Attrition values: {sorted(invalid_targets)}")
    return frame


def build_model_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Return leakage-aware model inputs plus a few transparent features."""
    frame = raw.drop(columns=[c for c in MODEL_EXCLUDED_COLUMNS if c in raw.columns]).copy()

    satisfaction_cols = [
        "EnvironmentSatisfaction",
        "JobSatisfaction",
        "RelationshipSatisfaction",
        "WorkLifeBalance",
    ]
    if all(col in frame for col in satisfaction_cols):
        frame["AverageSatisfaction"] = frame[satisfaction_cols].mean(axis=1)

    if {"YearsSinceLastPromotion", "YearsAtCompany"}.issubset(frame.columns):
        denominator = frame["YearsAtCompany"].clip(lower=1)
        frame["CareerStagnationRatio"] = frame["YearsSinceLastPromotion"] / denominator

    if {"YearsInCurrentRole", "YearsAtCompany"}.issubset(frame.columns):
        denominator = frame["YearsAtCompany"].clip(lower=1)
        frame["RoleTenureRatio"] = frame["YearsInCurrentRole"] / denominator

    return frame


def _preprocessor_for(frame: pd.DataFrame) -> ColumnTransformer:
    categorical = frame.select_dtypes(include=["object", "category"]).columns.tolist()
    numeric = [column for column in frame.columns if column not in categorical]

    numeric_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric_pipeline, numeric),
            ("categorical", categorical_pipeline, categorical),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def candidate_models(frame: pd.DataFrame) -> dict[str, Pipeline]:
    """Build intentionally small, diverse candidate set."""
    estimators = {
        "Logistic regression": LogisticRegression(
            C=0.6,
            class_weight="balanced",
            max_iter=3000,
            random_state=42,
        ),
        "Random forest": RandomForestClassifier(
            n_estimators=350,
            max_depth=8,
            min_samples_leaf=4,
            max_features="sqrt",
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=1,
        ),
        "Gradient boosted trees": HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_iter=220,
            max_leaf_nodes=15,
            min_samples_leaf=18,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=42,
        ),
    }
    return {
        name: Pipeline([("preprocess", deepcopy(_preprocessor_for(frame))), ("model", estimator)])
        for name, estimator in estimators.items()
    }


def _capacity_metrics(y_true: np.ndarray, probabilities: np.ndarray, capacity: int = 50) -> ModelScore:
    capacity = min(capacity, len(y_true))
    order = np.argsort(-probabilities)
    selected = order[:capacity]
    predicted = np.zeros(len(y_true), dtype=int)
    predicted[selected] = 1
    positives = max(int(np.sum(y_true)), 1)
    base_rate = float(np.mean(y_true))
    precision_at_k = float(np.mean(y_true[selected]))
    recall_at_k = float(np.sum(y_true[selected]) / positives)
    threshold = float(probabilities[selected[-1]])
    return ModelScore(
        name="",
        average_precision=float(average_precision_score(y_true, probabilities)),
        roc_auc=float(roc_auc_score(y_true, probabilities)),
        f1_at_capacity=float(f1_score(y_true, predicted, zero_division=0)),
        recall_at_capacity=float(recall_score(y_true, predicted, zero_division=0)),
        precision_at_50=precision_at_k,
        recall_at_50=recall_at_k,
        lift_at_50=float(precision_at_k / base_rate) if base_rate else 0.0,
        capacity_threshold=threshold,
    )


def evaluate_candidates(
    frame: pd.DataFrame,
    target: pd.Series,
    folds: int = 5,
) -> tuple[list[ModelScore], dict[str, np.ndarray], dict[str, Pipeline]]:
    """Compare models using out-of-fold probabilities for honest ranking metrics."""
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    models = candidate_models(frame)
    scores: list[ModelScore] = []
    predictions: dict[str, np.ndarray] = {}

    for name, pipeline in models.items():
        probabilities = cross_val_predict(
            pipeline,
            frame,
            target,
            cv=cv,
            method="predict_proba",
            n_jobs=1,
        )[:, 1]
        raw_score = _capacity_metrics(target.to_numpy(), probabilities, capacity=50)
        scores.append(ModelScore(name=name, **{k: v for k, v in raw_score.to_dict().items() if k != "name"}))
        predictions[name] = probabilities

    scores.sort(key=lambda score: (score.average_precision, score.precision_at_50), reverse=True)
    return scores, predictions, models


def _holdout_report(pipeline: Pipeline, frame: pd.DataFrame, target: pd.Series) -> dict[str, Any]:
    train_x, test_x, train_y, test_y = train_test_split(
        frame,
        target,
        test_size=0.2,
        stratify=target,
        random_state=42,
    )
    fitted = clone(pipeline).fit(train_x, train_y)
    probabilities = fitted.predict_proba(test_x)[:, 1]
    proportional_capacity = max(1, round(50 * len(test_y) / len(target)))
    summary = _capacity_metrics(test_y.to_numpy(), probabilities, proportional_capacity)
    order = np.argsort(-probabilities)
    selected = order[:proportional_capacity]
    predicted = np.zeros(len(test_y), dtype=int)
    predicted[selected] = 1
    matrix = confusion_matrix(test_y, predicted).tolist()
    return {
        "test_records": int(len(test_y)),
        "capacity": proportional_capacity,
        "average_precision": summary.average_precision,
        "roc_auc": summary.roc_auc,
        "precision_at_capacity": summary.precision_at_50,
        "recall_at_capacity": summary.recall_at_50,
        "lift_at_capacity": summary.lift_at_50,
        "confusion_matrix": matrix,
    }


def _baseline_values(raw: pd.DataFrame, features: Iterable[str]) -> dict[str, Any]:
    baselines: dict[str, Any] = {}
    for feature in features:
        if feature not in raw:
            continue
        if pd.api.types.is_numeric_dtype(raw[feature]):
            baselines[feature] = float(raw[feature].median())
        else:
            mode = raw[feature].mode(dropna=True)
            baselines[feature] = mode.iloc[0] if not mode.empty else ""
    return baselines


def _score_raw(pipeline: Pipeline, raw: pd.DataFrame) -> np.ndarray:
    return pipeline.predict_proba(build_model_frame(raw))[:, 1]


def _satisfaction_label(value: float) -> str:
    labels = {1: "low", 2: "below average", 3: "good", 4: "high"}
    return labels.get(int(value), f"{value:g}/4")


def explain_feature(feature: str, value: Any, baseline: Any) -> str:
    """Translate a model contribution into HR-readable, factual wording."""
    if feature == "OverTime":
        return "Regular overtime increases workload and burnout exposure" if value == "Yes" else "Workload pattern differs from lower-risk peers"
    if feature in {"JobSatisfaction", "EnvironmentSatisfaction", "JobInvolvement", "RelationshipSatisfaction", "WorkLifeBalance"}:
        label = _satisfaction_label(float(value))
        readable = {
            "JobSatisfaction": "Job satisfaction",
            "EnvironmentSatisfaction": "Work environment satisfaction",
            "JobInvolvement": "Job involvement",
            "RelationshipSatisfaction": "Workplace relationship satisfaction",
            "WorkLifeBalance": "Work-life balance",
        }[feature]
        return f"{readable} is {label} ({int(value)}/4)"
    if feature == "MonthlyIncome":
        relation = "below" if float(value) < float(baseline) else "different from"
        return f"Monthly income ({float(value):,.0f}) is {relation} the workforce median ({float(baseline):,.0f})"
    if feature == "StockOptionLevel":
        return f"Stock option level is {int(value)} compared with a workforce baseline of {int(float(baseline))}"
    if feature == "YearsSinceLastPromotion":
        return f"It has been {int(value)} years since the last promotion"
    if feature == "YearsInCurrentRole":
        return f"The employee has spent {int(value)} years in the current role"
    if feature == "YearsWithCurrManager":
        return f"The employee has worked {int(value)} years with the current manager"
    if feature == "TrainingTimesLastYear":
        return f"The employee completed {int(value)} training sessions last year"
    if feature == "BusinessTravel":
        label = str(value).replace("_", " ").lower()
        return f"Business travel pattern is {label}"
    if feature == "DistanceFromHome":
        return f"Commute distance is {int(value)} distance units"
    if feature == "YearsAtCompany":
        return f"Company tenure is {int(value)} years"
    if feature == "TotalWorkingYears":
        return f"Total career tenure is {int(value)} years"
    if feature == "NumCompaniesWorked":
        return f"The employee has worked at {int(value)} companies"
    return f"{feature} differs from the workforce baseline"


def employee_explanations(
    pipeline: Pipeline,
    all_raw: pd.DataFrame,
    selected_raw: pd.DataFrame,
    reason_count: int = 3,
) -> dict[int, list[RiskReason]]:
    """Estimate local risk drivers by replacing each feature with its baseline."""
    features = [feature for feature in ACTIONABLE_FEATURES if feature in all_raw.columns]
    baselines = _baseline_values(all_raw, features)
    base_probabilities = _score_raw(pipeline, selected_raw)
    contribution_by_feature: dict[str, np.ndarray] = {}

    for feature in features:
        counterfactual = selected_raw.copy()
        counterfactual[feature] = baselines[feature]
        contribution_by_feature[feature] = base_probabilities - _score_raw(pipeline, counterfactual)

    explanations: dict[int, list[RiskReason]] = {}
    for position, (_, row) in enumerate(selected_raw.iterrows()):
        candidates = sorted(
            ((feature, float(values[position])) for feature, values in contribution_by_feature.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        positive = [item for item in candidates if item[1] > 0.0001]
        chosen = (positive + [item for item in candidates if item not in positive])[:reason_count]
        employee_id = int(row[IDENTIFIER])
        explanations[employee_id] = [
            RiskReason(
                feature=feature,
                explanation=explain_feature(feature, row[feature], baselines[feature]),
                contribution=contribution,
            )
            for feature, contribution in chosen
        ]
    return explanations


def recommendation_for(reasons: list[RiskReason], detailed: bool = False) -> tuple[str, str]:
    features = {reason.feature for reason in reasons}
    actions: list[tuple[str, str]] = []

    if features.intersection({"MonthlyIncome", "StockOptionLevel"}):
        actions.append(("Compensation review", "Review pay positioning and total rewards against the role's internal band."))
    if features.intersection({"YearsSinceLastPromotion", "TrainingTimesLastYear", "JobInvolvement"}):
        actions.append(("Career progression plan", "Agree on a documented growth path, milestones, and a relevant development opportunity."))
    if "YearsInCurrentRole" in features:
        actions.append(("Role fit check-in", "Confirm role expectations, onboarding support, and whether the current assignment matches the employee's strengths."))
    if features.intersection({"OverTime", "WorkLifeBalance"}):
        actions.append(("Workload reset", "Review recurring overtime, rebalance near-term workload, and agree on sustainable working norms."))
    if features.intersection({"JobSatisfaction", "EnvironmentSatisfaction", "RelationshipSatisfaction", "YearsWithCurrManager"}):
        actions.append(("Manager stay interview", "Run a confidential stay interview and agree on two changes the manager can track."))
    if features.intersection({"BusinessTravel", "DistanceFromHome"}):
        actions.append(("Flexibility review", "Discuss travel expectations, scheduling, and feasible flexibility options."))
    if not actions:
        actions.append(("Stay interview", "Schedule a structured conversation to confirm the employee's priorities and concerns."))

    primary = actions[0][0]
    if detailed:
        selected = actions[:3]
        recommendation = " ".join(action for _, action in selected)
        recommendation += " Assign an HR partner and complete the first check-in within two weeks."
    else:
        recommendation = actions[0][1]
    return primary, recommendation


def _risk_band(rank: int) -> str:
    if rank <= 10:
        return "Priority"
    if rank <= 25:
        return "High"
    return "Elevated"


def _department_summary(raw: pd.DataFrame, oof_probabilities: np.ndarray, top_ids: set[int]) -> list[dict[str, Any]]:
    frame = raw[[IDENTIFIER, "Department", TARGET]].copy()
    frame["RiskScore"] = oof_probabilities
    frame["IsWatchlist"] = frame[IDENTIFIER].isin(top_ids)
    records = []
    for department, group in frame.groupby("Department"):
        records.append(
            {
                "department": department,
                "employees": int(len(group)),
                "historical_attrition_rate": float((group[TARGET] == "Yes").mean()),
                "average_risk": float(group["RiskScore"].mean()),
                "watchlist_count": int(group["IsWatchlist"].sum()),
            }
        )
    return sorted(records, key=lambda record: record["watchlist_count"], reverse=True)


def train_and_export(
    dataset_path: str | Path = DEFAULT_DATASET,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    """Run the full reproducible training workflow and write dashboard artifacts."""
    output_path = Path(output_dir)
    artifact_path = Path(artifact_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    artifact_path.mkdir(parents=True, exist_ok=True)

    raw = load_dataset(dataset_path)
    target = raw[TARGET].map({"No": 0, "Yes": 1}).astype(int)
    model_frame = build_model_frame(raw)
    scores, oof_predictions, candidates = evaluate_candidates(model_frame, target)
    selected_score = scores[0]
    selected_name = selected_score.name
    selected_pipeline = clone(candidates[selected_name])
    holdout = _holdout_report(selected_pipeline, model_frame, target)
    selected_pipeline.fit(model_frame, target)
    selected_oof = oof_predictions[selected_name]

    ranking = raw.copy()
    ranking["RiskScore"] = selected_oof
    ranking = ranking.sort_values(["RiskScore", IDENTIFIER], ascending=[False, True]).reset_index(drop=True)
    ranking["Rank"] = np.arange(1, len(ranking) + 1)
    top = ranking.head(50).copy()
    explanations = employee_explanations(selected_pipeline, raw, top)

    reason_features: list[str] = []
    reason_texts: list[list[str]] = []
    primary_actions: list[str] = []
    recommendations: list[str] = []
    for _, row in top.iterrows():
        employee_id = int(row[IDENTIFIER])
        reasons = explanations[employee_id]
        detailed = int(row["Rank"]) <= 10
        action, recommendation = recommendation_for(reasons, detailed=detailed)
        reason_features.append(",".join(reason.feature for reason in reasons))
        reason_texts.append([reason.explanation for reason in reasons])
        primary_actions.append(action)
        recommendations.append(recommendation)

    top["RiskBand"] = top["Rank"].map(_risk_band)
    top["ReasonFeatures"] = reason_features
    for index in range(3):
        top[f"RiskReason{index + 1}"] = [texts[index] for texts in reason_texts]
    top["PrimaryAction"] = primary_actions
    top["Recommendation"] = recommendations
    top["HistoricalOutcome"] = top[TARGET]

    watchlist_columns = [
        "Rank",
        IDENTIFIER,
        "RiskScore",
        "RiskBand",
        "Department",
        "JobRole",
        "YearsAtCompany",
        "YearsInCurrentRole",
        "OverTime",
        "JobSatisfaction",
        "WorkLifeBalance",
        "HistoricalOutcome",
        "RiskReason1",
        "RiskReason2",
        "RiskReason3",
        "ReasonFeatures",
        "PrimaryAction",
        "Recommendation",
    ]
    watchlist = top[watchlist_columns].copy()
    watchlist.to_csv(output_path / "top_50_watchlist.csv", index=False, float_format="%.6f")
    watchlist.head(10).to_csv(output_path / "top_10_action_plan.csv", index=False, float_format="%.6f")

    top_ids = set(top[IDENTIFIER].astype(int))
    department_summary = _department_summary(raw, selected_oof, top_ids)
    reason_counts = Counter(
        reason.feature
        for employee_reasons in explanations.values()
        for reason in employee_reasons
    )
    feature_label = {
        "OverTime": "Overtime",
        "JobSatisfaction": "Job satisfaction",
        "EnvironmentSatisfaction": "Environment satisfaction",
        "JobInvolvement": "Job involvement",
        "WorkLifeBalance": "Work-life balance",
        "RelationshipSatisfaction": "Relationship satisfaction",
        "MonthlyIncome": "Monthly income",
        "StockOptionLevel": "Stock options",
        "YearsSinceLastPromotion": "Time since promotion",
        "YearsInCurrentRole": "Time in current role",
        "YearsWithCurrManager": "Time with manager",
        "TrainingTimesLastYear": "Training frequency",
        "BusinessTravel": "Business travel",
        "DistanceFromHome": "Commute distance",
        "YearsAtCompany": "Company tenure",
        "TotalWorkingYears": "Career tenure",
        "NumCompaniesWorked": "Prior companies",
    }
    driver_summary = [
        {"feature": feature, "label": feature_label.get(feature, feature), "count": count}
        for feature, count in reason_counts.most_common(8)
    ]

    metrics = {
        "dataset": {
            "records": int(len(raw)),
            "columns": int(len(raw.columns)),
            "attrition_count": int(target.sum()),
            "attrition_rate": float(target.mean()),
            "missing_cells": int(raw.isna().sum().sum()),
        },
        "selected_model": selected_name,
        "selection_metric": "Five-fold out-of-fold average precision",
        "selected_model_score": selected_score.to_dict(),
        "candidate_scores": [score.to_dict() for score in scores],
        "holdout": holdout,
        "department_summary": department_summary,
        "driver_summary": driver_summary,
        "methodology": {
            "cross_validation_folds": 5,
            "capacity": 50,
            "priority_capacity": 10,
            "excluded_columns": MODEL_EXCLUDED_COLUMNS,
            "explanation_method": "Counterfactual feature replacement against workforce medians or modes",
            "scope": "Historical demonstration using the IBM HR attrition dataset",
        },
    }

    with (output_path / "model_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
    joblib.dump(selected_pipeline, artifact_path / "talentguard_pipeline.joblib")
    return metrics


class DashboardService:
    """Read generated outputs and expose presentation-ready records."""

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)

    @property
    def is_ready(self) -> bool:
        return (self.output_dir / "top_50_watchlist.csv").exists() and (self.output_dir / "model_metrics.json").exists()

    def load(self) -> dict[str, Any]:
        if not self.is_ready:
            raise FileNotFoundError("Dashboard outputs are missing. Run `python train.py` first.")
        watchlist = pd.read_csv(self.output_dir / "top_50_watchlist.csv")
        with (self.output_dir / "model_metrics.json").open(encoding="utf-8") as handle:
            metrics = json.load(handle)
        records = watchlist.to_dict(orient="records")
        return {
            "watchlist": records,
            "top_ten": records[:10],
            "metrics": metrics,
            "departments": sorted(watchlist["Department"].dropna().unique().tolist()),
        }

    def employee(self, employee_number: int) -> dict[str, Any] | None:
        data = self.load()
        return next((row for row in data["watchlist"] if int(row[IDENTIFIER]) == employee_number), None)

