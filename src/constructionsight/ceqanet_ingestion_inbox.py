"""Read-only reconciliation between reviewed CEQAnet discovery and persisted CEQA records."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from constructionsight.ceqanet_capture_queue import build_reviewed_ceqanet_capture_queue
from constructionsight.storage.domain_store import CeqaStore

IngestionState = Literal[
    "pending_capture",
    "pending_capture_existing_sch",
    "persisted_source_claim_match",
    "persisted_source_claim_conflict",
    "persisted_county_unavailable",
]


class CeqanetIngestionCandidate(BaseModel):
    """One exact reviewed SCH candidate reconciled against retained CEQA rows."""

    sch_number: str = Field(pattern=r"^[0-9]{10}$")
    source_claimed_county: str = Field(min_length=1)
    source_claimed_title: str | None = None
    official_detail_url: str = Field(min_length=1)
    state: IngestionState
    existing_sch_record_keys: list[str] = Field(default_factory=list)
    existing_sch_record_count: int = Field(ge=0)
    persisted_record_keys: list[str] = Field(default_factory=list)
    persisted_known_counties: list[str] = Field(default_factory=list)
    persisted_missing_county_count: int = Field(ge=0)
    persisted_record_count: int = Field(ge=0)


class CeqanetIngestionInbox(BaseModel):
    """Deterministic queue-to-database status; never authorizes collection or writes."""

    schema_version: Literal["ceqanet_ingestion_inbox.v1"] = "ceqanet_ingestion_inbox.v1"
    listing_artifact_sha256: str = Field(min_length=64, max_length=64)
    queue_artifact_sha256: str = Field(min_length=64, max_length=64)
    listing_plan_id: str | None = None
    candidate_count: int = Field(ge=0)
    pending_capture_count: int = Field(ge=0)
    persisted_candidate_count: int = Field(ge=0)
    conflict_candidate_count: int = Field(ge=0)
    county_unavailable_candidate_count: int = Field(ge=0)
    next_pending_sch: str | None = None
    candidates: list[CeqanetIngestionCandidate] = Field(default_factory=list)
    read_only: Literal[True] = True
    network_executed: Literal[False] = False
    persistence_mutated: Literal[False] = False
    commercial_leads_created: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Queue membership remains a source claim, not proof of current construction activity.",
            "Completion requires exact SCH plus reviewed CEQAnet CSV provenance; other retained "
            "records for the SCH remain context and do not suppress enrichment capture.",
            "County agreement compares retained source claims; it does not independently verify location.",
            "This inbox performs no remote collection, persistence mutation, lead qualification, outreach, or bidding.",
            "Each pending candidate still requires separate current lawful-access review and capture authorization.",
            "Any import still requires independent approval of the exact source and write-plan digests.",
        ]
    )


def build_ceqanet_ingestion_inbox(
    session: Session,
    *,
    listing_payload: Mapping[str, Any],
    listing_bytes: bytes,
    queue_payload: Mapping[str, Any],
    queue_bytes: bytes,
) -> CeqanetIngestionInbox:
    """Rebind a reviewed queue to exact listing bytes and reconcile it with SQLite."""

    if len(queue_bytes) > 16 * 1024 * 1024:
        raise ValueError("retained review queue exceeds the bounded artifact input")
    regenerated = build_reviewed_ceqanet_capture_queue(
        listing_payload,
        original_bytes=listing_bytes,
    )
    if queue_payload != regenerated:
        raise ValueError(
            "saved queue does not exactly match a fresh derivation from listing evidence"
        )
    raw_candidates = regenerated.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("reviewed queue candidates are malformed")
    raw_plan_id = regenerated.get("listing_plan_id")
    if raw_plan_id is not None and not isinstance(raw_plan_id, str):
        raise ValueError("reviewed queue listing plan identity is malformed")

    store = CeqaStore(session)
    candidates: list[CeqanetIngestionCandidate] = []
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            raise ValueError("reviewed queue candidate is malformed")
        sch_number = raw_candidate.get("sch_number")
        source_claimed_county = raw_candidate.get("source_claimed_county")
        official_detail_url = raw_candidate.get("official_detail_url")
        source_claimed_title = raw_candidate.get("source_claimed_title")
        if (
            not isinstance(sch_number, str)
            or not isinstance(source_claimed_county, str)
            or not isinstance(official_detail_url, str)
            or (
                source_claimed_title is not None
                and not isinstance(source_claimed_title, str)
            )
        ):
            raise ValueError("reviewed queue candidate identity is malformed")

        records = store.list_by_state_clearinghouse_number(sch_number)
        reviewed_records = [
            record
            for record in records
            if any(
                provenance.adapter_family == "ceqanet_csv_reviewed"
                for provenance in record.provenance
            )
        ]
        known_counties = sorted(
            {
                record.county.strip()
                for record in reviewed_records
                if isinstance(record.county, str) and record.county.strip()
            }
        )
        missing_county_count = sum(
            record.county is None
            or not isinstance(record.county, str)
            or not record.county.strip()
            for record in reviewed_records
        )
        if not reviewed_records:
            state: IngestionState = (
                "pending_capture_existing_sch" if records else "pending_capture"
            )
        elif any(county != source_claimed_county for county in known_counties):
            state = "persisted_source_claim_conflict"
        elif missing_county_count:
            state = "persisted_county_unavailable"
        else:
            state = "persisted_source_claim_match"

        candidates.append(
            CeqanetIngestionCandidate(
                sch_number=sch_number,
                source_claimed_county=source_claimed_county,
                source_claimed_title=source_claimed_title,
                official_detail_url=official_detail_url,
                state=state,
                existing_sch_record_keys=[record.ceqa_key for record in records],
                existing_sch_record_count=len(records),
                persisted_record_keys=[record.ceqa_key for record in reviewed_records],
                persisted_known_counties=known_counties,
                persisted_missing_county_count=missing_county_count,
                persisted_record_count=len(reviewed_records),
            )
        )

    pending = [
        item
        for item in candidates
        if item.state in {"pending_capture", "pending_capture_existing_sch"}
    ]
    persisted = [
        item
        for item in candidates
        if item.state not in {"pending_capture", "pending_capture_existing_sch"}
    ]
    conflicts = [
        item for item in candidates if item.state == "persisted_source_claim_conflict"
    ]
    unavailable = [
        item for item in candidates if item.state == "persisted_county_unavailable"
    ]
    return CeqanetIngestionInbox(
        listing_artifact_sha256=hashlib.sha256(listing_bytes).hexdigest(),
        queue_artifact_sha256=hashlib.sha256(queue_bytes).hexdigest(),
        listing_plan_id=raw_plan_id,
        candidate_count=len(candidates),
        pending_capture_count=len(pending),
        persisted_candidate_count=len(persisted),
        conflict_candidate_count=len(conflicts),
        county_unavailable_candidate_count=len(unavailable),
        next_pending_sch=pending[0].sch_number if pending else None,
        candidates=candidates,
    )
