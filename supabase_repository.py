"""Supabase-backed data access for the authenticated TalentGuard API.

The browser supplies a Supabase access token. The backend forwards that token
with the publishable key, so Postgres row-level security remains the source of
truth for tenant authorization. Elevated keys are reserved for offline
ingestion and scoring jobs and are never used by request handlers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SupabaseAPIError(RuntimeError):
    """A sanitized upstream Supabase error."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class AuthenticationRequired(SupabaseAPIError):
    def __init__(self, message: str = "A valid Supabase session is required."):
        super().__init__(message, 401)


class OrganizationAccessRequired(SupabaseAPIError):
    def __init__(self):
        super().__init__("This account has not been assigned to an organization.", 403)


class ScoringRunUnavailable(SupabaseAPIError):
    def __init__(self):
        super().__init__("No completed scoring run is available for this organization.", 503)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str | None
    organization_id: str
    role: str


class SupabaseRepository:
    """Small PostgREST/Auth client that preserves end-user RLS semantics."""

    def __init__(self, url: str, publishable_key: str, timeout: float = 12.0):
        self.url = url.rstrip("/")
        self.publishable_key = publishable_key
        self.timeout = timeout

    def _request(
        self,
        path: str,
        *,
        token: str,
        method: str = "GET",
        query: dict[str, str] | None = None,
        body: dict[str, Any] | list[dict[str, Any]] | None = None,
        prefer: str | None = None,
    ) -> Any:
        if not token:
            raise AuthenticationRequired()
        endpoint = f"{self.url}{path}"
        if query:
            endpoint = f"{endpoint}?{urlencode(query)}"
        headers = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer

        request = Request(endpoint, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                details = json.loads(raw)
                message = details.get("message") or details.get("msg") or "Supabase request failed."
            except json.JSONDecodeError:
                message = "Supabase request failed."
            if error.code == 401:
                raise AuthenticationRequired() from error
            if error.code == 403:
                raise SupabaseAPIError("You do not have permission to perform this action.", 403) from error
            raise SupabaseAPIError(message, error.code) from error
        except (URLError, TimeoutError) as error:
            raise SupabaseAPIError("Supabase is temporarily unavailable.", 503) from error

        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as error:
            raise SupabaseAPIError("Supabase returned an invalid response.") from error

    def auth_context(self, token: str) -> AuthContext:
        user = self._request("/auth/v1/user", token=token)
        user_id = user.get("id") if isinstance(user, dict) else None
        if not user_id:
            raise AuthenticationRequired()

        memberships = self._request(
            "/rest/v1/organization_members",
            token=token,
            query={
                "select": "organization_id,role",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if not memberships:
            raise OrganizationAccessRequired()
        membership = memberships[0]
        return AuthContext(
            user_id=user_id,
            email=user.get("email"),
            organization_id=membership["organization_id"],
            role=membership["role"],
        )

    def session(self, token: str) -> dict[str, Any]:
        context = self.auth_context(token)
        organizations = self._request(
            "/rest/v1/organizations",
            token=token,
            query={
                "select": "id,name,slug",
                "id": f"eq.{context.organization_id}",
                "limit": "1",
            },
        )
        organization = organizations[0] if organizations else None
        return {
            "user": {"id": context.user_id, "email": context.email},
            "membership": {
                "organization_id": context.organization_id,
                "role": context.role,
            },
            "organization": organization,
        }

    def dashboard(self, token: str) -> dict[str, Any]:
        context = self.auth_context(token)
        scoring_runs = self._request(
            "/rest/v1/scoring_runs",
            token=token,
            query={
                "select": "id,model_version_id,snapshot_date,records_scored,capacity,completed_at",
                "organization_id": f"eq.{context.organization_id}",
                "status": "eq.completed",
                "order": "completed_at.desc",
                "limit": "1",
            },
        )
        if not scoring_runs:
            raise ScoringRunUnavailable()
        run = scoring_runs[0]

        versions = self._request(
            "/rest/v1/model_versions",
            token=token,
            query={
                "select": "id,name,version,trained_at,metrics,methodology,fairness_report,calibration_report",
                "id": f"eq.{run['model_version_id']}",
                "limit": "1",
            },
        )
        if not versions:
            raise ScoringRunUnavailable()
        model = versions[0]

        scores = self._request(
            "/rest/v1/risk_scores",
            token=token,
            query={
                "select": "employee_snapshot_id,source_employee_id,risk_probability,risk_rank,risk_band,explanations,reason_features,primary_action,recommendation,historical_outcome",
                "scoring_run_id": f"eq.{run['id']}",
                "order": "risk_rank.asc",
                "limit": "50",
            },
        )
        snapshot_ids = [str(row["employee_snapshot_id"]) for row in scores]
        snapshots: list[dict[str, Any]] = []
        if snapshot_ids:
            snapshots = self._request(
                "/rest/v1/employee_snapshots",
                token=token,
                query={
                    "select": "id,department,job_role,years_at_company,years_in_current_role,over_time,job_satisfaction,work_life_balance,monthly_income",
                    "id": f"in.({','.join(snapshot_ids)})",
                },
            )
        snapshot_by_id = {str(row["id"]): row for row in snapshots}

        watchlist = [
            self._presentation_record(score, snapshot_by_id.get(str(score["employee_snapshot_id"]), {}))
            for score in scores
        ]
        metrics = dict(model.get("metrics") or {})
        metrics["fairness_report"] = model.get("fairness_report") or {}
        metrics["calibration_report"] = model.get("calibration_report") or {}
        metrics["temporal_validation"] = (model.get("methodology") or {}).get(
            "temporal_validation",
            {"status": "unavailable", "reason": "No dated historical snapshots are available."},
        )
        metrics["model_version"] = {
            "id": model["id"],
            "version": model["version"],
            "trained_at": model["trained_at"],
            "scoring_run_id": run["id"],
            "snapshot_date": run["snapshot_date"],
        }
        return {
            "watchlist": watchlist,
            "top_ten": watchlist[:10],
            "metrics": metrics,
            "departments": sorted({row["Department"] for row in watchlist}),
            "source": "supabase",
        }

    def employee(self, token: str, employee_number: int) -> dict[str, Any] | None:
        """Return the latest approved score for one employee under end-user RLS."""
        context = self.auth_context(token)
        scores = self._request(
            "/rest/v1/risk_scores",
            token=token,
            query={
                "select": "employee_snapshot_id,source_employee_id,risk_probability,risk_rank,risk_band,explanations,reason_features,primary_action,recommendation,historical_outcome",
                "organization_id": f"eq.{context.organization_id}",
                "source_employee_id": f"eq.{employee_number}",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        if not scores:
            return None
        score = scores[0]
        snapshots = self._request(
            "/rest/v1/employee_snapshots",
            token=token,
            query={
                "select": "id,department,job_role,years_at_company,years_in_current_role,over_time,job_satisfaction,work_life_balance,monthly_income",
                "id": f"eq.{score['employee_snapshot_id']}",
                "limit": "1",
            },
        )
        return self._presentation_record(score, snapshots[0] if snapshots else {})

    @staticmethod
    def _presentation_record(score: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        explanations = score.get("explanations") or []
        reason_text = [
            item.get("explanation", "") if isinstance(item, dict) else str(item)
            for item in explanations
        ]
        reason_text = (reason_text + ["", "", ""])[:3]
        return {
            "Rank": score["risk_rank"],
            "EmployeeNumber": score["source_employee_id"],
            "RiskScore": float(score["risk_probability"]),
            "RiskBand": score["risk_band"],
            "Department": snapshot.get("department", "Unknown"),
            "JobRole": snapshot.get("job_role", "Unknown"),
            "YearsAtCompany": snapshot.get("years_at_company", 0),
            "YearsInCurrentRole": snapshot.get("years_in_current_role", 0),
            "OverTime": "Yes" if snapshot.get("over_time") else "No",
            "JobSatisfaction": snapshot.get("job_satisfaction", 0),
            "WorkLifeBalance": snapshot.get("work_life_balance", 0),
            "MonthlyIncome": float(snapshot.get("monthly_income", 0)),
            "HistoricalOutcome": "Yes" if score.get("historical_outcome") else "No",
            "RiskReason1": reason_text[0],
            "RiskReason2": reason_text[1],
            "RiskReason3": reason_text[2],
            "ReasonFeatures": ",".join(score.get("reason_features") or []),
            "PrimaryAction": score.get("primary_action") or "Manager review",
            "Recommendation": score.get("recommendation") or "Review context with a qualified HR partner.",
        }

    def interventions(self, token: str, employee_number: int) -> dict[str, Any]:
        context = self.auth_context(token)
        cases = self._request(
            "/rest/v1/intervention_cases",
            token=token,
            query={
                "select": "*",
                "organization_id": f"eq.{context.organization_id}",
                "source_employee_id": f"eq.{employee_number}",
                "limit": "1",
            },
        )
        case = cases[0] if cases else None
        events: list[dict[str, Any]] = []
        if case:
            events = self._request(
                "/rest/v1/intervention_events",
                token=token,
                query={
                    "select": "id,event_type,from_status,to_status,notes,actor_user_id,event_payload,created_at",
                    "intervention_case_id": f"eq.{case['id']}",
                    "order": "created_at.desc",
                },
            )
        return {"case": case, "events": events}

    def create_intervention(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        context = self.auth_context(token)
        employee_number = int(payload["source_employee_id"])
        score_rows = self._request(
            "/rest/v1/risk_scores",
            token=token,
            query={
                "select": "employee_snapshot_id,scoring_run_id",
                "organization_id": f"eq.{context.organization_id}",
                "source_employee_id": f"eq.{employee_number}",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        score = score_rows[0] if score_rows else {}
        record = {
            "organization_id": context.organization_id,
            "source_employee_id": employee_number,
            "employee_snapshot_id": score.get("employee_snapshot_id"),
            "scoring_run_id": score.get("scoring_run_id"),
            "status": payload.get("status", "not_reviewed"),
            "intervention_type": payload.get("intervention_type"),
            "notes": payload.get("notes"),
            "assigned_to_name": payload.get("assigned_to_name"),
            "follow_up_at": payload.get("follow_up_at"),
            "outcome": payload.get("outcome"),
            "created_by": context.user_id,
            "updated_by": context.user_id,
        }
        created = self._request(
            "/rest/v1/intervention_cases",
            token=token,
            method="POST",
            body=record,
            prefer="return=representation",
        )
        return created[0]

    def update_intervention(self, token: str, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.auth_context(token)
        allowed = {
            "status",
            "intervention_type",
            "notes",
            "assigned_to_name",
            "follow_up_at",
            "outcome",
        }
        record = {key: value for key, value in payload.items() if key in allowed}
        if not record:
            raise SupabaseAPIError("No supported intervention fields were supplied.", 400)
        updated = self._request(
            "/rest/v1/intervention_cases",
            token=token,
            method="PATCH",
            query={"id": f"eq.{case_id}"},
            body=record,
            prefer="return=representation",
        )
        if not updated:
            raise SupabaseAPIError("Intervention case was not found.", 404)
        return updated[0]

    def ingestion_runs(self, token: str, limit: int = 10) -> list[dict[str, Any]]:
        context = self.auth_context(token)
        return self._request(
            "/rest/v1/ingestion_runs",
            token=token,
            query={
                "select": "id,source_type,source_name,status,source_cursor,records_read,records_written,records_rejected,started_at,completed_at,error_summary,metadata",
                "organization_id": f"eq.{context.organization_id}",
                "order": "started_at.desc",
                "limit": str(max(1, min(limit, 50))),
            },
        )
