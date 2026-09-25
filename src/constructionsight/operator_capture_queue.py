"""Read one retained CEQAnet exact-SCH review queue for the local operator.

This module is intentionally offline.  It validates a bounded queue artifact and
returns a reduced presentation model.  A queue candidate is not authorization
to fetch, import, qualify, contact, bid, or otherwise mutate ConstructionSight.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_QUEUE_SCHEMA = "ceqanet_exact_sch_capture_queue.v1"
_OPERATOR_SCHEMA = "constructionsight.operator_capture_queue.v1"
_SOURCE_HOST = "ceqanet.lci.ca.gov"
_TARGET_COUNTIES = frozenset({"San Bernardino", "Riverside"})
_SCH = re.compile(r"^[0-9]{10}$")
_DETAIL = re.compile(r"^/(?:Project|Document)/([0-9]{10})/?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_BYTES = 2 * 1024 * 1024
_MAX_CANDIDATES = 1_000


def empty_operator_capture_queue() -> dict[str, Any]:
    """Return the explicit not-configured state used by the local dashboard."""

    return {
        "schema_version": _OPERATOR_SCHEMA,
        "configured": False,
        "read_only": True,
        "network_executed": False,
        "persistence_mutated": False,
        "commercial_leads_created": False,
        "candidate_count": 0,
        "candidates": [],
        "limitations": [
            "No retained exact-SCH capture queue was configured for this operator session.",
            (
                "The dashboard cannot discover, fetch, import, qualify, contact, or bid "
                "from this state."
            ),
        ],
    }


def _integer(value: object, *, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} is outside its bounded integer range")
    return value


def _official_detail_url(value: object, *, sch_number: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("capture queue candidate lacks an official detail URL")
    parsed = urlparse(value)
    match = _DETAIL.fullmatch(parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _SOURCE_HOST
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or match is None
        or match[1] != sch_number
    ):
        raise ValueError("capture queue candidate detail URL is not the exact official SCH page")
    return value


def _candidate(value: object, *, page_count: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("capture queue candidate is not an object")
    sch_number = value.get("sch_number")
    if not isinstance(sch_number, str) or _SCH.fullmatch(sch_number) is None:
        raise ValueError("capture queue candidate lacks an exact 10-digit SCH number")
    county = value.get("source_claimed_county")
    if county not in _TARGET_COUNTIES:
        raise ValueError("capture queue candidate county is outside the operator target scope")
    title = value.get("source_claimed_title")
    if not isinstance(title, str) or not title.strip() or len(title) > 2_000:
        raise ValueError("capture queue candidate title is missing or unbounded")
    pages = value.get("observation_pages")
    if (
        not isinstance(pages, list)
        or not pages
        or len(pages) > page_count
        or any(
            isinstance(page, bool)
            or not isinstance(page, int)
            or not 1 <= page <= page_count
            for page in pages
        )
        or pages != sorted(set(pages))
    ):
        raise ValueError("capture queue candidate observation pages are inconsistent")
    observation_count = _integer(
        value.get("source_observation_count"),
        minimum=len(pages),
        maximum=10_000,
        label="source observation count",
    )
    if (
        value.get("review_state") != "unverified_source_claim"
        or value.get("candidate_only") is not True
        or value.get("network_executed_for_candidate") is not False
        or value.get("persistence_mutated") is not False
        or not isinstance(value.get("title_requires_detail_enrichment"), bool)
    ):
        raise ValueError("capture queue candidate authority state is inconsistent")
    return {
        "sch_number": sch_number,
        "source_claimed_county": county,
        "source_claimed_title": title,
        "title_requires_detail_enrichment": value["title_requires_detail_enrichment"],
        "official_detail_url": _official_detail_url(
            value.get("official_detail_url"), sch_number=sch_number
        ),
        "observation_pages": pages,
        "source_observation_count": observation_count,
        "review_state": "unverified_source_claim",
        "candidate_only": True,
        "network_executed_for_candidate": False,
        "persistence_mutated": False,
    }


def load_operator_capture_queue(path: Path) -> dict[str, Any]:
    """Load and validate one bounded retained queue without performing network access."""

    raw = read_runtime_artifact(path, max_bytes=_MAX_BYTES)
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("capture queue is not valid bounded UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != _QUEUE_SCHEMA:
        raise ValueError("capture queue has an unsupported schema")
    source_digest = payload.get("listing_artifact_sha256")
    if not isinstance(source_digest, str) or _SHA256.fullmatch(source_digest) is None:
        raise ValueError("capture queue lacks its exact listing-artifact digest")
    page_count = _integer(
        payload.get("listing_pages_reviewed"),
        minimum=1,
        maximum=10,
        label="listing page count",
    )
    parsed_count = _integer(
        payload.get("listing_records_parsed"),
        minimum=0,
        maximum=100_000,
        label="listing parsed record count",
    )
    values = payload.get("candidates")
    if not isinstance(values, list) or len(values) > _MAX_CANDIDATES:
        raise ValueError("capture queue candidate collection is missing or unbounded")
    candidates = [_candidate(item, page_count=page_count) for item in values]
    keys = [item["sch_number"] for item in candidates]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError("capture queue candidates are duplicated or not canonically ordered")
    count = _integer(
        payload.get("candidate_count"),
        minimum=0,
        maximum=_MAX_CANDIDATES,
        label="candidate count",
    )
    if count != len(candidates):
        raise ValueError("capture queue candidate count disagrees with retained candidates")
    excluded = payload.get("excluded_observations")
    if (
        not isinstance(excluded, dict)
        or set(excluded) != {"missing_or_ambiguous_sch", "outside_target_counties"}
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in excluded.values()
        )
    ):
        raise ValueError("capture queue exclusion counts are inconsistent")
    if (
        payload.get("network_executed") is not False
        or payload.get("persistence_mutated") is not False
        or payload.get("commercial_leads_created") is not False
    ):
        raise ValueError("capture queue authority state is inconsistent")
    plan_id = payload.get("listing_plan_id")
    if plan_id is not None and (
        not isinstance(plan_id, str) or not plan_id or len(plan_id) > 255
    ):
        raise ValueError("capture queue listing plan identity is invalid")
    return {
        "schema_version": _OPERATOR_SCHEMA,
        "configured": True,
        "read_only": True,
        "network_executed": False,
        "persistence_mutated": False,
        "commercial_leads_created": False,
        "listing_artifact_sha256": source_digest,
        "listing_plan_id": plan_id,
        "listing_pages_reviewed": page_count,
        "listing_records_parsed": parsed_count,
        "candidate_count": count,
        "excluded_observations": dict(excluded),
        "candidates": candidates,
        "limitations": [
            "Candidates are retained source claims, not verified current projects or active sites.",
            "Queue metadata is not independent authentication of the original listing execution.",
            (
                "Each SCH requires a separate current lawful-access review and one-request "
                "authorization."
            ),
            "The local dashboard cannot fetch, import, qualify, contact, bid, or create a lead.",
        ],
    }
