from __future__ import annotations

import csv
import unittest

from app import create_app
from dashboard_service import DEFAULT_OUTPUT_DIR


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DEFAULT_OUTPUT_DIR / "top_50_watchlist.csv").exists():
            raise RuntimeError("Run `python train.py` before the dashboard tests.")
        cls.app = create_app({"TESTING": True})
        cls.client = cls.app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["outputs_ready"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_api_root_and_dashboard_endpoints(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json()["service"], "TalentGuard API")
        api_response = self.client.get("/api/watchlist")
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(len(api_response.get_json()), 50)
        dashboard_response = self.client.get("/api/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(len(dashboard_response.get_json()["top_ten"]), 10)

    def test_local_frontend_cors(self):
        response = self.client.get(
            "/api/dashboard", headers={"Origin": "http://127.0.0.1:5173"}
        )
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"],
            "http://127.0.0.1:5173",
        )

    def test_generated_watchlist_contract(self):
        with (DEFAULT_OUTPUT_DIR / "top_50_watchlist.csv").open(
            newline="", encoding="utf-8-sig"
        ) as handle:
            watchlist = list(csv.DictReader(handle))
        self.assertEqual(len(watchlist), 50)
        self.assertEqual([int(row["Rank"]) for row in watchlist], list(range(1, 51)))
        self.assertTrue(
            all(
                row["RiskReason1"] and row["RiskReason2"] and row["RiskReason3"]
                for row in watchlist
            )
        )
        self.assertTrue(all(row["MonthlyIncome"] for row in watchlist))
        scores = [float(row["RiskScore"]) for row in watchlist]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_legacy_frontend_assets_are_not_served(self):
        stylesheet = self.client.get("/style.css")
        self.assertEqual(stylesheet.status_code, 404)
        stylesheet.close()
        script = self.client.get("/app.js")
        self.assertEqual(script.status_code, 404)
        script.close()

    def test_downloads(self):
        response = self.client.get("/downloads/watchlist.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        response.close()

    def test_live_employee_lookup(self):
        with (DEFAULT_OUTPUT_DIR / "top_50_watchlist.csv").open(
            newline="", encoding="utf-8-sig"
        ) as handle:
            first_employee = int(next(csv.DictReader(handle))["EmployeeNumber"])
        response = self.client.get(f"/api/employees/{first_employee}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["EmployeeNumber"], first_employee)
        self.assertTrue(payload["RiskReason1"])
        self.assertTrue(payload["PrimaryAction"])

    def test_frontend_does_not_contain_backend_secret_markers(self):
        frontend = DEFAULT_OUTPUT_DIR.parent / "frontend"
        forbidden = ("sb_secret_", "SUPABASE_SECRET_KEY", "service_role")
        for path in frontend.rglob("*"):
            if not path.is_file() or "node_modules" in path.parts or "dist" in path.parts:
                continue
            if path.name == ".env.local" or path.suffix in {".jpg", ".png", ".ico"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                self.assertNotIn(marker, content, f"Frontend secret marker found in {path}")

    def test_frontend_theme_switch_is_persistent_and_available_before_render(self):
        frontend = DEFAULT_OUTPUT_DIR.parent / "frontend"
        index = (frontend / "index.html").read_text(encoding="utf-8")
        provider = (frontend / "src" / "theme" / "ThemeProvider.tsx").read_text(
            encoding="utf-8"
        )
        toggle = (frontend / "src" / "components" / "ThemeToggle.tsx").read_text(
            encoding="utf-8"
        )
        self.assertIn("talentguard-theme", index)
        self.assertIn("prefers-color-scheme: dark", index)
        self.assertIn("localStorage.setItem(STORAGE_KEY, theme)", provider)
        self.assertIn('role="switch"', toggle)
        self.assertIn("aria-checked={dark}", toggle)

    def test_supabase_mode_rejects_missing_session_before_upstream_call(self):
        remote_app = create_app(
            {
                "TESTING": True,
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
            }
        )
        client = remote_app.test_client()
        health = client.get("/health")
        self.assertEqual(health.get_json()["data_backend"], "supabase")
        response = client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401)
        self.assertIn("session", response.get_json()["error"].lower())

    def test_intervention_payload_is_validated_server_side(self):
        remote_app = create_app(
            {
                "TESTING": True,
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
            }
        )
        client = remote_app.test_client()
        response = client.post(
            "/api/interventions",
            json={"source_employee_id": 1, "status": "fire_employee"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.get_json()["error"].lower())


if __name__ == "__main__":
    unittest.main()
