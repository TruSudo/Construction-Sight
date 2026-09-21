"""Typed, non-authoritative read models for the local operator interface."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.entity_models import Entity
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance

RecordKind = Literal["ceqa", "permit"]
RecordSelection = Literal["all", "ceqa", "permit"]
MilestoneKind = Literal[
    "ceqa_received", "ceqa_posted", "permit_applied", "permit_issued", "permit_finaled"
]


class DashboardPoint(BaseModel):
    """Source-claimed geographic coordinates, never proof of a verified location."""

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    site_key: str
    provenance: list[Provenance]
    classification: Literal["source_claimed"] = "source_claimed"


class SourceMilestone(BaseModel):
    """Stored source-event date, never proof of a current construction phase."""

    event_kind: MilestoneKind
    recorded_date: date
    classification: Literal["source_claimed"] = "source_claimed"


class DashboardProject(BaseModel):
    """One source record, not a deduplicated project or approved prospect."""

    record_id: str
    record_kind: RecordKind
    title: str
    county: str | None
    jurisdiction: str | None
    source_status: str | None = None
    description: str | None = None
    source_record_number: str | None = None
    milestones: list[SourceMilestone] = Field(default_factory=list)
    site_key: str | None = None
    address: str | None = None
    apn: str | None = None
    point: DashboardPoint | None = None
    map_reason: str
    coverage: Literal["target_county", "outside_target_counties", "unknown"]
    entities: list[Entity] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DashboardSnapshot(BaseModel):
    """Bounded source-record page with honest whole-query and page counts."""

    selection: RecordSelection
    projects: list[DashboardProject]
    total: int
    returned: int
    mapped_on_page: int
    offset: int
    limit: int
    has_more: bool
    read_only: Literal[True] = True
    live_collection_enabled: Literal[False] = False
    crime_overlay_enabled: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Source records are not deduplicated projects or qualified leads.",
            "Historical source status does not establish present construction activity.",
            "Coordinates are source claims; no geocoding or spatial verification is performed.",
            "This offline coordinate map has no street basemap or county boundary layer.",
        ]
    )


class FootprintPoint(BaseModel):
    """Lightweight map identity for one source record in stable query order."""

    ordinal: int = Field(ge=0)
    record_id: str
    record_kind: RecordKind
    title: str
    county: str | None
    point: DashboardPoint


class GeographicFootprintSnapshot(BaseModel):
    """Bounded whole-query geographic view with explicit completeness semantics."""

    selection: RecordSelection
    points: list[FootprintPoint]
    matching_total: int
    records_scanned: int
    mapped_in_scan: int
    scan_limit: int
    truncated: bool
    read_only: Literal[True] = True
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Points are source records, not deduplicated projects or qualified leads.",
            "Coordinates are source claims; no geocoding or spatial verification is performed.",
            "When truncated is true, this response is not the complete matching footprint.",
        ]
    )


class HistoricalSourceEvent(BaseModel):
    """One dated assertion retained within a specific source-family/key record."""

    ordinal: int = Field(ge=0)
    record_kind: RecordKind
    record_id: str
    title: str
    county: str | None
    event_kind: MilestoneKind
    recorded_date: date
    source_date_order_conflict: bool = False
    classification: Literal["source_claimed"] = "source_claimed"


class HistoricalTimelineSnapshot(BaseModel):
    """Bounded historical event view, not live construction or distinct-project counts."""

    selection: RecordSelection
    events: list[HistoricalSourceEvent]
    matching_total: int
    records_scanned: int
    dated_records_in_scan: int
    milestones_in_scan: int
    returned_events: int
    scan_limit: int
    result_limit: int
    source_scan_truncated: bool
    event_result_truncated: bool
    read_only: Literal[True] = True
    live_collection_enabled: Literal[False] = False
    limitations: list[str] = Field(default_factory=lambda: [
        "Dates and statuses are retained source claims, not a construction-site activity feed.",
        "Events belong to source records, not deduplicated real-world projects.",
        "When source_scan_truncated is true, newer events may exist outside the scan.",
        "When event_result_truncated is true, events beyond the displayed set were omitted.",
        "Absent dates are not inferred and source event ordering conflicts are flagged.",
    ])


class EntityNeighborhoodSnapshot(BaseModel):
    """Bounded exact-key co-occurrence in persisted source claims, never identity proof."""

    entity_key: str
    selection: RecordSelection
    county_filter: str
    records: list[DashboardProject]
    scanned_source_records: int
    total_source_records: int
    matching_records_in_scan: int
    returned: int
    scan_limit: int
    result_limit: int
    source_scan_truncated: bool
    matching_records_truncated: bool
    read_only: Literal[True] = True
    limitations: list[str] = Field(
        default_factory=lambda: [
            "An exact stored entity key is a source co-occurrence, not independently "
            "verified identity.",
            "Different source-family IDs remain separate records; no project deduplication "
            "is performed.",
            "Counts cover only the scanned source records when source_scan_truncated is true.",
            "Records shown are a bounded subset when matching_records_truncated is true.",
            "Source claims do not establish current construction activity or commercial "
            "qualification.",
        ]
    )



class SourceCandidateReviewCheck(BaseModel):
    """A source observation or unresolved review gap; never an approval."""

    key: Literal["provenance", "county", "site", "parties", "current_activity",
                 "deduplication", "commercial_review"]
    state: Literal["source_claim_only", "missing", "conflict",
                   "out_of_scope", "review_required"]
    detail: str = Field(min_length=1)


class SourceCandidatePreview(BaseModel):
    """Unpersisted, non-authoritative candidate review based on one exact source."""

    schema_version: Literal["constructionsight.source-candidate-preview/v1"] = (
        "constructionsight.source-candidate-preview/v1"
    )
    candidate_key: str = Field(min_length=1)
    preview_id: str = Field(min_length=1)
    normalized_source_sha256: str = Field(min_length=64, max_length=64)
    source_record: DashboardProject
    source_snapshot: CeqaRecord | PermitRecord
    state: Literal["hold", "review_required"]
    checks: list[SourceCandidateReviewCheck]
    read_only: Literal[True] = True
    persisted: Literal[False] = False
    commercial_lead_created: Literal[False] = False
    outreach_authorized: Literal[False] = False
    bid_authorized: Literal[False] = False
    limitations: list[str] = Field(default_factory=lambda: [
        "This is a normalized stored-record digest, not a raw source document hash.",
        "Source records do not prove independent entity/site identity or current activity.",
        "No legacy scored OpportunityCandidate, persisted commercial lead, review "
        "approval, outreach, or bid authorization was created.",
    ])
