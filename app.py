"""Flask application for the TalentGuard retention-risk dashboard."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, send_from_directory

from services import DEFAULT_OUTPUT_DIR, DashboardService, train_and_export


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        OUTPUT_DIR=Path(os.environ.get("TALENTGUARD_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)),
        AUTO_TRAIN=os.environ.get("TALENTGUARD_AUTO_TRAIN", "1") == "1",
    )
    if test_config:
        app.config.update(test_config)

    dashboard = DashboardService(app.config["OUTPUT_DIR"])
    if not dashboard.is_ready and app.config["AUTO_TRAIN"]:
        train_and_export(output_dir=app.config["OUTPUT_DIR"])

    @app.get("/")
    def index():
        data = dashboard.load()
        return render_template("index.html", **data)

    @app.get("/api/watchlist")
    def watchlist_api():
        return jsonify(dashboard.load()["watchlist"])

    @app.get("/api/employees/<int:employee_number>")
    def employee_api(employee_number: int):
        employee = dashboard.employee(employee_number)
        if employee is None:
            abort(404)
        return jsonify(employee)

    @app.get("/downloads/watchlist.csv")
    def download_watchlist():
        return send_from_directory(
            app.config["OUTPUT_DIR"],
            "top_50_watchlist.csv",
            as_attachment=True,
            download_name="TalentGuard_Top_50_Watchlist.csv",
        )

    @app.get("/downloads/top-10-action-plan.csv")
    def download_top_ten():
        return send_from_directory(
            app.config["OUTPUT_DIR"],
            "top_10_action_plan.csv",
            as_attachment=True,
            download_name="TalentGuard_Top_10_Action_Plan.csv",
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "outputs_ready": dashboard.is_ready})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)

