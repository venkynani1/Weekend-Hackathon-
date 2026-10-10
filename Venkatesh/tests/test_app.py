from __future__ import annotations

import unittest

import pandas as pd

from app import create_app
from services import DEFAULT_OUTPUT_DIR, train_and_export


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DEFAULT_OUTPUT_DIR / "top_50_watchlist.csv").exists():
            train_and_export()
        cls.app = create_app({"TESTING": True, "AUTO_TRAIN": False})
        cls.client = cls.app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["outputs_ready"])

    def test_dashboard_and_api(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Top 50 watch list", response.data)
        api_response = self.client.get("/api/watchlist")
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(len(api_response.get_json()), 50)

    def test_generated_watchlist_contract(self):
        watchlist = pd.read_csv(DEFAULT_OUTPUT_DIR / "top_50_watchlist.csv")
        self.assertEqual(len(watchlist), 50)
        self.assertEqual(watchlist["Rank"].tolist(), list(range(1, 51)))
        self.assertTrue(watchlist[["RiskReason1", "RiskReason2", "RiskReason3"]].notna().all().all())
        self.assertTrue(watchlist["RiskScore"].is_monotonic_decreasing)

    def test_downloads(self):
        response = self.client.get("/downloads/watchlist.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        response.close()


if __name__ == "__main__":
    unittest.main()
