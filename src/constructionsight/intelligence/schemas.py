"""Foundational intelligence domain schemas.

These Pydantic models define the first stable intelligence-layer contract for
ConstructionSight. They intentionally contain no persistence or runtime side
effects; stores, services, and event processing will be layered on top after the
schema contract is validated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class EntityType(StrEnum):
    """Entity categories used by the relationship intelligence layer."""

    PERSON = "person"
    ORGANIZATION = "organization"
    DEVELOPER = "developer"
    OWNER = "owner"
    APPLICANT = "applicant"
    GENERAL_CONTRACTOR = "general_contractor"
    SUBCONTRACTOR = "subcontractor"
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    DIRECTOR = "director"
    PROJECT_EXECUTIVE = "project_executive"
    PROJECT = "project"
    SITE = "site"
    PARCEL = "parcel"
    PERMIT = "permit"
    PLANNING_CASE = "planning_case"
    CEQA_RECORD = "ceqa_record"
    AGENCY = "agency"
    JURISDICTION = "jurisdiction"
    DOCUMENT = "document"
    CONTACT = "contact"
    UNKNOWN = "unknown"


class IdentityStatus(StrEnum):
    """Resolution state for identity assertions and candidates."""

    CONFIRMED_SAME = "confirmed_same"
    PROBABLE_SAME = "probable_same"
    POSSIBLE_SAME = "possible_same"
    RELATED_DISTINCT = "related_distinct"
    CONFLICTING = "conflicting"
    UNRESOLVED = "unresolved"
    REJECTED_MATCH = "rejected_match"
    SUPERSEDED = "superseded"
    STALE = "stale"


class RelationshipStatus(StrEnum):
    """Evidence status for relationship assertions."""

    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    CONFLICTING = "conflicting"
    UNRESOLVED = "unresolved"
    SUPERSEDED = "superseded"
    STALE = "stale"


class CoverageStatus(StrEnum):
    """Geographic coverage classification for records and entities."""

    IN_ZONE = "in_zone"
    ADJACENT_CANDIDATE = "adjacent_candidate"
    OUT_OF_ZONE_REFERENCE = "out_of_zone_reference"
    UNKNOWN_ZONE = "unknown_zone"
    UNSUPPORTED = "unsupported"
    REJECTED = "rejected"


class MonitoringStatus(StrEnum):
    """Operational monitoring classification."""

    ACTIVE = "active"
    WATCHLIST = "watchlist"
    REFERENCE_ONLY = "reference_only"
    PAUSED = "paused"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    NEEDS_REVIEW = "needs_review"
    IGNORED = "ignored"


class ProjectClusterStatus(StrEnum):
    """Confidence state for a project cluster."""

    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    CONFLICTING = "conflicting"
    STANDALONE = "standalone"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class LifecyclePhase(StrEnum):
    """Construction lifecycle phases inferred from public evidence."""

    UNKNOWN = "unknown"
    CONCEPTUAL_OR_PREAPPLICATION = "conceptual_or_preapplication"
    PLANNING_ENTITLEMENT = "planning_entitlement"
    ENVIRONMENTAL_REVIEW = "environmental_review"
    APPROVED_NOT_PERMITTED = "approved_not_permitted"
    PRECONSTRUCTION = "preconstruction"
    DEMOLITION = "demolition"
    SITE_WORK_GRADING = "site_work_grading"
    FOUNDATION = "foundation"
    VERTICAL_CONSTRUCTION = "vertical_construction"
    ROUGH_IN_TRADES = "rough_in_trades"
    FIRE_LIFE_SAFETY = "fire_life_safety"
    SPECIALTY_SYSTEMS = "specialty_systems"
    INSPECTION_FINALIZATION = "inspection_finalization"
    COMPLETED_OCCUPIED = "completed_occupied"
    STALLED_EXPIRED = "stalled_expired"
    CANCELLED_OR_WITHDRAWN = "cancelled_or_withdrawn"


class AuthorityStatus(StrEnum):
    """Site or project authority enrichment state."""

    NOT_STARTED = "not_started"
    SOURCE_RECORD_IDENTIFIED = "source_record_identified"
    PRIMARY_PARTIES_EXTRACTED = "primary_parties_extracted"
    RELATED_RECORDS_SEARCHING = "related_records_searching"
    CANDIDATE_AUTHORITIES_FOUND = "candidate_authorities_found"
    AUTHORITY_PARTIALLY_RESOLVED = "authority_partially_resolved"
    AUTHORITY_CONFIRMED = "authority_confirmed"
    CONFLICTING_AUTHORITY_CANDIDATES = "conflicting_authority_candidates"
    AUTHORITY_UNRESOLVED_WITH_REASON = "authority_unresolved_with_reason"


class OpportunityCategory(StrEnum):
    """Commercial opportunity categories supported by the intelligence layer."""

    CONSTRUCTION_SITE_SECURITY = "construction_site_security"
    TEMPORARY_FENCING = "temporary_fencing"
    SURVEILLANCE_TRAILERS = "surveillance_trailers"
    LIGHTING_TOWERS = "lighting_towers"
    ACCESS_CONTROL = "access_control"
    PATROL_SERVICES = "patrol_services"
    ROOFING = "roofing"
    SOLAR_INSTALLATION = "solar_installation"
    BATTERY_STORAGE = "battery_storage"
    EV_CHARGING = "ev_charging"
    HVAC = "hvac"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    CONCRETE = "concrete"
    GRADING = "grading"
    DEMOLITION = "demolition"
    FIRE_SPRINKLER = "fire_sprinkler"
    FIRE_ALARM = "fire_alarm"
    TENANT_IMPROVEMENT = "tenant_improvement"
    LANDSCAPING = "landscaping"
    SIGNAGE = "signage"
    GENERAL_CONSTRUCTION_SERVICES = "general_construction_services"
    PROFESSIONAL_SERVICES = "professional_services"


class OpportunityStatus(StrEnum):
    """Lifecycle state for an opportunity signal."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    HIGH_PRIORITY = "high_priority"
    WATCHLIST = "watchlist"
    STALE = "stale"
    EXPIRED = "expired"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class RuntimeEventType(StrEnum):
    """High-level runtime event types emitted by the intelligence system."""

    SOURCE_RECORD_DISCOVERED = "source_record_discovered"
    SOURCE_RECORD_CHANGED = "source_record_changed"
    ENTITY_CREATED = "entity_created"
    ENTITY_MERGED = "entity_merged"
    RELATIONSHIP_CREATED = "relationship_created"
    RELATIONSHIP_UPDATED = "relationship_updated"
    PROJECT_CLUSTER_CREATED = "project_cluster_created"
    PROJECT_CLUSTER_UPDATED = "project_cluster_updated"
    AUTHORITY_STATUS_CHANGED = "authority_status_changed"
    PROJECT_PHASE_CHANGED = "project_phase_changed"
    OPPORTUNITY_SIGNAL_CREATED = "opportunity_signal_created"
    SOURCE_VERIFICATION_ADDED = "source_verification_added"
    EXPORT_CREATED = "export_created"
    ENRICHMENT_FAILED = "enrichment_failed"


class RuntimeEventSeverity(StrEnum):
    """UI and operational severity for runtime events."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEBUG = "debug"


class WatchlistStatus(StrEnum):
    """User watchlist lifecycle state."""

    ACTIVE = "active"
    PAUSED = "paused"
    STALE = "stale"
    TRIGGERED = "triggered"
    NEEDS_REVIEW = "needs_review"
    ARCHIVED = "archived"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class EvidenceRecord(BaseModel):
    """Source evidence supporting facts, relationships, clusters, or opportunities."""

    evidence_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str | None = None
    source_family: str | None = None
    jurisdiction: str | None = None
    record_type: str = Field(min_length=1)
    source_record_id: str | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    observed_at: datetime | None = None
    evidence_field: str | None = None
    evidence_value: str | None = None
    evidence_text: str | None = None
    content_hash: str | None = None
    retrieval_method: str | None = None
    access_status: str | None = None
    adapter_name: str | None = None
    confidence_contribution: int = Field(default=0, ge=0, le=100)
    limitations: list[str] = Field(default_factory=list)
    raw_observations: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_evidence_payload(self) -> EvidenceRecord:
        """Require at least one concrete evidence payload field."""

        if not any([self.evidence_value, self.evidence_text, self.raw_observations]):
            raise ValueError("evidence must include a value, text, or raw_observations")
        return self


class EntityIdentity(BaseModel):
    """Canonical or candidate entity identity."""

    entity_id: str = Field(min_length=1)
    entity_type: EntityType
    canonical_name: str = Field(min_length=1)
    normalized_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)
    identifiers: dict[str, str] = Field(default_factory=dict)
    addresses: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)
    related_source_record_ids: list[str] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    confidence_score: int = Field(default=0, ge=0, le=100)
    identity_status: IdentityStatus = IdentityStatus.UNRESOLVED
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
    last_verified: datetime | None = None
    evidence_summary: str | None = None
    contradiction_summary: str | None = None

    @field_validator(
        "aliases",
        "source_names",
        "addresses",
        "jurisdictions",
        "related_source_record_ids",
        "evidence_record_ids",
    )
    @classmethod
    def require_unique_values(cls, value: list[str]) -> list[str]:
        """Reject duplicate list values to keep identity payloads deterministic."""

        if len(value) != len(set(value)):
            raise ValueError("identity list fields must contain unique values")
        return value


class IdentityCandidate(BaseModel):
    """Candidate match between two identities before merge or rejection."""

    candidate_id: str = Field(min_length=1)
    left_entity_id: str = Field(min_length=1)
    right_entity_id: str = Field(min_length=1)
    candidate_score: int = Field(ge=0, le=100)
    matching_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    proposed_status: IdentityStatus = IdentityStatus.POSSIBLE_SAME
    explanation: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    review_required: bool = False

    @model_validator(mode="after")
    def reject_self_match(self) -> IdentityCandidate:
        """Do not allow an entity to be matched to itself as a candidate."""

        if self.left_entity_id == self.right_entity_id:
            raise ValueError("identity candidate cannot match an entity to itself")
        return self


class RelationshipAssertion(BaseModel):
    """Evidence-backed graph relationship assertion."""

    relationship_id: str = Field(min_length=1)
    subject_entity_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_entity_id: str = Field(min_length=1)
    relationship_status: RelationshipStatus = RelationshipStatus.POSSIBLE
    confidence_score: int = Field(default=0, ge=0, le=100)
    evidence_summary: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradictory_evidence_ids: list[str] = Field(default_factory=list)
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
    last_verified: datetime | None = None
    source_family: str | None = None
    jurisdiction: str | None = None
    enrichment_run_id: str | None = None

    @model_validator(mode="after")
    def reject_self_relationship(self) -> RelationshipAssertion:
        """Do not allow a relationship edge from an entity to itself."""

        if self.subject_entity_id == self.object_entity_id:
            raise ValueError("relationship subject and object must differ")
        return self


class AuthorityState(BaseModel):
    """Authority enrichment state for a project or site."""

    authority_state_id: str = Field(min_length=1)
    project_cluster_id: str = Field(min_length=1)
    authority_status: AuthorityStatus = AuthorityStatus.NOT_STARTED
    known_authority_entity_ids: list[str] = Field(default_factory=list)
    candidate_authority_entity_ids: list[str] = Field(default_factory=list)
    missing_authority_roles: list[str] = Field(default_factory=list)
    unresolved_reason: str | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    evidence_record_ids: list[str] = Field(default_factory=list)
    last_enrichment_at: datetime | None = None

    @model_validator(mode="after")
    def require_reason_when_unresolved(self) -> AuthorityState:
        """Require a reason when authority is explicitly unresolved."""

        if (
            self.authority_status == AuthorityStatus.AUTHORITY_UNRESOLVED_WITH_REASON
            and not self.unresolved_reason
        ):
            raise ValueError("unresolved authority state requires unresolved_reason")
        return self


class ProjectCluster(BaseModel):
    """Evidence-backed construction project cluster."""

    project_cluster_id: str = Field(min_length=1)
    project_name: str | None = None
    normalized_address: str | None = None
    apns: list[str] = Field(default_factory=list)
    jurisdiction: str | None = None
    coverage_status: CoverageStatus = CoverageStatus.UNKNOWN_ZONE
    monitoring_status: MonitoringStatus = MonitoringStatus.REFERENCE_ONLY
    cluster_status: ProjectClusterStatus = ProjectClusterStatus.POSSIBLE
    lifecycle_phase: LifecyclePhase = LifecyclePhase.UNKNOWN
    cluster_confidence: int = Field(default=0, ge=0, le=100)
    major_project_probability: int = Field(default=0, ge=0, le=100)
    standalone_probability: int = Field(default=0, ge=0, le=100)
    related_permit_ids: list[str] = Field(default_factory=list)
    related_planning_case_ids: list[str] = Field(default_factory=list)
    related_ceqa_record_ids: list[str] = Field(default_factory=list)
    related_document_ids: list[str] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    known_authority_roles: dict[str, str] = Field(default_factory=dict)
    missing_authority_roles: list[str] = Field(default_factory=list)
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
    last_updated: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def require_cluster_anchor(self) -> ProjectCluster:
        """Require at least one location, identifier, or evidence anchor."""

        if not any(
            [self.project_name, self.normalized_address, self.apns, self.evidence_record_ids]
        ):
            raise ValueError("project cluster requires name, address, APN, or evidence")
        return self


class OpportunitySignal(BaseModel):
    """Evidence-backed commercial or operational opportunity signal."""

    opportunity_id: str = Field(min_length=1)
    category: OpportunityCategory
    opportunity_status: OpportunityStatus = OpportunityStatus.CANDIDATE
    project_cluster_id: str | None = None
    site_entity_id: str | None = None
    related_entity_ids: list[str] = Field(default_factory=list)
    geographic_region: str | None = None
    timing_window: str | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    evidence_summary: str = Field(min_length=1)
    source_record_ids: list[str] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    related_scope_tags: list[str] = Field(default_factory=list)
    lifecycle_phase_basis: LifecyclePhase = LifecyclePhase.UNKNOWN
    market_context_basis: str | None = None
    limitations: list[str] = Field(default_factory=list)
    first_seen: datetime = Field(default_factory=utc_now)
    last_updated: datetime = Field(default_factory=utc_now)
    stale_after: datetime | None = None

    @model_validator(mode="after")
    def require_opportunity_target(self) -> OpportunitySignal:
        """Require an opportunity to point at a project, site, or related entity."""

        if not any([self.project_cluster_id, self.site_entity_id, self.related_entity_ids]):
            raise ValueError("opportunity requires a project, site, or related entity target")
        return self


class RuntimeEvent(BaseModel):
    """Runtime event emitted by source refresh, enrichment, graph, or UI systems."""

    event_id: str = Field(min_length=1)
    event_type: RuntimeEventType
    severity: RuntimeEventSeverity = RuntimeEventSeverity.LOW
    created_at: datetime = Field(default_factory=utc_now)
    source_service: str = Field(min_length=1)
    correlation_id: str | None = None
    causation_id: str | None = None
    operational_region_id: str | None = None
    jurisdiction: str | None = None
    entity_refs: list[str] = Field(default_factory=list)
    project_cluster_refs: list[str] = Field(default_factory=list)
    source_record_refs: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(min_length=1)
    confidence_delta: int | None = Field(default=None, ge=-100, le=100)
    requires_user_attention: bool = False


class WatchlistItem(BaseModel):
    """User-selected object receiving enhanced attention."""

    watchlist_item_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    target_type: EntityType | str
    target_id: str = Field(min_length=1)
    status: WatchlistStatus = WatchlistStatus.ACTIVE
    priority: int = Field(default=50, ge=0, le=100)
    alert_enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    notes: str | None = None
