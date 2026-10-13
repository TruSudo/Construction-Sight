"""Explainable security-fit ranking of source claims, independent of lead readiness."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

WEIGHTS = {
    "industrial": 40,
    "commercial": 30,
    "residential": 20,
    "infrastructure": 10,
    "commenced": 30,
    "upcoming": 20,
    "unknown_stage": 5,
    "repeat_developer": 5,
    "repeat_cap": 20,
}
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


def rank_leads(rows: list[dict[str, Any]], *, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
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
        score = WEIGHTS.get(project_type, 0)
        reasons = [f"Name keywords: {project_type} (+{score})"]
        start = parse_date(row.get("CONSTRUCTION_COMMENCEMENT_DATE"))
        end = parse_date(row.get("COMPLETE_PROJECT_DATE"))
        if end and end < today:
            stage, points = "Reported completion date passed", 0
        elif start and start <= today:
            stage, points = "Reported commencement date passed", WEIGHTS["commenced"]
        elif start:
            stage, points = "Reported future commencement", WEIGHTS["upcoming"]
        else:
            stage, points = "Commencement unknown", WEIGHTS["unknown_stage"]
        score += points
        reasons.append(f"{stage} (+{points})")
        count = counts.get(developer_key(row), 0)
        repeat = min(max(count - 1, 0) * WEIGHTS["repeat_developer"], WEIGHTS["repeat_cap"])
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
