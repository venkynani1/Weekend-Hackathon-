"""Tests for the business layer, agent, live scoring and launch checklist."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from agent import decide, load_queue
from app import create_app
from scoring import ScoringService, ValidationError, validate_profile
from services import DEFAULT_ARTIFACT_DIR, DEFAULT_OUTPUT_DIR, train_and_export

PAGES = ["/", "/insights", "/simulator", "/queue", "/privacy", "/terms"]


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: set[str] = set()
        self.assets: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href", "").startswith("/"):
            self.links.add(attrs["href"].split("#")[0])
        if tag in {"link", "script"}:
            ref = attrs.get("href") or attrs.get("src") or ""
            if ref.startswith("/"):
                self.assets.add(ref)


class LaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Work on a copy so approval tests never touch the committed outputs.
        cls.tmp = Path(tempfile.mkdtemp())
        if not (DEFAULT_OUTPUT_DIR / "action_queue.json").exists():
            train_and_export()
        shutil.copytree(DEFAULT_OUTPUT_DIR, cls.tmp / "output")
        cls.app = create_app({"TESTING": True, "AUTO_TRAIN": False, "OUTPUT_DIR": cls.tmp / "output",
                              "ARTIFACT_DIR": DEFAULT_ARTIFACT_DIR})
        cls.client = cls.app.test_client()
        cls.metrics = json.loads((DEFAULT_OUTPUT_DIR / "model_metrics.json").read_text())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- model evidence
    def test_model_beats_every_baseline(self):
        baselines = self.metrics["insights"]["baselines"]
        ml = next(b for b in baselines if b["kind"] == "ML (selected)")
        for other in baselines:
            if other is not ml:
                self.assertGreater(ml["average_precision"], other["average_precision"])
                self.assertGreaterEqual(ml["precision_at_50"], other["precision_at_50"])

    def test_no_leakage_signal(self):
        leakage = self.metrics["insights"]["leakage"]
        self.assertLess(leakage["max_single_auc"], 0.9)
        self.assertLess(leakage["model_auc"], 0.95)

    def test_traps_are_detected(self):
        eda = self.metrics["insights"]["eda"]
        self.assertEqual(set(eda["constant_columns"]), {"EmployeeCount", "Over18", "StandardHours"})
        self.assertAlmostEqual(eda["all_no_accuracy"], 1 - 237 / 1470, places=4)

    def test_watchlist_has_business_columns(self):
        import pandas as pd

        watch = pd.read_csv(DEFAULT_OUTPUT_DIR / "top_50_watchlist.csv")
        self.assertTrue(watch["LeaveProbability"].between(0, 1).all())
        self.assertTrue(watch["LeaveProbability"].is_monotonic_decreasing)
        self.assertTrue((watch["ValueAtRisk"] > 0).all())

    # ---------------------------------------------------------------- agent
    def test_every_draft_starts_pending_and_hides_score(self):
        queue = json.loads((DEFAULT_OUTPUT_DIR / "action_queue.json").read_text())
        self.assertEqual(len(queue), 50)
        for item in queue:
            self.assertEqual(item["status"], "PENDING_APPROVAL")
            self.assertNotRegex(item["invite_body"].lower(), r"risk|score|model|watch list|algorithm")

    def test_decision_needs_reviewer_and_is_audited(self):
        out = self.tmp / "output"
        with self.assertRaises(ValueError):
            decide(out, "TG-622", "APPROVED", " ")
        item = decide(out, "TG-622", "APPROVED", "Test Reviewer", "ok")
        self.assertEqual(item["status"], "APPROVED")
        self.assertEqual(item["history"][-1]["by"], "Test Reviewer")
        self.assertEqual(next(i for i in load_queue(out) if i["id"] == "TG-622")["status"], "APPROVED")

    # ---------------------------------------------------------------- scoring
    def test_validation_rejects_bad_profiles(self):
        good = ScoringService().profile_for(622)
        validate_profile(good)
        bad = {**good, "JobRole": "Sales Executive", "MonthlyIncome": -5, "YearsInCurrentRole": good["YearsAtCompany"] + 1}
        with self.assertRaises(ValidationError) as ctx:
            validate_profile(bad)
        self.assertIn("JobRole", ctx.exception.errors)
        self.assertIn("MonthlyIncome", ctx.exception.errors)

    def test_live_score_and_scenarios(self):
        scorer = ScoringService()
        result = scorer.score(validate_profile(scorer.profile_for(622)), 622)
        self.assertEqual(len(result["reasons"]), 3)
        self.assertTrue(0 <= result["leave_probability"] <= 1)
        removal = next(s for s in result["scenarios"] if s["label"] == "Remove regular overtime")
        self.assertLess(removal["new_leave_probability"], result["leave_probability"])

    def _csrf(self) -> str:
        html = self.client.get("/simulator").get_data(as_text=True)
        return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)

    def test_score_api_protections(self):
        token = self._csrf()
        profile = ScoringService().profile_for(622)
        ok = self.client.post("/api/score", json={"profile": profile}, headers={"X-CSRF-Token": token})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.post("/api/score", json={"profile": profile}, headers={"X-CSRF-Token": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/score", json={"profile": profile, "website": "http://spam"},
                                          headers={"X-CSRF-Token": token}).status_code, 400)
        bad = self.client.post("/api/score", json={"profile": {**profile, "OverTime": "Maybe"}}, headers={"X-CSRF-Token": token})
        self.assertEqual(bad.status_code, 422)
        self.assertIn("OverTime", bad.get_json()["fields"])

    # ---------------------------------------------------------------- launch checklist
    def test_pages_have_meta_and_one_h1(self):
        for path in PAGES:
            html = self.client.get(path).get_data(as_text=True)
            with self.subTest(path=path):
                self.assertRegex(html, r"<title>TalentGuard \| [^<]+</title>")
                self.assertRegex(html, r'<meta name="description" content="[^"]{50,}">')
                self.assertIn('property="og:image"', html)
                self.assertIn('rel="icon"', html)
                self.assertEqual(html.count("<h1"), 1)
                self.assertIn('href="/privacy"', html)
                self.assertIn('href="/terms"', html)
                self.assertIn('id="cookie-banner"', html)
                self.assertNotIn("\u2014", html)  # house style: no em dashes

    def test_no_broken_internal_links_or_assets(self):
        seen: set[str] = set()
        for path in PAGES:
            parser = LinkParser()
            parser.feed(self.client.get(path).get_data(as_text=True))
            for target in (parser.links | parser.assets) - seen:
                seen.add(target)
                response = self.client.get(target)
                with self.subTest(source=path, target=target):
                    self.assertEqual(response.status_code, 200)
                response.close()

    def test_custom_404_robots_sitemap_headers(self):
        missing = self.client.get("/definitely-not-here")
        self.assertEqual(missing.status_code, 404)
        self.assertIn("Back to the watch list", missing.get_data(as_text=True))
        self.assertIn("Sitemap:", self.client.get("/robots.txt").get_data(as_text=True))
        sitemap = self.client.get("/sitemap.xml").get_data(as_text=True)
        for path in ("/insights", "/privacy", "/terms"):
            self.assertIn(path + "</loc>", sitemap)
        headers = self.client.get("/").headers
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_no_secrets_in_repo_frontend(self):
        root = Path(__file__).resolve().parent.parent
        pattern = re.compile(r"(api[_-]?key|secret[_-]?key|password)\s*[:=]\s*['\"][^'\"]{8,}", re.I)
        for file in list((root / "static").rglob("*.js")) + list((root / "templates").rglob("*.html")) + [root / "app.py"]:
            with self.subTest(file=file.name):
                self.assertIsNone(pattern.search(file.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
