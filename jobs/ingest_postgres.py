"""Incrementally ingest an existing hosted PostgreSQL employee view.

This job has no CSV upload path. The source account should be read-only and the
source view should expose the snake_case fields listed in SNAPSHOT_FIELDS plus a
monotonic cursor column configured with SOURCE_CURSOR_COLUMN.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os
import re
from typing import Any

from jobs.publish_model_run import PublishError, SupabaseAdminClient, chunks


SNAPSHOT_FIELDS = [
    "source_employee_id", "attrition", "age", "business_travel", "daily_rate",
    "department", "distance_from_home", "education", "education_field",
    "employee_count", "environment_satisfaction", "gender", "hourly_rate",
    "job_involvement", "job_level", "job_role", "job_satisfaction",
    "marital_status", "monthly_income", "monthly_rate", "num_companies_worked",
    "over_18", "over_time", "percent_salary_hike", "performance_rating",
    "relationship_satisfaction", "standard_hours", "stock_option_level",
    "total_working_years", "training_times_last_year", "work_life_balance",
    "years_at_company", "years_in_current_role", "years_since_last_promotion",
    "years_with_current_manager",
]

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def qualified_identifier(value: str):
    """Return a safely quoted psycopg identifier for schema.table or table."""
    from psycopg import sql

    parts = value.split(".")
    if not 1 <= len(parts) <= 2 or any(not SAFE_IDENTIFIER.fullmatch(part) for part in parts):
        raise PublishError(f"Unsafe database identifier: {value!r}")
    return sql.SQL(".").join(sql.Identifier(part) for part in parts)


def normalize_record(row: dict[str, Any], organization_id: str, run_id: str, snapshot_date: str) -> dict[str, Any]:
    missing = [field for field in SNAPSHOT_FIELDS if field not in row and field != "attrition"]
    if missing:
        raise PublishError(f"Source view is missing required fields: {', '.join(missing)}")
    record = {field: row.get(field) for field in SNAPSHOT_FIELDS}
    if isinstance(record["attrition"], str):
        record["attrition"] = record["attrition"].strip().lower() in {"yes", "true", "1"}
    if isinstance(record["over_time"], str):
        record["over_time"] = record["over_time"].strip().lower() in {"yes", "true", "1"}
    record.update(
        {
            "organization_id": organization_id,
            "ingestion_run_id": run_id,
            "snapshot_date": snapshot_date,
            "source_payload": {"ingested_at": datetime.now(timezone.utc).isoformat()},
        }
    )
    return record


def fetch_source_rows(connection_url: str, view: str, cursor_column: str, after: str | None, limit: int) -> list[dict[str, Any]]:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row

    view_identifier = qualified_identifier(view)
    cursor_identifier = qualified_identifier(cursor_column)
    where = sql.SQL("")
    parameters: list[Any] = []
    if after is not None:
        # Cursor text must sort monotonically (ISO-8601 timestamps or zero-padded sequences).
        where = sql.SQL(" where {}::text > %s").format(cursor_identifier)
        parameters.append(after)
    query = sql.SQL("select *, {}::text as _talentguard_cursor from {}{} order by {} asc limit %s").format(
        cursor_identifier,
        view_identifier,
        where,
        cursor_identifier,
    )
    parameters.append(limit)
    with psycopg.connect(connection_url, row_factory=dict_row, connect_timeout=15) as connection:
        connection.execute("set transaction read only")
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return list(cursor.fetchall())


def ingest(args: argparse.Namespace) -> dict[str, Any]:
    source_url = os.environ.get("SOURCE_DATABASE_URL", "").strip()
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    secret_key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    if not source_url or not supabase_url or not secret_key:
        raise PublishError("SOURCE_DATABASE_URL, SUPABASE_URL, and SUPABASE_SECRET_KEY are required.")
    client = SupabaseAdminClient(supabase_url, secret_key)
    organizations = client.request("organizations", query={"select": "id", "slug": f"eq.{args.organization_slug}", "limit": "1"})
    if not organizations:
        raise PublishError(f"Organization {args.organization_slug!r} does not exist.")
    organization_id = organizations[0]["id"]

    previous = client.request(
        "ingestion_runs",
        query={
            "select": "source_cursor",
            "organization_id": f"eq.{organization_id}",
            "source_name": f"eq.{args.source_view}",
            "status": "eq.completed",
            "order": "completed_at.desc",
            "limit": "1",
        },
    )
    after = previous[0]["source_cursor"] if previous else None
    run = client.request(
        "ingestion_runs",
        method="POST",
        body={
            "organization_id": organization_id,
            "source_type": "hosted_postgresql",
            "source_name": args.source_view,
            "status": "running",
            "source_cursor": after,
            "metadata": {"cursor_column": args.cursor_column, "mode": "incremental_read_only"},
        },
        prefer="return=representation",
    )[0]
    try:
        rows = fetch_source_rows(source_url, args.source_view, args.cursor_column, after, args.limit)
        # Keep only the latest update per employee within this batch.
        deduplicated: dict[int, dict[str, Any]] = {}
        for row in rows:
            deduplicated[int(row["source_employee_id"])] = row
        snapshots = [normalize_record(row, organization_id, run["id"], args.snapshot_date) for row in deduplicated.values()]
        for batch in chunks(snapshots, 250):
            client.request(
                "employee_snapshots",
                method="POST",
                query={"on_conflict": "organization_id,source_employee_id,snapshot_date"},
                body=batch,
                prefer="resolution=merge-duplicates,return=minimal",
            )
        next_cursor = rows[-1]["_talentguard_cursor"] if rows else after
        completed = client.request(
            "ingestion_runs",
            method="PATCH",
            query={"id": f"eq.{run['id']}"},
            body={
                "status": "completed",
                "source_cursor": next_cursor,
                "records_read": len(rows),
                "records_written": len(snapshots),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            prefer="return=representation",
        )[0]
    except Exception as error:
        client.request(
            "ingestion_runs",
            method="PATCH",
            query={"id": f"eq.{run['id']}"},
            body={"status": "failed", "error_summary": str(error)[:1000], "completed_at": datetime.now(timezone.utc).isoformat()},
            prefer="return=minimal",
        )
        raise
    return {"ingestion_run_id": completed["id"], "records_read": len(rows), "records_written": len(snapshots), "source_cursor": next_cursor}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest employee snapshots from a hosted PostgreSQL view.")
    parser.add_argument("--organization-slug", default=os.environ.get("TALENTGUARD_ORGANIZATION_SLUG", "talentguard-demo"))
    parser.add_argument("--source-view", default=os.environ.get("SOURCE_EMPLOYEE_VIEW", "employee_attrition_features"))
    parser.add_argument("--cursor-column", default=os.environ.get("SOURCE_CURSOR_COLUMN", "updated_at"))
    parser.add_argument("--snapshot-date", default=date.today().isoformat())
    parser.add_argument("--limit", type=int, default=5000)
    return parser.parse_args()


if __name__ == "__main__":
    try:
        result = ingest(parse_args())
    except PublishError as error:
        raise SystemExit(f"Ingestion failed: {error}") from error
    print(json.dumps(result, indent=2))
