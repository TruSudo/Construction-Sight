"""Observed outcome cohorts and explicit operator-reviewed scoring changes."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from constructionsight import command_center_state as state
from constructionsight.lead_workflow import STATUSES, connect


def report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        feedback = row.get("feedback", {})
        score = feedback.get("score_at_update", row["security_fit"])
        if score is None:
            score = row["security_fit"]
        band = "60–100" if score >= 60 else "30–59" if score >= 30 else "0–29"
        kind = feedback.get("project_type_at_update") or row["project_type"]
        groups[(kind, band)].append(row)
    result = []
    for (kind, band), cohort in sorted(groups.items()):
        statuses = Counter(r.get("feedback", {}).get("status", "New") for r in cohort)
        closed = statuses["Won"] + statuses["Lost"]
        result.append(
            {
                "project_type": kind,
                "score_band": band,
                "leads": len(cohort),
                "statuses": {s: statuses[s] for s in STATUSES},
                "closed": closed,
                "win_rate": statuses["Won"] / closed if closed else None,
                "source_keys": [r["source_key"] for r in cohort],
            }
        )
    return result


def changes(directory: Path) -> list[dict[str, Any]]:
    state.initialize(directory)
    with connect(directory) as db:
        return [
            json.loads(r["data"]) | {"id": r["id"], "at": r["at"]}
            for r in db.execute("SELECT id,at,data FROM cc_weight_changes ORDER BY id DESC")
        ]


def apply(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if (
        set(payload) != {"weights", "expected_digest", "reason", "reviewed"}
        or payload["reviewed"] is not True
    ):
        raise ValueError("Explicit reviewed weights, prior digest and reason required")
    reason = payload["reason"]
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValueError("Enter a review reason up to 2,000 characters")
    if payload["expected_digest"] != state.fingerprint(state.settings(directory)["weights"]):
        raise ValueError("Weights changed since review; reload before applying")
    result = state.save_settings(
        directory, {"weights": payload["weights"]}, weight_reason=reason.strip()
    )
    return {"weights": result["weights"], "changes": changes(directory)}
