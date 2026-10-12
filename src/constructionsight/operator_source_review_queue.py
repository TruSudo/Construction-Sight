"""Bounded read-only source-observation triage; never qualify leads by inference."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.operator_dashboard_models import (
    RecordKind,
    RecordSelection,
    SourceCandidateReviewCheck,
)
from constructionsight.operator_source_candidate import build_source_candidate_preview
from constructionsight.storage.operator_read_store import read_project_page


class SourceReviewQueueItem(BaseModel):
    """A single content-bound source observation requiring independent review."""

    record_kind: RecordKind
    record_id: str
    title: str
    county: str | None
    candidate_key: str
    preview_id: str
    normalized_source_sha256: str = Field(min_length=64, max_length=64)
    state: Literal["hold", "review_required"]
    checks: list[SourceCandidateReviewCheck]
    source_claim_only: Literal[True] = True
    outreach_authorized: Literal[False] = False
    bid_authorized: Literal[False] = False


class SourceReviewQueuePage(BaseModel):
    """Page counts are source records; no implication of countywide coverage."""

    schema_version: Literal["constructionsight.source-review-queue/v1"] = (
        "constructionsight.source-review-queue/v1"
    )
    selection: RecordSelection
    county_filter: str
    query: str
    items: list[SourceReviewQueueItem]
    total_source_records: int = Field(ge=0)
    returned: int = Field(ge=0, le=25)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=25)
    has_more: bool
    read_only: Literal[True] = True
    network_executed: Literal[False] = False
    source_records_mutated: Literal[False] = False
    lead_created: Literal[False] = False
    outreach_authorized: Literal[False] = False
    bid_authorized: Literal[False] = False
    limitations: list[str] = Field(default_factory=lambda: [
        "This queue lists retained source observations, not distinct construction projects.",
        "Historical CEQA and permit facts cannot establish current construction activity.",
        "Hold/review-required classifications are not green outreach eligibility.",
        "No domain, commercial or source-review-docket mutation occurs.",
    ])


def build_source_review_queue(
    session: Session,
    *,
    kind: RecordSelection = "all",
    county: str = "",
    query: str = "",
    limit: int = 10,
    offset: int = 0,
) -> SourceReviewQueuePage:
    """Resolve exact normalized source digests on one capped deterministic page."""

    if kind not in {"all", "ceqa", "permit"}:
        raise ValueError("invalid source review kind")
    if county not in {"", "San Bernardino", "Riverside"} or len(query) > 200:
        raise ValueError("invalid source review county or query")
    if not 1 <= limit <= 25 or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid source review page bounds")
    normalized_query = query.strip()
    records, total = read_project_page(
        session, kind=kind, query=normalized_query, county=county,
        limit=limit, offset=offset,
    )
    items: list[SourceReviewQueueItem] = []
    for record in records:
        record_kind: RecordKind = "ceqa" if isinstance(record, CeqaRecord) else "permit"
        record_id = record.ceqa_key if isinstance(record, CeqaRecord) else record.permit_key
        preview = build_source_candidate_preview(
            session, kind=record_kind, record_id=record_id
        )
        # An intervening writer must not silently bind a new digest to an old page.
        if (
            preview.source_record.record_kind != record_kind
            or preview.source_record.record_id != record_id
            or preview.source_snapshot.model_dump(mode="json", round_trip=True)
            != record.model_dump(mode="json", round_trip=True)
        ):
            raise ValueError("source record changed during triage page inspection")
        items.append(SourceReviewQueueItem(
            record_kind=record_kind,
            record_id=record_id,
            title=preview.source_record.title,
            county=preview.source_record.county,
            candidate_key=preview.candidate_key,
            preview_id=preview.preview_id,
            normalized_source_sha256=preview.normalized_source_sha256,
            state=preview.state,
            checks=preview.checks,
        ))
    return SourceReviewQueuePage(
        selection=kind,
        county_filter=county,
        query=normalized_query,
        items=items,
        total_source_records=total,
        returned=len(items),
        offset=offset,
        limit=limit,
        has_more=offset + len(items) < total,
    )
