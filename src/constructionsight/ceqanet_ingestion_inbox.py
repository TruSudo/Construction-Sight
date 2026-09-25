"""Read-only reconciliation of reviewed CEQAnet discovery candidates with SQLite state."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.ceqanet_capture_queue import build_reviewed_ceqanet_capture_queue
from constructionsight.storage.domain_orm import CeqaDomainRecord


class CeqanetIngestionCandidate(BaseModel):
    """One immutable listing candidate reconciled against retained CEQA rows."""

    model_config = ConfigDict(extra="forbid")

    sch_number: str
    source_claimed_county: str
    source_claimed_title: str | None = None
    official_detail_url: str
    state: Literal[
        "pending_capture",
        "pending_capture_existing_sch",
        "persisted_source_claim_match",
        "persisted_source_claim_conflict",
    ]
    existing_sch_record_count: int = Field(ge=0)
    existing_sch_record_keys: list[str]
    persisted_record_count: int = Field(ge=0)
    persisted_record_keys: list[str]
    persisted_known_counties: list[str]
    candidate_only: bool = True
    read_only: bool = True


class CeqanetIngestionInbox(BaseModel):
    """Exact discovery queue status without network or persistence authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ceqanet_ingestion_inbox.v1"] = "ceqanet_ingestion_inbox.v1"
    listing_artifact_sha256: str
    queue_artifact_sha256: str
    candidate_count: int = Field(ge=0)
    pending_capture_count: int = Field(ge=0)
    persisted_candidate_count: int = Field(ge=0)
    conflict_candidate_count: int = Field(ge=0)
    next_pending_sch: str | None
    candidates: list[CeqanetIngestionCandidate]
    read_only: bool = True
    network_executed: bool = False
    persistence_mutated: bool = False
    commercial_leads_created: bool = False
    limitations: list[str]


def _provenance_is_reviewed_csv(raw: str) -> bool:
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("stored CEQA provenance JSON is invalid") from exc
    if not isinstance(payload, list):
        raise ValueError("stored CEQA provenance must be a JSON array")
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("stored CEQA provenance entry is malformed")
        if item.get("adapter_family") == "ceqanet_csv_reviewed":
            return True
    return False


def build_ceqanet_ingestion_inbox(
    session: Session,
    *,
    listing_payload: dict[str, Any],
    listing_bytes: bytes,
    queue_payload: dict[str, Any],
    queue_bytes: bytes,
) -> CeqanetIngestionInbox:
    """Re-derive the queue and classify every candidate against current retained state."""

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

    reconciled: list[CeqanetIngestionCandidate] = []
    pending = 0
    persisted = 0
    conflicts = 0
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            raise ValueError("reviewed queue candidate is malformed")
        sch = raw_candidate.get("sch_number")
        county = raw_candidate.get("source_claimed_county")
        title = raw_candidate.get("source_claimed_title")
        detail_url = raw_candidate.get("official_detail_url")
        if (
            not isinstance(sch, str)
            or not isinstance(county, str)
            or not isinstance(detail_url, str)
            or (title is not None and not isinstance(title, str))
        ):
            raise ValueError("reviewed queue candidate identity is malformed")

        rows = session.scalars(
            select(CeqaDomainRecord)
            .where(CeqaDomainRecord.state_clearinghouse_number == sch)
            .order_by(CeqaDomainRecord.ceqa_key)
        ).all()
        existing_keys = [row.ceqa_key for row in rows]
        reviewed_rows = [row for row in rows if _provenance_is_reviewed_csv(row.provenance_json)]
        reviewed_keys = [row.ceqa_key for row in reviewed_rows]
        reviewed_counties = sorted(
            {row.county for row in reviewed_rows if isinstance(row.county, str) and row.county}
        )

        if reviewed_rows:
            if reviewed_counties == [county]:
                state = "persisted_source_claim_match"
                persisted += 1
            else:
                state = "persisted_source_claim_conflict"
                conflicts += 1
        elif rows:
            state = "pending_capture_existing_sch"
            pending += 1
        else:
            state = "pending_capture"
            pending += 1

        reconciled.append(
            CeqanetIngestionCandidate(
                sch_number=sch,
                source_claimed_county=county,
                source_claimed_title=title,
                official_detail_url=detail_url,
                state=state,
                existing_sch_record_count=len(rows),
                existing_sch_record_keys=existing_keys,
                persisted_record_count=len(reviewed_rows),
                persisted_record_keys=reviewed_keys,
                persisted_known_counties=reviewed_counties,
            )
        )

    next_pending = next(
        (
            item.sch_number
            for item in reconciled
            if item.state in {"pending_capture", "pending_capture_existing_sch"}
        ),
        None,
    )
    return CeqanetIngestionInbox(
        listing_artifact_sha256=hashlib.sha256(listing_bytes).hexdigest(),
        queue_artifact_sha256=hashlib.sha256(queue_bytes).hexdigest(),
        candidate_count=len(reconciled),
        pending_capture_count=pending,
        persisted_candidate_count=persisted,
        conflict_candidate_count=conflicts,
        next_pending_sch=next_pending,
        candidates=reconciled,
        limitations=[
            "This is a read-only reconciliation of retained evidence and SQLite records.",
            "A queued SCH is a source claim, not a verified active construction site or qualified lead.",
            "Network capture and two-digest persistence approval remain separate explicit operations.",
        ],
    )
