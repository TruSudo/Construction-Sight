"""Bounded SMARTS recent-project review through ConstructionSight's shared intake spine.

Explicit operator-run demonstration only: not a scheduler, sales pipeline, or
an authoritative count of all new or physically active construction projects.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

import httpx

from constructionsight.smarts_api import (
    COUNTIES,
    USER_AGENT,
    SmartsApiError,
    fetch_exact_facility,
    fetch_recent_candidates,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview


def build_recent_review(
    client: httpx.Client, *, county: str, limit: int = 3
) -> dict[str, Any]:
    """One index query + at most five exact record queries, no retries or writes."""
    if county not in COUNTIES or type(limit) is not int or not 1 <= limit <= 5:
        raise SmartsApiError("Only approved counties and 1..5 candidates are permitted")
    observation = fetch_recent_candidates(client, county=county, limit=limit)
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in observation.records:
        app_id = row.get("APP_ID")
        if row.get("STATUS") != "Active":
            skipped.append({"reason": "not_active_regulatory_status"})
            continue
        if not isinstance(app_id, str) or not re.fullmatch(r"[0-9]{1,15}", app_id):
            skipped.append({"reason": "missing_usable_app_id"})
            continue
        if app_id in seen:
            skipped.append({"reason": "repeated_app_id_in_candidate_query"})
            continue
        seen.add(app_id)
        try:
            page = fetch_exact_facility(client, county=county, app_id=app_id)
            preview = build_smarts_intake_preview(page, page.records[0])
        except SmartsApiError as exc:
            # Do not silently drop a candidate; retain an explicit review blocker.
            skipped.append({"reason": "exact_retrieval_failed", "app_id": app_id,
                            "detail": str(exc)})
            continue
        title = next(
            (fact.value for fact in preview.intake.extracted_facts
             if fact.source_field == "SITE_NAME"),
            None,
        )
        site = preview.site_resolution.candidates
        candidate = site[0] if site else None
        results.append({
            "source_record_key": preview.source_record_key,
            "record_sha256": preview.record_sha256,
            "response_sha256": preview.source_response_sha256,
            "site_name": title,
            "site_city": preview.intake.source_hints.get("jurisdiction"),
            "reported_commencement": preview.intake.record_hints.get(
                "reported_construction_commencement"
            ),
            "regulatory_status": preview.intake.record_hints["regulatory_status"],
            "site_resolution_status": preview.site_resolution.status.value,
            "site_key_candidate": candidate.site_key if candidate else None,
            "latitude": candidate.latitude if candidate else None,
            "longitude": candidate.longitude if candidate else None,
            "construction_activity": preview.construction_activity,
            "commercial_readiness": preview.commercial_readiness,
            "next_action": preview.intake.next_action,
        })
    return {
        "mode": "smarts_recent_review.v1",
        "county": county,
        "candidate_query_sha256": observation.response_sha256,
        "candidate_count": len(observation.records),
        "reviewed_count": len(results),
        "skipped": skipped,
        "records": results,
        "read_only": True,
        "persistence_mutated": False,
        "construction_activity_verified": False,
        "outreach_authorized": False,
        "limitations": [
            "Newest nonnull NOI processing dates do not mean construction is underway.",
            "Records lacking numeric APP_ID are not resolved by this bounded review.",
            "No complete county coverage or historical completeness is claimed.",
            "Site keys are only provisional; parcel/project linkage requires review.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only SMARTS recent regulatory project review"
    )
    parser.add_argument("--county", required=True, choices=COUNTIES)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_live:
        parser.error("Live access requires --execute-live")
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            report = build_recent_review(client, county=args.county, limit=args.limit)
    except SmartsApiError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, **report}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
