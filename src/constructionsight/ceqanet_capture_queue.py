"""Conservative offline queue from saved, complete public CEQAnet listing evidence.

Neither a listing observation nor a candidate command is authority to fetch a
project, write the database, qualify a lead, or assert current construction.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from constructionsight.adapters.ceqanet_result_parser import parse_ceqanet_result_page

_TARGET_COUNTIES = frozenset({"San Bernardino", "Riverside"})
_SOURCE_HOST = "ceqanet.lci.ca.gov"
_MAX_PAGES = 10
_MAX_CANDIDATES = 1_000
_SCH_PATTERN = re.compile(r"[0-9]{10}")
_DETAIL_PATTERN = re.compile(r"/(?:Project|Document)/([0-9]{10})/?")


def _official_url(value: object, *, search: bool) -> str:
    if not isinstance(value, str):
        raise ValueError("listing URL is not a string")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _SOURCE_HOST
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("listing URL is not an exact official HTTPS source")
    if search:
        if parsed.path != "/Search":
            raise ValueError("listing request does not target the official /Search path")
    elif not _DETAIL_PATTERN.fullmatch(parsed.path) or parsed.query:
        raise ValueError("candidate link is not an exact official SCH detail page")
    return value


def build_reviewed_ceqanet_capture_queue(
    listing_payload: Mapping[str, Any], *, original_bytes: bytes,
) -> dict[str, Any]:
    """Review every saved page; emit only exact 10-digit, target-county project candidates.

    Fail the whole derivation for incomplete/contradictory execution evidence.
    Per-record unknown counties and absent/ambiguous SCH identifiers remain
    exclusions, never guessed or promoted to approved project records.
    """

    if len(original_bytes) > 16 * 1024 * 1024:
        raise ValueError("retained listing exceeds the bounded artifact input")
    metadata = listing_payload.get("metadata")
    snapshots = listing_payload.get("snapshots")
    if not isinstance(metadata, dict) or metadata.get("schema_version") != (
        "ceqanet_listing_execution.v2"
    ):
        raise ValueError("requires a governed v2 listing execution report")
    access = metadata.get("access")
    authorization = metadata.get("authorization")
    if (
        metadata.get("allowed") is not True
        or not isinstance(access, dict)
        or access.get("decision") != "allowed"
        or not isinstance(authorization, dict)
        or not isinstance(authorization.get("decision_id"), str)
        or not authorization["decision_id"]
        or not isinstance(snapshots, list)
        or not 1 <= len(snapshots) <= _MAX_PAGES
        or metadata.get("planned_request_count") != len(snapshots)
        or metadata.get("executed_request_count") != len(snapshots)
        or metadata.get("successful_response_count") != len(snapshots)
        or metadata.get("failed_response_count") != 0
    ):
        raise ValueError("listing execution does not report a complete authorized page set")

    candidates: dict[str, dict[str, Any]] = {}
    excluded = {"missing_or_ambiguous_sch": 0, "outside_target_counties": 0}
    parsed_count = 0
    for page_index, snapshot in enumerate(snapshots, 1):
        if not isinstance(snapshot, dict):
            raise ValueError("listing snapshot is not an object")
        request_url = _official_url(snapshot.get("request_url"), search=True)
        final_url = _official_url(snapshot.get("final_url"), search=True)
        body = snapshot.get("body_text")
        content_type = snapshot.get("content_type")
        if (
            snapshot.get("page_number") != page_index
            or snapshot.get("method") != "GET"
            or request_url != final_url
            or snapshot.get("status_code") != 200
            or snapshot.get("executed") is not True
            or snapshot.get("reachable") is not True
            or snapshot.get("body_truncated") is not False
            or snapshot.get("error") is not None
            or snapshot.get("failure_kind") != "none"
            or not isinstance(content_type, str)
            or content_type.split(";", 1)[0].strip().lower() not in {
                "text/html", "application/xhtml+xml",
            }
            or not isinstance(body, str)
            or not body.strip()
            or len(body.encode("utf-8")) > 50_000
        ):
            raise ValueError("listing page is incomplete, redirected, or not a valid HTML GET")
        records = parse_ceqanet_result_page(body, source_url=request_url).records
        parsed_count += len(records)
        for record in records:
            sch = record.sch_number
            if not isinstance(sch, str) or not _SCH_PATTERN.fullmatch(sch):
                excluded["missing_or_ambiguous_sch"] += 1
                continue
            try:
                link = _official_url(record.detail_url, search=False)
            except ValueError:
                excluded["missing_or_ambiguous_sch"] += 1
                continue
            match = _DETAIL_PATTERN.fullmatch(urlparse(link).path)
            if match is None or match[1] != sch:
                excluded["missing_or_ambiguous_sch"] += 1
                continue
            if record.county not in _TARGET_COUNTIES:
                excluded["outside_target_counties"] += 1
                continue
            existing = candidates.get(sch)
            if existing is None:
                if len(candidates) == _MAX_CANDIDATES:
                    raise ValueError("listing produced more than the bounded candidate limit")
                candidates[sch] = {
                    "sch_number": sch,
                    "source_claimed_county": record.county,
                    "source_claimed_title": record.title,
                    "title_requires_detail_enrichment": record.requires_detail_enrichment,
                    "official_detail_url": link,
                    "observation_pages": [page_index],
                    "source_observation_count": 1,
                    "review_state": "unverified_source_claim",
                    "candidate_only": True,
                    "network_executed_for_candidate": False,
                    "persistence_mutated": False,
                }
            else:
                if existing["source_claimed_county"] != record.county:
                    raise ValueError("conflicting county claims for one exact SCH identity")
                existing["source_observation_count"] += 1
                if page_index not in existing["observation_pages"]:
                    existing["observation_pages"].append(page_index)
                existing["title_requires_detail_enrichment"] = (
                    existing["title_requires_detail_enrichment"]
                    or record.requires_detail_enrichment
                )

    ordered = [candidates[key] for key in sorted(candidates)]
    return {
        "schema_version": "ceqanet_exact_sch_capture_queue.v1",
        "listing_artifact_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "listing_plan_id": metadata.get("plan_id"),
        "listing_pages_reviewed": len(snapshots),
        "listing_records_parsed": parsed_count,
        "candidate_count": len(ordered),
        "excluded_observations": excluded,
        "candidates": ordered,
        "network_executed": False,
        "persistence_mutated": False,
        "commercial_leads_created": False,
        "limitations": [
            (
                "Stored listing execution metadata is not independently authenticated "
                "by this offline queue."
            ),
            (
                "A listing search candidate is a source claim, not a verified current "
                "project or active site."
            ),
            (
                "Only exact 10-digit SCH/detail URL agreement and explicitly target-county "
                "rows are queued."
            ),
            "A retained snapshot can be historical; its capture timestamp is not established here.",
            (
                "Each candidate requires separate current lawful-access review and "
                "one-request authorization."
            ),
            "A repeated exact SCH may replay old evidence; capture-preview refuses to call it new.",
            "The existing two-digest reviewed import remains separate and is never auto-approved.",
        ],
    }
