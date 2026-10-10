"""Publish generated TalentGuard model outputs to Supabase.

Run this only in a trusted Render job with SUPABASE_SECRET_KEY configured.
The secret key bypasses RLS and must never be copied into the frontend.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PublishError(RuntimeError):
    pass


class SupabaseAdminClient:
    def __init__(self, url: str, secret_key: str, timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.secret_key = secret_key
        self.timeout = timeout

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        query: dict[str, str] | None = None,
        body: Any = None,
        prefer: str | None = None,
        range_header: str | None = None,
    ) -> Any:
        endpoint = f"{self.url}/rest/v1/{path}"
        if query:
            endpoint = f"{endpoint}?{urlencode(query)}"
        headers = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
            "Accept": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        if range_header:
            headers["Range"] = range_header
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        try:
            with urlopen(Request(endpoint, data=data, headers=headers, method=method), timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise PublishError(f"Supabase returned HTTP {error.code}: {detail[:400]}") from error
        except (URLError, TimeoutError) as error:
            raise PublishError("Could not reach Supabase.") from error
        return json.loads(payload) if payload else None

    def all(self, table: str, query: dict[str, str], page_size: int = 1000) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self.request(table, query=query, range_header=f"{offset}-{offset + page_size - 1}") or []
            records.extend(page)
            if len(page) < page_size:
                return records
            offset += page_size


def chunks(records: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(records), size):
        yield records[index : index + size]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def build_score_records(
    scores: list[dict[str, str]],
    top_details: dict[int, dict[str, str]],
    snapshots: dict[int, int],
    organization_id: str,
    scoring_run_id: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    missing: list[int] = []
    for score in scores:
        employee_number = int(score["EmployeeNumber"])
        snapshot_id = snapshots.get(employee_number)
        if snapshot_id is None:
            missing.append(employee_number)
            continue
        detail = top_details.get(employee_number)
        features = detail["ReasonFeatures"].split(",") if detail else []
        explanations = []
        if detail:
            explanations = [
                {"feature": features[index] if index < len(features) else "", "explanation": detail[f"RiskReason{index + 1}"]}
                for index in range(3)
            ]
        records.append(
            {
                "organization_id": organization_id,
                "scoring_run_id": scoring_run_id,
                "employee_snapshot_id": snapshot_id,
                "source_employee_id": employee_number,
                "risk_probability": float(score["RiskScore"]),
                "risk_rank": int(score["Rank"]),
                "risk_band": score["RiskBand"],
                "explanations": explanations,
                "reason_features": features,
                "primary_action": detail["PrimaryAction"] if detail else None,
                "recommendation": detail["Recommendation"] if detail else None,
                "historical_outcome": score["HistoricalOutcome"] == "Yes",
            }
        )
    if missing:
        preview = ", ".join(str(item) for item in missing[:10])
        raise PublishError(f"No employee snapshot exists for {len(missing)} scored employees: {preview}")
    return records


def publish(args: argparse.Namespace) -> dict[str, Any]:
    url = os.environ.get("SUPABASE_URL", "").strip()
    secret_key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    if not url or not secret_key:
        raise PublishError("SUPABASE_URL and SUPABASE_SECRET_KEY are required.")
    client = SupabaseAdminClient(url, secret_key)

    organizations = client.request(
        "organizations",
        query={"select": "id", "slug": f"eq.{args.organization_slug}", "limit": "1"},
    )
    if not organizations:
        raise PublishError(f"Organization {args.organization_slug!r} does not exist.")
    organization_id = organizations[0]["id"]

    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    methodology = dict(metrics.get("methodology") or {})
    methodology["temporal_validation"] = metrics.get("temporal_validation") or {}
    model_payload = {
        "organization_id": organization_id,
        "name": metrics["selected_model"],
        "version": args.model_version,
        "status": "approved",
        "trained_at": args.trained_at,
        "metrics": metrics,
        "methodology": methodology,
        "fairness_report": metrics.get("fairness_report") or {},
        "calibration_report": metrics.get("calibration_report") or {},
        "artifact_uri": args.artifact_uri,
    }
    versions = client.request(
        "model_versions",
        method="POST",
        query={"on_conflict": "organization_id,name,version"},
        body=model_payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    model_version_id = versions[0]["id"]

    ingestion_runs = client.request(
        "ingestion_runs",
        query={
            "select": "id",
            "organization_id": f"eq.{organization_id}",
            "status": "eq.completed",
            "order": "completed_at.desc",
            "limit": "1",
        },
    )
    run_payload = {
        "organization_id": organization_id,
        "model_version_id": model_version_id,
        "ingestion_run_id": ingestion_runs[0]["id"] if ingestion_runs else None,
        "snapshot_date": args.snapshot_date,
        "status": "running",
        "records_scored": 0,
        "capacity": 50,
        "threshold": metrics["selected_model_score"]["capacity_threshold"],
        "metadata": {"publisher": "jobs/publish_model_run.py"},
    }
    scoring_run = client.request(
        "scoring_runs", method="POST", body=run_payload, prefer="return=representation"
    )[0]
    scoring_run_id = scoring_run["id"]

    try:
        snapshots = client.all(
            "employee_snapshots",
            {
                "select": "id,source_employee_id",
                "organization_id": f"eq.{organization_id}",
                "snapshot_date": f"eq.{args.snapshot_date}",
                "order": "source_employee_id.asc",
            },
        )
        snapshot_by_employee = {int(row["source_employee_id"]): int(row["id"]) for row in snapshots}
        all_scores = load_csv(args.all_scores)
        top = load_csv(args.watchlist)
        top_by_employee = {int(row["EmployeeNumber"]): row for row in top}
        records = build_score_records(
            all_scores,
            top_by_employee,
            snapshot_by_employee,
            organization_id,
            scoring_run_id,
        )
        for batch in chunks(records, 250):
            client.request("risk_scores", method="POST", body=batch, prefer="return=minimal")
        completed = client.request(
            "scoring_runs",
            method="PATCH",
            query={"id": f"eq.{scoring_run_id}"},
            body={"status": "completed", "records_scored": len(records), "completed_at": args.completed_at},
            prefer="return=representation",
        )[0]
    except Exception as error:
        client.request(
            "scoring_runs",
            method="PATCH",
            query={"id": f"eq.{scoring_run_id}"},
            body={"status": "failed", "error_summary": str(error)[:1000], "completed_at": args.completed_at},
            prefer="return=minimal",
        )
        raise
    return {"model_version_id": model_version_id, "scoring_run_id": completed["id"], "records_scored": len(records)}


def parse_args() -> argparse.Namespace:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    parser = argparse.ArgumentParser(description="Publish generated TalentGuard scores to Supabase.")
    parser.add_argument("--organization-slug", default="talentguard-demo")
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--trained-at", default=now)
    parser.add_argument("--completed-at", default=now)
    parser.add_argument("--artifact-uri", default="artifacts/talentguard_pipeline.joblib")
    parser.add_argument("--metrics", type=Path, default=PROJECT_ROOT / "output" / "model_metrics.json")
    parser.add_argument("--all-scores", type=Path, default=PROJECT_ROOT / "output" / "all_risk_scores.csv")
    parser.add_argument("--watchlist", type=Path, default=PROJECT_ROOT / "output" / "top_50_watchlist.csv")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        result = publish(parse_args())
    except PublishError as error:
        raise SystemExit(f"Publish failed: {error}") from error
    print(json.dumps(result, indent=2))
