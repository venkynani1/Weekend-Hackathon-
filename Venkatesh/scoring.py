"""Live scoring and what-if intervention simulator.

Used on stage: pick an employee (or type a new profile), score it with the
trained pipeline, see the top-3 reasons, then see which intervention moves the
risk most and whether it pays for itself.

Important caveat we say out loud: a score drop under a what-if change is model
sensitivity, not proof the change causes retention. Proving that needs the
randomised hold-out test described on the Insights page.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from insights import REPLACEMENT_COST_MONTHS
from services import (
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_DATASET,
    DEFAULT_OUTPUT_DIR,
    IDENTIFIER,
    employee_explanations,
    load_dataset,
    recommendation_for,
    train_and_export,
)

INT_FIELDS = {
    # field: (min, max)
    "MonthlyIncome": (1000, 25000),
    "JobLevel": (1, 5),
    "StockOptionLevel": (0, 3),
    "JobSatisfaction": (1, 4),
    "EnvironmentSatisfaction": (1, 4),
    "WorkLifeBalance": (1, 4),
    "JobInvolvement": (1, 4),
    "RelationshipSatisfaction": (1, 4),
    "YearsAtCompany": (0, 40),
    "YearsInCurrentRole": (0, 40),
    "YearsSinceLastPromotion": (0, 40),
    "YearsWithCurrManager": (0, 40),
    "TotalWorkingYears": (0, 45),
    "NumCompaniesWorked": (0, 9),
    "DistanceFromHome": (1, 29),
    "TrainingTimesLastYear": (0, 6),
}
CHOICE_FIELDS = {
    "OverTime": ["No", "Yes"],
    "BusinessTravel": ["Non-Travel", "Travel_Rarely", "Travel_Frequently"],
}
ROLES_BY_DEPARTMENT = {
    "Human Resources": ["Human Resources", "Manager"],
    "Research & Development": [
        "Research Scientist", "Laboratory Technician", "Manufacturing Director",
        "Healthcare Representative", "Research Director", "Manager",
    ],
    "Sales": ["Sales Executive", "Sales Representative", "Manager"],
}
FIELD_LABELS = {
    "Department": "Department", "JobRole": "Job role", "OverTime": "Overtime",
    "BusinessTravel": "Business travel", "MonthlyIncome": "Monthly income",
    "JobLevel": "Job level", "StockOptionLevel": "Stock option level",
    "JobSatisfaction": "Job satisfaction", "EnvironmentSatisfaction": "Environment satisfaction",
    "WorkLifeBalance": "Work-life balance", "JobInvolvement": "Job involvement",
    "RelationshipSatisfaction": "Relationship satisfaction", "YearsAtCompany": "Years at company",
    "YearsInCurrentRole": "Years in current role", "YearsSinceLastPromotion": "Years since promotion",
    "YearsWithCurrManager": "Years with manager", "TotalWorkingYears": "Total working years",
    "NumCompaniesWorked": "Companies worked", "DistanceFromHome": "Distance from home",
    "TrainingTimesLastYear": "Trainings last year",
}
EDITABLE_FIELDS = ["Department", "JobRole", *CHOICE_FIELDS, *INT_FIELDS]


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def validate_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Server-side validation. Never trust the browser."""
    errors: dict[str, str] = {}
    clean: dict[str, Any] = {}

    department = str(payload.get("Department", "")).strip()
    if department not in ROLES_BY_DEPARTMENT:
        errors["Department"] = "Choose a valid department."
    clean["Department"] = department

    role = str(payload.get("JobRole", "")).strip()
    if department in ROLES_BY_DEPARTMENT and role not in ROLES_BY_DEPARTMENT[department]:
        errors["JobRole"] = f"{role or 'This role'} does not exist in {department}."
    clean["JobRole"] = role

    for field, options in CHOICE_FIELDS.items():
        value = str(payload.get(field, "")).strip()
        if value not in options:
            errors[field] = "Choose one of the listed options."
        clean[field] = value

    for field, (low, high) in INT_FIELDS.items():
        raw_value = payload.get(field, "")
        try:
            number = float(raw_value)
            if not number.is_integer():
                raise ValueError
            number = int(number)
        except (TypeError, ValueError):
            errors[field] = "Enter a whole number."
            continue
        if not low <= number <= high:
            errors[field] = f"Must be between {low:,} and {high:,}."
            continue
        clean[field] = number

    # Cross-field logic: tenure numbers must be consistent with each other.
    if not errors:
        years = clean["YearsAtCompany"]
        for field in ("YearsInCurrentRole", "YearsSinceLastPromotion", "YearsWithCurrManager"):
            if clean[field] > years:
                errors[field] = "Cannot be more than years at company."
        if years > clean["TotalWorkingYears"]:
            errors["TotalWorkingYears"] = "Cannot be less than years at company."

    if errors:
        raise ValidationError(errors)
    return clean


class ScoringService:
    def __init__(
        self,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
        artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
        dataset: str | Path = DEFAULT_DATASET,
    ):
        self.output_dir = Path(output_dir)
        self.artifact_dir = Path(artifact_dir)
        self.dataset = Path(dataset)
        self._pipeline = None
        self._raw: pd.DataFrame | None = None
        self._oof: pd.DataFrame | None = None

    def _ensure(self) -> None:
        if self._pipeline is not None:
            return
        model_path = self.artifact_dir / "talentguard_pipeline.joblib"
        oof_path = self.output_dir / "oof_scores.csv"
        if not model_path.exists() or not oof_path.exists():
            train_and_export(self.dataset, self.output_dir, self.artifact_dir)
        self._pipeline = joblib.load(model_path)
        self._raw = load_dataset(self.dataset)
        self._oof = pd.read_csv(oof_path).sort_values("RiskScore").reset_index(drop=True)

    @property
    def raw(self) -> pd.DataFrame:
        self._ensure()
        return self._raw  # type: ignore[return-value]

    def employee_ids(self) -> list[int]:
        return sorted(self.raw[IDENTIFIER].astype(int).tolist())

    def profile_for(self, employee_number: int) -> dict[str, Any] | None:
        match = self.raw[self.raw[IDENTIFIER] == employee_number]
        if match.empty:
            return None
        row = match.iloc[0]
        return {field: (row[field].item() if hasattr(row[field], "item") else row[field]) for field in EDITABLE_FIELDS}

    def _template_row(self, employee_number: int | None) -> pd.Series:
        raw = self.raw
        if employee_number is not None:
            match = raw[raw[IDENTIFIER] == employee_number]
            if not match.empty:
                return match.iloc[0].copy()
        # New profile: start from a typical employee, then overwrite edited fields.
        row = raw.iloc[0].copy()
        for column in raw.columns:
            if pd.api.types.is_numeric_dtype(raw[column]):
                row[column] = raw[column].median()
            else:
                row[column] = raw[column].mode().iloc[0]
        row[IDENTIFIER] = 0
        return row

    def _calibrate(self, score: float) -> tuple[float, float]:
        oof = self._oof
        assert oof is not None
        probability = float(np.interp(score, oof["RiskScore"], oof["LeaveProbability"]))
        percentile = float(np.searchsorted(oof["RiskScore"].to_numpy(), score) / len(oof))
        return probability, percentile

    def _score_frame(self, frame: pd.DataFrame) -> np.ndarray:
        from services import build_model_frame

        return self._pipeline.predict_proba(build_model_frame(frame))[:, 1]  # type: ignore[union-attr]

    def score(self, profile: dict[str, Any], employee_number: int | None = None) -> dict[str, Any]:
        self._ensure()
        row = self._template_row(employee_number)
        for field, value in profile.items():
            row[field] = value
        frame = pd.DataFrame([row])
        frame[IDENTIFIER] = int(row[IDENTIFIER])
        score = float(self._score_frame(frame)[0])
        probability, percentile = self._calibrate(score)
        replacement = float(row["MonthlyIncome"]) * REPLACEMENT_COST_MONTHS

        reasons = employee_explanations(self._pipeline, self.raw, frame)[int(row[IDENTIFIER])]
        action, recommendation = recommendation_for(reasons, detailed=True)

        return {
            "risk_score": score,
            "leave_probability": probability,
            "percentile": percentile,
            "would_make_top_50": percentile >= 1 - 50 / len(self.raw),
            "replacement_cost": replacement,
            "expected_loss": probability * replacement,
            "reasons": [r.explanation for r in reasons],
            "primary_action": action,
            "recommendation": recommendation,
            "scenarios": self._scenarios(row, score, probability, replacement),
        }

    def _scenarios(self, row: pd.Series, score: float, probability: float, replacement: float) -> list[dict[str, Any]]:
        income = float(row["MonthlyIncome"])
        options: list[tuple[str, dict[str, Any], float, str]] = []
        if row["OverTime"] == "Yes":
            options.append(("Remove regular overtime", {"OverTime": "No"}, income * 0.5,
                            "Backfill or redistribution, about half a month of salary"))
        options.append(("Raise pay by 10%", {"MonthlyIncome": int(income * 1.10)}, income * 0.10 * 12,
                        "10% of annual salary"))
        if int(row["StockOptionLevel"]) == 0:
            options.append(("Grant stock option level 1", {"StockOptionLevel": 1}, income * 1.0,
                            "About one month of salary in equity"))
        if int(row["YearsSinceLastPromotion"]) >= 2 and int(row["JobLevel"]) < 5:
            options.append(("Promote one level", {"YearsSinceLastPromotion": 0, "JobLevel": int(row["JobLevel"]) + 1,
                                                  "MonthlyIncome": int(income * 1.15)}, income * 0.15 * 12,
                            "15% of annual salary"))
        if row["BusinessTravel"] == "Travel_Frequently":
            options.append(("Cut travel to occasional", {"BusinessTravel": "Travel_Rarely"}, 0.0,
                            "No direct cost, possible client impact"))
        if int(row["YearsInCurrentRole"]) >= 4:
            options.append(("Internal move to a new role", {"YearsInCurrentRole": 0, "YearsWithCurrManager": 0},
                            income * 0.25, "Onboarding time, about a week of salary"))

        if not options:
            return []
        frames = []
        for _, changes, _, _ in options:
            changed = row.copy()
            for key, value in changes.items():
                changed[key] = value
            frames.append(changed)
        batch = pd.DataFrame(frames)
        new_scores = self._score_frame(batch)

        results = []
        for (label, changes, cost, cost_note), new_score in zip(options, new_scores):
            new_probability, _ = self._calibrate(float(new_score))
            avoided = (probability - new_probability) * replacement
            results.append({
                "label": label,
                "changes": {FIELD_LABELS.get(k, k): v for k, v in changes.items()},
                "new_risk_score": float(new_score),
                "new_leave_probability": new_probability,
                "risk_change_points": (new_probability - probability) * 100,
                "cost": cost,
                "cost_note": cost_note,
                "expected_loss_avoided": avoided,
                "net_value": avoided - cost,
            })
        results.sort(key=lambda r: r["net_value"], reverse=True)
        return results
