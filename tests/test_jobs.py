from __future__ import annotations

import unittest

from jobs.ingest_postgres import SNAPSHOT_FIELDS, normalize_record
from jobs.publish_model_run import build_score_records


class BackgroundJobTests(unittest.TestCase):
    def test_ingestion_normalizes_boolean_source_values(self):
        source = {field: 1 for field in SNAPSHOT_FIELDS}
        source.update(
            {
                "source_employee_id": 42,
                "attrition": None,
                "over_time": "Yes",
                "business_travel": "Travel_Rarely",
                "department": "Sales",
                "education_field": "Marketing",
                "gender": "Female",
                "job_role": "Sales Executive",
                "marital_status": "Single",
                "over_18": "Y",
            }
        )
        record = normalize_record(source, "org", "run", "2026-10-10")
        self.assertIsNone(record["attrition"])
        self.assertTrue(record["over_time"])
        self.assertEqual(record["snapshot_date"], "2026-10-10")

    def test_score_publisher_requires_a_matching_snapshot(self):
        scores = [{
            "EmployeeNumber": "42",
            "RiskScore": "0.75",
            "Rank": "1",
            "RiskBand": "Priority",
            "HistoricalOutcome": "Yes",
        }]
        details = {42: {
            "ReasonFeatures": "OverTime,JobSatisfaction,MonthlyIncome",
            "RiskReason1": "Overtime signal",
            "RiskReason2": "Satisfaction signal",
            "RiskReason3": "Income signal",
            "PrimaryAction": "Manager review",
            "Recommendation": "Review context.",
        }}
        records = build_score_records(scores, details, {42: 99}, "org", "run")
        self.assertEqual(records[0]["employee_snapshot_id"], 99)
        self.assertEqual(len(records[0]["explanations"]), 3)


if __name__ == "__main__":
    unittest.main()
