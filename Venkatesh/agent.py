"""Rule-based retention agent.

For each employee on the watch list it drafts two things:
  1. a private briefing for the line manager / HR partner (reasons + talking points)
  2. a neutral meeting invite to the employee

Nothing is sent. Every draft starts as PENDING_APPROVAL and only a named human
reviewer can move it to APPROVED or REJECTED. Each decision is written to an
audit trail. The employee invite never mentions a risk score or the model:
telling someone "our algorithm thinks you will quit" damages trust and can
trigger the exit it was meant to prevent.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

QUEUE_FILE = "action_queue.json"
STATUSES = {"PENDING_APPROVAL", "APPROVED", "REJECTED"}
_LOCK = threading.Lock()

# Talking points per intervention type. Kept short so a manager can use them live.
PLAYBOOK: dict[str, dict[str, Any]] = {
    "Compensation review": {
        "invite_topic": "your role, growth and reward",
        "talking_points": [
            "Ask how they see their pay and total reward compared with the market.",
            "Share what is possible this cycle (band review, stock, allowance) without promising a number.",
            "Agree a date to come back with a concrete answer.",
        ],
        "owner": "HR Business Partner + Compensation",
        "sla_days": 10,
    },
    "Career progression plan": {
        "invite_topic": "your career plans for the next 12 months",
        "talking_points": [
            "Ask where they want to be in a year and what is blocking them.",
            "Offer one specific stretch project, course or mentor.",
            "Write down two milestones and review them in 60 days.",
        ],
        "owner": "Line manager",
        "sla_days": 14,
    },
    "Role fit check-in": {
        "invite_topic": "how your current role is going",
        "talking_points": [
            "Check that role expectations and success measures are clear.",
            "Ask what support they did not get when they started.",
            "Consider a buddy or an internal move if the fit is wrong.",
        ],
        "owner": "Line manager",
        "sla_days": 7,
    },
    "Workload reset": {
        "invite_topic": "your workload and schedule",
        "talking_points": [
            "Review the last 8 weeks of overtime together.",
            "Remove or re-assign one recurring task this week.",
            "Agree a norm for after-hours work and check it in 30 days.",
        ],
        "owner": "Line manager",
        "sla_days": 7,
    },
    "Manager stay interview": {
        "invite_topic": "what keeps you here and what we could do better",
        "talking_points": [
            "Ask: what would make you leave, and what would make you stay?",
            "Listen first; do not defend.",
            "Commit to two changes and track them openly.",
        ],
        "owner": "Skip-level manager",
        "sla_days": 10,
    },
    "Flexibility review": {
        "invite_topic": "your travel and working pattern",
        "talking_points": [
            "Map their travel or commute over the last quarter.",
            "Offer a rotation, a remote day, or a travel cap where the role allows.",
            "Review the change after one month.",
        ],
        "owner": "Line manager",
        "sla_days": 10,
    },
    "Stay interview": {
        "invite_topic": "how things are going",
        "talking_points": [
            "Ask what they enjoy most and least about the job.",
            "Ask what one change would make the biggest difference.",
            "Agree a follow-up date.",
        ],
        "owner": "Line manager",
        "sla_days": 14,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def draft_for(row: dict[str, Any]) -> dict[str, Any]:
    action = row["PrimaryAction"]
    play = PLAYBOOK.get(action, PLAYBOOK["Stay interview"])
    emp = int(row["EmployeeNumber"])
    reasons = [row["RiskReason1"], row["RiskReason2"], row["RiskReason3"]]

    manager_brief = (
        f"CONFIDENTIAL: HR use only. PENDING_APPROVAL.\n\n"
        f"Employee #{emp}, {row['JobRole']} ({row['Department']}). Watch-list rank {int(row['Rank'])} of 50.\n\n"
        f"Why this person is on the list (model signals, not facts about intent):\n"
        + "\n".join(f"  {i}. {r}" for i, r in enumerate(reasons, 1))
        + f"\n\nRecommended intervention: {action}\n"
        f"{row['Recommendation']}\n\n"
        f"Talking points:\n" + "\n".join(f"  - {p}" for p in play["talking_points"])
        + f"\n\nOwner: {play['owner']}. Hold the conversation within {play['sla_days']} days of approval.\n"
        f"Do not mention the risk score, the watch list or this tool to the employee."
    )

    invite_subject = f"Time to talk about {play['invite_topic']}"
    invite_body = (
        f"Hi,\n\n"
        f"I would like to set aside 30 minutes in the next couple of weeks to talk about {play['invite_topic']}. "
        f"There is nothing to prepare. I want to hear how things are going for you and what would help.\n\n"
        f"Please pick a slot that works for you, or suggest another time.\n\n"
        f"Thanks,\n[Manager name]"
    )

    return {
        "id": f"TG-{emp}",
        "employee_number": emp,
        "rank": int(row["Rank"]),
        "job_role": row["JobRole"],
        "department": row["Department"],
        "action": action,
        "owner": play["owner"],
        "sla_days": play["sla_days"],
        "value_at_risk": float(row.get("ValueAtRisk", 0.0) or 0.0),
        "manager_brief": manager_brief,
        "invite_subject": invite_subject,
        "invite_body": invite_body,
        "status": "PENDING_APPROVAL",
        "created_at": _now(),
        "history": [{"at": _now(), "event": "DRAFTED", "by": "TalentGuard agent (rule-based)"}],
    }


def build_action_queue(watchlist: pd.DataFrame, output_dir: str | Path) -> list[dict[str, Any]]:
    queue = [draft_for(row) for row in watchlist.to_dict(orient="records")]
    path = Path(output_dir) / QUEUE_FILE
    with _LOCK, path.open("w", encoding="utf-8") as handle:
        json.dump(queue, handle, indent=2)
    return queue


def load_queue(output_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(output_dir) / QUEUE_FILE
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def decide(output_dir: str | Path, draft_id: str, decision: str, reviewer: str, note: str = "") -> dict[str, Any]:
    """Record a human decision. Raises ValueError on bad input."""
    if decision not in {"APPROVED", "REJECTED", "PENDING_APPROVAL"}:
        raise ValueError("Decision must be APPROVED, REJECTED or PENDING_APPROVAL.")
    reviewer = reviewer.strip()
    if not (2 <= len(reviewer) <= 60):
        raise ValueError("Reviewer name must be 2 to 60 characters.")
    note = note.strip()[:300]
    path = Path(output_dir) / QUEUE_FILE
    with _LOCK:
        queue = load_queue(output_dir)
        item = next((d for d in queue if d["id"] == draft_id), None)
        if item is None:
            raise KeyError(draft_id)
        item["status"] = decision
        item["history"].append({"at": _now(), "event": decision, "by": reviewer, "note": note})
        with path.open("w", encoding="utf-8") as handle:
            json.dump(queue, handle, indent=2)
    return item
