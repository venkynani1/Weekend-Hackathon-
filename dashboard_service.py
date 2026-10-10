"""Lightweight read-only dashboard data service for the deployed application.

This module intentionally uses only the Python standard library so the Vercel
function does not need pandas, numpy, joblib, or scikit-learn at runtime.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

INTEGER_FIELDS = {
    "Rank",
    "EmployeeNumber",
    "YearsAtCompany",
    "YearsInCurrentRole",
    "JobSatisfaction",
    "WorkLifeBalance",
}
FLOAT_FIELDS = {"RiskScore", "MonthlyIncome"}


def _coerce_record(record: dict[str, str]) -> dict[str, Any]:
    converted: dict[str, Any] = dict(record)
    for field in INTEGER_FIELDS:
        if field in converted and converted[field] != "":
            converted[field] = int(float(converted[field]))
    for field in FLOAT_FIELDS:
        if field in converted and converted[field] != "":
            converted[field] = float(converted[field])
    return converted


class DashboardService:
    """Load the precomputed hackathon outputs packaged with the deployment."""

    def __init__(self, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)

    @property
    def is_ready(self) -> bool:
        return (self.output_dir / "top_50_watchlist.csv").exists() and (
            self.output_dir / "model_metrics.json"
        ).exists()

    @lru_cache(maxsize=1)
    def load(self) -> dict[str, Any]:
        if not self.is_ready:
            raise FileNotFoundError(
                "Precomputed dashboard outputs are missing. Run `python train.py` locally before deployment."
            )

        with (self.output_dir / "top_50_watchlist.csv").open(
            newline="", encoding="utf-8-sig"
        ) as handle:
            watchlist = [_coerce_record(row) for row in csv.DictReader(handle)]

        with (self.output_dir / "model_metrics.json").open(encoding="utf-8") as handle:
            metrics = json.load(handle)

        return {
            "watchlist": watchlist,
            "top_ten": watchlist[:10],
            "metrics": metrics,
            "departments": sorted({row["Department"] for row in watchlist}),
        }

    def employee(self, employee_number: int) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in self.load()["watchlist"]
                if int(row["EmployeeNumber"]) == employee_number
            ),
            None,
        )

