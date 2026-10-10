"""Flask application for the TalentGuard retention-risk dashboard."""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from agent import decide, load_queue
from scoring import (
    CHOICE_FIELDS,
    FIELD_LABELS,
    INT_FIELDS,
    ROLES_BY_DEPARTMENT,
    ScoringService,
    ValidationError,
    validate_profile,
)
from services import DEFAULT_ARTIFACT_DIR, DEFAULT_OUTPUT_DIR, DashboardService, train_and_export

PUBLIC_PAGES = ["index", "insights", "simulator", "queue", "privacy", "terms"]
RATE_LIMIT = (30, 60)  # 30 requests per 60 seconds per client on write endpoints


class RateLimiter:
    """Small in-memory sliding-window limiter. Good enough for one free instance."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            bucket = self.hits[key]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True


class PageCounter:
    """Cookie-free, first-party analytics: page views per path per day. No personal data."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def hit(self, page: str) -> None:
        today = date.today().isoformat()
        with self.lock:
            self.data.setdefault(today, {}).setdefault(page, 0)
            self.data[today][page] += 1
            try:
                self.path.write_text(json.dumps(self.data), encoding="utf-8")
            except OSError:
                pass

    def summary(self) -> dict:
        today = date.today().isoformat()
        return {
            "today": sum(self.data.get(today, {}).values()),
            "all_time": sum(sum(day.values()) for day in self.data.values()),
            "by_page_today": self.data.get(today, {}),
        }


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        OUTPUT_DIR=Path(os.environ.get("TALENTGUARD_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)),
        ARTIFACT_DIR=Path(os.environ.get("TALENTGUARD_ARTIFACT_DIR", DEFAULT_ARTIFACT_DIR)),
        AUTO_TRAIN=os.environ.get("TALENTGUARD_AUTO_TRAIN", "1") == "1",
        # Secrets come from the environment only. A random key is generated for
        # local runs so nothing secret is ever committed to the repo.
        SECRET_KEY=os.environ.get("TALENTGUARD_SECRET_KEY") or secrets.token_hex(32),
        SITE_URL=os.environ.get("TALENTGUARD_SITE_URL", "").rstrip("/"),
        GOATCOUNTER_CODE=os.environ.get("TALENTGUARD_GOATCOUNTER", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("TALENTGUARD_SECURE_COOKIES", "0") == "1",
        SEND_FILE_MAX_AGE_DEFAULT=60 * 60 * 24 * 7,
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    output_dir = app.config["OUTPUT_DIR"]
    dashboard = DashboardService(output_dir)
    if (not dashboard.is_ready or not (Path(output_dir) / "action_queue.json").exists()) and app.config["AUTO_TRAIN"]:
        train_and_export(output_dir=output_dir, artifact_dir=app.config["ARTIFACT_DIR"])
    scorer = ScoringService(output_dir, app.config["ARTIFACT_DIR"])
    limiter = RateLimiter(*RATE_LIMIT)
    counter = PageCounter(Path(output_dir) / "analytics.json")

    # ------------------------------------------------------------ helpers
    def client_key() -> str:
        forwarded = request.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[0].strip() or request.remote_addr or "unknown"

    def csrf_token() -> str:
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    def check_write_request(token: str | None, honeypot: str | None) -> tuple[str, int] | None:
        """Shared spam / abuse protection for every POST."""
        if honeypot:
            return "Request rejected.", 400  # bots fill hidden fields
        if not token or token != session.get("csrf"):
            return "Your session expired. Reload the page and try again.", 400
        if not limiter.allow(client_key()):
            return "Too many requests. Wait a minute and try again.", 429
        return None

    def site_url() -> str:
        return app.config["SITE_URL"] or request.url_root.rstrip("/")

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": csrf_token,
            "site_url": site_url(),
            "goatcounter": app.config["GOATCOUNTER_CODE"],
            "current_year": date.today().year,
        }

    @app.before_request
    def count_page_view():
        if request.method == "GET" and request.endpoint in PUBLIC_PAGES:
            counter.hit(request.endpoint)

    @app.after_request
    def harden(response: Response) -> Response:
        gc = "https://gc.zgo.at" if app.config["GOATCOUNTER_CODE"] else ""
        gc_connect = f"https://{app.config['GOATCOUNTER_CODE']}.goatcounter.com" if gc else ""
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' {gc}; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            f"connect-src 'self' {gc_connect}; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        ).replace("  ", " ")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/api/") or request.endpoint == "queue":
            response.headers["Cache-Control"] = "no-store"

        # gzip text responses: the dashboard HTML drops by roughly 80%.
        compressible = response.mimetype in {"text/css", "application/javascript", "text/javascript", "image/svg+xml"}
        if response.direct_passthrough and compressible and request.path.startswith("/static/"):
            response.direct_passthrough = False  # let small static text files be gzipped below
        if (
            "gzip" in request.headers.get("Accept-Encoding", "")
            and response.status_code == 200
            and not response.direct_passthrough
            and response.mimetype in {"text/html", "text/css", "application/javascript", "text/javascript",
                                      "application/json", "image/svg+xml", "text/plain", "application/xml"}
            and "Content-Encoding" not in response.headers
        ):
            data = response.get_data()
            if len(data) > 1024:
                response.set_data(gzip.compress(data, compresslevel=6))
                response.headers["Content-Encoding"] = "gzip"
                response.headers["Content-Length"] = str(len(response.get_data()))
                response.headers.add("Vary", "Accept-Encoding")
        return response

    # ------------------------------------------------------------ pages
    @app.get("/")
    def index():
        data = dashboard.load()
        return render_template("index.html", **data)

    @app.get("/insights")
    def insights():
        data = dashboard.load()
        return render_template("insights.html", metrics=data["metrics"], ins=data["metrics"]["insights"])

    @app.get("/simulator")
    def simulator():
        data = dashboard.load()
        requested = request.args.get("employee", type=int)
        default_id = requested or int(data["watchlist"][0]["EmployeeNumber"])
        profile = scorer.profile_for(default_id)
        if profile is None:
            default_id = int(data["watchlist"][0]["EmployeeNumber"])
            profile = scorer.profile_for(default_id)
        return render_template(
            "simulator.html",
            watchlist=data["watchlist"],
            employee_ids=scorer.employee_ids(),
            selected_id=default_id,
            profile=profile,
            int_fields=INT_FIELDS,
            choice_fields=CHOICE_FIELDS,
            labels=FIELD_LABELS,
            roles_by_department=ROLES_BY_DEPARTMENT,
        )

    @app.get("/queue")
    def queue():
        items = load_queue(output_dir)
        status = request.args.get("status", "")
        if status and status in {"PENDING_APPROVAL", "APPROVED", "REJECTED"}:
            shown = [i for i in items if i["status"] == status]
        else:
            status, shown = "", items
        counts = {s: sum(1 for i in items if i["status"] == s) for s in ("PENDING_APPROVAL", "APPROVED", "REJECTED")}
        return render_template("queue.html", items=shown, counts=counts, status=status,
                               message=request.args.get("msg", ""), stats=counter.summary())

    @app.post("/queue/<draft_id>/decision")
    def queue_decision(draft_id: str):
        problem = check_write_request(request.form.get("csrf"), request.form.get("website"))
        if problem:
            return render_template("error.html", title="Request not accepted", message=problem[0]), problem[1]
        try:
            item = decide(output_dir, draft_id, request.form.get("decision", ""),
                          request.form.get("reviewer", ""), request.form.get("note", ""))
        except KeyError:
            abort(404)
        except ValueError as error:
            return redirect(url_for("queue", msg=f"Not saved: {error}") + f"#{draft_id}")
        verb = {"APPROVED": "approved", "REJECTED": "rejected", "PENDING_APPROVAL": "reset to pending"}[item["status"]]
        return redirect(url_for("queue", msg=f"Draft for employee {item['employee_number']} {verb}.") + f"#{draft_id}")

    @app.get("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.get("/terms")
    def terms():
        return render_template("terms.html")

    # ------------------------------------------------------------ APIs
    @app.get("/api/watchlist")
    def watchlist_api():
        return jsonify(dashboard.load()["watchlist"])

    @app.get("/api/employees/<int:employee_number>")
    def employee_api(employee_number: int):
        employee = dashboard.employee(employee_number)
        if employee is None:
            abort(404)
        return jsonify(employee)

    @app.get("/api/profile/<int:employee_number>")
    def profile_api(employee_number: int):
        profile = scorer.profile_for(employee_number)
        if profile is None:
            return jsonify({"error": "Employee not found."}), 404
        return jsonify(profile)

    @app.post("/api/score")
    def score_api():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Send a JSON object."}), 400
        problem = check_write_request(request.headers.get("X-CSRF-Token"), payload.get("website"))
        if problem:
            return jsonify({"error": problem[0]}), problem[1]
        try:
            profile = validate_profile(payload.get("profile") or {})
        except ValidationError as error:
            return jsonify({"error": "Some fields need attention.", "fields": error.errors}), 422
        employee = payload.get("employee_number")
        employee = int(employee) if isinstance(employee, (int, str)) and str(employee).isdigit() else None
        return jsonify(scorer.score(profile, employee))

    @app.get("/api/queue")
    def queue_api():
        return jsonify(load_queue(output_dir))

    # ------------------------------------------------------------ downloads
    @app.get("/downloads/watchlist.csv")
    def download_watchlist():
        return send_from_directory(output_dir, "top_50_watchlist.csv", as_attachment=True,
                                   download_name="TalentGuard_Top_50_Watchlist.csv")

    @app.get("/downloads/top-10-action-plan.csv")
    def download_top_ten():
        return send_from_directory(output_dir, "top_10_action_plan.csv", as_attachment=True,
                                   download_name="TalentGuard_Top_10_Action_Plan.csv")

    @app.get("/downloads/action-queue.csv")
    def download_queue():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "rank", "employee_number", "job_role", "action", "owner", "status",
                         "last_decision_by", "invite_subject", "invite_body", "manager_brief"])
        for item in load_queue(output_dir):
            writer.writerow([item["id"], item["rank"], item["employee_number"], item["job_role"], item["action"],
                             item["owner"], item["status"], item["history"][-1]["by"], item["invite_subject"],
                             item["invite_body"], item["manager_brief"]])
        return Response(buffer.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=TalentGuard_Action_Queue.csv"})

    # ------------------------------------------------------------ SEO and platform files
    @app.get("/robots.txt")
    def robots():
        body = f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /downloads/\n\nSitemap: {site_url()}/sitemap.xml\n"
        return Response(body, mimetype="text/plain")

    @app.get("/sitemap.xml")
    def sitemap():
        today = date.today().isoformat()
        priorities = {"index": "1.0", "insights": "0.8", "simulator": "0.8", "queue": "0.5", "privacy": "0.2", "terms": "0.2"}
        urls = "".join(
            f"<url><loc>{site_url()}{url_for(page)}</loc><lastmod>{today}</lastmod><priority>{priorities[page]}</priority></url>"
            for page in PUBLIC_PAGES
        )
        xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
        return Response(xml, mimetype="application/xml")

    @app.get("/site.webmanifest")
    def manifest():
        return jsonify({
            "name": "TalentGuard", "short_name": "TalentGuard", "start_url": "/", "display": "standalone",
            "background_color": "#f5f6f1", "theme_color": "#173f35",
            "icons": [{"src": url_for("static", filename="img/icon-192.png"), "sizes": "192x192", "type": "image/png"},
                      {"src": url_for("static", filename="img/icon-512.png"), "sizes": "512x512", "type": "image/png"}],
        })

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(Path(app.static_folder) / "img", "favicon.ico", mimetype="image/x-icon")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "outputs_ready": dashboard.is_ready})

    # ------------------------------------------------------------ errors
    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found."}), 404
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"error": "Request too large."}), 413

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", title="Something went wrong",
                               message="The error has been logged. Try again in a moment."), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
