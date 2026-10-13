"""Explainable security-fit ranking of source claims, independent of lead readiness."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

WEIGHTS_PATH = Path(__file__).parent / "command_center" / "security_fit_weights.json"
WEIGHTS: dict[str, int] = json.loads(WEIGHTS_PATH.read_text())


def load_weights(path: Path | None = None) -> dict[str, int]:
    weights = json.loads((path or WEIGHTS_PATH).read_text())
    if (
        not isinstance(weights, dict)
        or set(weights) != set(WEIGHTS)
        or any(type(v) is not int or not 0 <= v <= 100 for v in weights.values())
    ):
        raise ValueError("Weights must contain the configured names and integers from 0 to 100")
    return weights


KEYWORDS = {
    "industrial": ("logistic", "warehouse", "distribution", "industrial", "fulfillment"),
    "commercial": ("retail", "commercial", "hotel", "shopping", "office", "hospital"),
    "residential": ("residential", "apartment", "housing", "homes", "townhome"),
    "infrastructure": ("road", "street", "pipeline", "highway", "utility", "bridge"),
}


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def developer_key(row: dict[str, Any]) -> str:
    key = " ".join(str(row.get("DEVELOPER_NAME") or "").casefold().split())
    return "" if key in {"na", "n/a", "unknown", "none", "-"} else key


def rank_leads(
    rows: list[dict[str, Any]], *, today: date | None = None, weights: dict[str, int] | None = None
) -> list[dict[str, Any]]:
    today = today or date.today()
    weights = weights if weights is not None else load_weights()
    counts = Counter(developer_key(row) for row in rows if developer_key(row))
    ranked = []
    for row in rows:
        text = (
            str(row.get("SITE_NAME") or "") + " " + str(row.get("DEVELOPER_NAME") or "")
        ).casefold()
        project_type = next(
            (kind for kind, words in KEYWORDS.items() if any(word in text for word in words)),
            "unknown",
        )
        score = weights.get(project_type, 0)
        reasons = [f"Name keywords: {project_type} (+{score})"]
        start = parse_date(row.get("CONSTRUCTION_COMMENCEMENT_DATE"))
        end = parse_date(row.get("COMPLETE_PROJECT_DATE"))
        if end and end < today:
            stage, points = "Reported completion date passed", 0
        elif start and start <= today:
            stage, points = "Reported commencement date passed", weights["commenced"]
        elif start:
            stage, points = "Reported future commencement", weights["upcoming"]
        else:
            stage, points = "Commencement unknown", weights["unknown_stage"]
        score += points
        reasons.append(f"{stage} (+{points})")
        count = counts.get(developer_key(row), 0)
        repeat = min(max(count - 1, 0) * weights["repeat_developer"], weights["repeat_cap"])
        score += repeat
        reasons.append(f"Developer appears in {count} active source rows (+{repeat})")
        if row.get("conflicting_fields"):
            reasons.append(
                "Conflicting source fields shown as unknown: "
                + ", ".join(row["conflicting_fields"])
            )
        ranked.append(
            {
                **row,
                "security_fit": min(score, 100),
                "project_type": project_type,
                "stage": stage,
                "reason": "; ".join(reasons),
                "fit_band": "high" if score >= 60 else "review" if score >= 30 else "low",
            }
        )
    return sorted(
        ranked,
        key=lambda r: (
            -r["security_fit"],
            str(r.get("SITE_NAME") or ""),
            str(r.get("WDID") or ""),
            str(r.get("APP_ID") or ""),
        ),
    )
