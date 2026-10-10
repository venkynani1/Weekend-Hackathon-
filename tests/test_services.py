from __future__ import annotations

import unittest
import csv
import json

from services import (
    CONSTANT_COLUMNS,
    DEFAULT_DATASET,
    DEFAULT_OUTPUT_DIR,
    IDENTIFIER,
    SENSITIVE_COLUMNS,
    TARGET,
    build_model_frame,
    load_dataset,
    recommendation_for,
)
from models import RiskReason


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_dataset(DEFAULT_DATASET)
        cls.model_frame = build_model_frame(cls.raw)

    def test_dataset_contract(self):
        self.assertEqual(len(self.raw), 1470)
        self.assertEqual(self.raw[IDENTIFIER].nunique(), 1470)
        self.assertEqual(set(self.raw[TARGET].unique()), {"Yes", "No"})

    def test_model_frame_excludes_identifier_constants_and_sensitive_fields(self):
        excluded = {TARGET, IDENTIFIER, *CONSTANT_COLUMNS, *SENSITIVE_COLUMNS}
        self.assertTrue(excluded.isdisjoint(self.model_frame.columns))
        self.assertIn("AverageSatisfaction", self.model_frame.columns)
        self.assertIn("CareerStagnationRatio", self.model_frame.columns)

    def test_recommendation_uses_reason_categories(self):
        reasons = [
            RiskReason("OverTime", "Regular overtime", 0.2),
            RiskReason("MonthlyIncome", "Income below median", 0.1),
            RiskReason("JobSatisfaction", "Low satisfaction", 0.08),
        ]
        action, recommendation = recommendation_for(reasons, detailed=True)
        self.assertEqual(action, "Compensation review")
        self.assertIn("two weeks", recommendation)

    def test_governance_reports_and_all_score_export(self):
        with (DEFAULT_OUTPUT_DIR / "model_metrics.json").open(encoding="utf-8") as handle:
            metrics = json.load(handle)
        self.assertEqual(metrics["calibration_report"]["status"], "reported_not_recalibrated")
        self.assertGreater(metrics["calibration_report"]["brier_score"], 0)
        self.assertIn("Gender", metrics["fairness_report"]["attributes"])
        self.assertEqual(metrics["temporal_validation"]["status"], "unavailable")

        with (DEFAULT_OUTPUT_DIR / "all_risk_scores.csv").open(newline="", encoding="utf-8-sig") as handle:
            scores = list(csv.DictReader(handle))
        self.assertEqual(len(scores), 1470)
        self.assertEqual([int(row["Rank"]) for row in scores], list(range(1, 1471)))


if __name__ == "__main__":
    unittest.main()
