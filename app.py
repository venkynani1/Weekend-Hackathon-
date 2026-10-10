"""Flask application for the TalentGuard retention-risk dashboard."""

from __future__ import annotations

import os
from io import StringIO
import csv
from datetime import datetime

from flask import Flask, abort, jsonify, make_response, render_template, request, send_from_directory

from dashboard_service import DEFAULT_OUTPUT_DIR, DashboardService
from supabase_repository import SupabaseAPIError, SupabaseRepository


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="public", static_url_path="")
    app.config.from_mapping(
        OUTPUT_DIR=DEFAULT_OUTPUT_DIR,
        SUPABASE_URL=os.environ.get("SUPABASE_URL", ""),
        SUPABASE_PUBLISHABLE_KEY=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    dashboard = DashboardService(app.config["OUTPUT_DIR"])
    supabase = None
    if app.config["SUPABASE_URL"] and app.config["SUPABASE_PUBLISHABLE_KEY"]:
        supabase = SupabaseRepository(
            app.config["SUPABASE_URL"],
            app.config["SUPABASE_PUBLISHABLE_KEY"],
        )

    def access_token() -> str:
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise SupabaseAPIError("A valid Supabase session is required.", 401)
        return token.strip()

    def dashboard_data() -> dict:
        if supabase is None:
            return dashboard.load()
        return supabase.dashboard(access_token())

    def validated_intervention_payload(*, require_employee: bool) -> dict:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise SupabaseAPIError("A JSON object is required.", 400)
        if require_employee:
            employee_number = payload.get("source_employee_id")
            if isinstance(employee_number, bool) or not isinstance(employee_number, int) or employee_number < 1:
                raise SupabaseAPIError("source_employee_id must be a positive integer.", 400)
        allowed_statuses = {
            "not_reviewed",
            "reviewed",
            "intervention_planned",
            "follow_up_scheduled",
            "closed",
        }
        if "status" in payload and payload["status"] not in allowed_statuses:
            raise SupabaseAPIError("Unsupported intervention status.", 400)
        for field, limit in {
            "intervention_type": 120,
            "assigned_to_name": 120,
            "notes": 1000,
            "outcome": 500,
        }.items():
            value = payload.get(field)
            if value is not None and (not isinstance(value, str) or len(value.strip()) > limit):
                raise SupabaseAPIError(f"{field} must be text under {limit} characters.", 400)
        follow_up = payload.get("follow_up_at")
        if follow_up is not None:
            if not isinstance(follow_up, str) or len(follow_up) > 40:
                raise SupabaseAPIError("follow_up_at must be an ISO-8601 timestamp.", 400)
            try:
                datetime.fromisoformat(follow_up.replace("Z", "+00:00"))
            except ValueError as error:
                raise SupabaseAPIError("follow_up_at must be an ISO-8601 timestamp.", 400) from error
        return payload

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        origin = request.headers.get("Origin")
        allowed_origins = {
            item.strip()
            for item in os.environ.get(
                "CORS_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173",
            ).split(",")
            if item.strip()
        }
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
            response.headers["Vary"] = "Origin"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(SupabaseAPIError)
    def handle_supabase_error(error: SupabaseAPIError):
        return jsonify({"error": str(error)}), error.status

    @app.get("/")
    def index():
        data = dashboard.load()
        return render_template("index.html", **data)

    @app.get("/api/watchlist")
    def watchlist_api():
        return jsonify(dashboard_data()["watchlist"])

    @app.get("/api/dashboard")
    def dashboard_api():
        return jsonify(dashboard_data())

    @app.get("/api/session")
    def session_api():
        if supabase is None:
            return jsonify(
                {
                    "user": {"id": "local-demo", "email": "local@talentguard.demo"},
                    "membership": {"organization_id": "local-demo", "role": "org_admin"},
                    "organization": {"id": "local-demo", "name": "TalentGuard Demo", "slug": "talentguard-demo"},
                    "source": "local",
                }
            )
        return jsonify(supabase.session(access_token()))

    @app.get("/api/employees/<int:employee_number>")
    def employee_api(employee_number: int):
        if supabase is None:
            employee = dashboard.employee(employee_number)
        else:
            employee = supabase.employee(access_token(), employee_number)
        if employee is None:
            abort(404)
        return jsonify(employee)

    @app.get("/api/interventions")
    def intervention_api():
        if supabase is None:
            return jsonify({"case": None, "events": [], "source": "local"})
        employee_number = request.args.get("employee_number", type=int)
        if employee_number is None:
            return jsonify({"error": "employee_number is required."}), 400
        return jsonify(supabase.interventions(access_token(), employee_number))

    @app.post("/api/interventions")
    def create_intervention_api():
        if supabase is None:
            return jsonify({"error": "Persistent interventions require Supabase configuration."}), 503
        payload = validated_intervention_payload(require_employee=True)
        return jsonify(supabase.create_intervention(access_token(), payload)), 201

    @app.patch("/api/interventions/<uuid:case_id>")
    def update_intervention_api(case_id):
        if supabase is None:
            return jsonify({"error": "Persistent interventions require Supabase configuration."}), 503
        payload = validated_intervention_payload(require_employee=False)
        return jsonify(supabase.update_intervention(access_token(), str(case_id), payload))

    @app.get("/api/ingestion-runs")
    def ingestion_runs_api():
        if supabase is None:
            return jsonify([])
        return jsonify(supabase.ingestion_runs(access_token(), request.args.get("limit", 10, type=int)))

    @app.get("/downloads/watchlist.csv")
    def download_watchlist():
        if supabase is not None:
            rows = dashboard_data()["watchlist"]
            stream = StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()) if rows else [])
            if rows:
                writer.writeheader()
                writer.writerows(rows)
            response = make_response(stream.getvalue())
            response.headers["Content-Type"] = "text/csv; charset=utf-8"
            response.headers["Content-Disposition"] = "attachment; filename=TalentGuard_Top_50_Watchlist.csv"
            return response
        return send_from_directory(
            app.config["OUTPUT_DIR"],
            "top_50_watchlist.csv",
            as_attachment=True,
            download_name="TalentGuard_Top_50_Watchlist.csv",
        )

    @app.get("/downloads/top-10-action-plan.csv")
    def download_top_ten():
        if supabase is not None:
            rows = dashboard_data()["top_ten"]
            stream = StringIO()
            writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()) if rows else [])
            if rows:
                writer.writeheader()
                writer.writerows(rows)
            response = make_response(stream.getvalue())
            response.headers["Content-Type"] = "text/csv; charset=utf-8"
            response.headers["Content-Disposition"] = "attachment; filename=TalentGuard_Top_10_Action_Plan.csv"
            return response
        return send_from_directory(
            app.config["OUTPUT_DIR"],
            "top_10_action_plan.csv",
            as_attachment=True,
            download_name="TalentGuard_Top_10_Action_Plan.csv",
        )

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "data_backend": "supabase" if supabase is not None else "local",
                "outputs_ready": dashboard.is_ready,
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

