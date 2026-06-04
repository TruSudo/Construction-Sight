"""Artifact-based identity resolution memory models.

This module defines the first governed identity-resolution memory contract for
ConstructionSight. It is intentionally deterministic and side-effect free:
no persistence, no automatic graph propagation, and no AI/API integration live
here. Runtime services may later use these schemas to build auditable project
identity convergence and ripple workflows.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class ArtifactTier(StrEnum):
    """Identity-resolution strength tier for observed artifacts."""

    NEAR_UNIQUE = "near_unique"
    STRONG_RELATIONAL = "strong_relational"
    CONTEXTUAL = "contextual"
    WEAK_ASSISTIVE = "weak_assistive"


class IdentityArtifactType(StrEnum):
    """Artifact types used to resolve project identity across public records."""

    APN = "apn"
    PARCEL_GEOMETRY = "parcel_geometry"
    CEQA_SCH_NUMBER = "ceqa_sch_number"
    PLANNING_CASE_NUMBER = "planning_case_number"
    PERMIT_NUMBER = "permit_number"
    TRACT_MAP_NUMBER = "tract_map_number"
    APPLICANT_LLC = "applicant_llc"
    OWNER_MAILING_ADDRESS = "owner_mailing_address"
    DEVELOPER_ENTITY = "developer_entity"
    CONSULTANT_ENTITY = "consultant_entity"
    EXACT_SITE_ADDRESS = "exact_site_address"
    LEGAL_DESCRIPTION = "legal_description"
    PROJECT_TITLE = "project_title"
    PROJECT_TITLE_FRAGMENT = "project_title_fragment"
    LAND_USE_TYPE = "land_use_type"
    ACREAGE = "acreage"
    SQUARE_FOOTAGE = "square_footage"
    VALUATION = "valuation"
    CITY_DISTRICT = "city_district"
    HEARING_DATE = "hearing_date"
    GENERIC_PROJECT_WORD = "generic_project_word"
    BROAD_DEVELOPER_NAME = "broad_developer_name"
    PARTIAL_ADDRESS = "partial_address"
    NEIGHBORHOOD_NAME = "neighborhood_name"
    INFORMAL_ALIAS = "informal_alias"


class ResolutionTargetKind(StrEnum):
    """Identity target kinds supported by the first resolution phase."""

    PROJECT = "project"
    ENTITY = "entity"
    SITE = "site"
    CONTACT = "contact"


class ResolutionDecisionType(StrEnum):
    """Possible deterministic decisions for an identity-resolution candidate."""

    AUTO_LINK = "auto_link"
    NEEDS_REVIEW = "needs_review"
    CREATE_NEW_IDENTITY = "create_new_identity"
    REJECT_MATCH = "reject_match"
    QUEUE_FOLLOWUP_SEARCH = "queue_followup_search"


class MemoryLifecycleStatus(StrEnum):
    """Lifecycle state for governed identity-resolution memory."""

    OBSERVED = "observed"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"


class MemoryKind(StrEnum):
    """Governed memory categories used by identity-resolution workflows."""

    IDENTITY_ARTIFACT = "identity_artifact"
    SOURCE_LAYOUT = "source_layout"
    NORMALIZATION_HINT = "normalization_hint"
    SEARCH_ALIAS = "search_alias"
    RELATIONSHIP_HINT = "relationship_hint"


class RippleEventType(StrEnum):
    """Auditable downstream effects caused by new artifact observations."""

    ARTIFACT_OBSERVED = "artifact_observed"
    FINGERPRINT_CONFIDENCE_CHANGED = "fingerprint_confidence_changed"
    ALIAS_CANDIDATE_CREATED = "alias_candidate_created"
    FOLLOWUP_SEARCH_QUEUED = "followup_search_queued"
    RELATIONSHIP_RECHECK_REQUESTED = "relationship_recheck_requested"
    MEMORY_PROMOTION_REVIEW_REQUIRED = "memory_promotion_review_required"


ARTIFACT_TYPE_TIERS: dict[IdentityArtifactType, ArtifactTier] = {
    IdentityArtifactType.APN: ArtifactTier.NEAR_UNIQUE,
    IdentityArtifactType.PARCEL_GEOMETRY: ArtifactTier.NEAR_UNIQUE,
    IdentityArtifactType.CEQA_SCH_NUMBER: ArtifactTier.NEAR_UNIQUE,
    IdentityArtifactType.PLANNING_CASE_NUMBER: ArtifactTier.NEAR_UNIQUE,
    IdentityArtifactType.PERMIT_NUMBER: ArtifactTier.NEAR_UNIQUE,
    IdentityArtifactType.TRACT_MAP_NUMBER: ArtifactTier.NEAR_UNIQUE,
    IdentityArtifactType.APPLICANT_LLC: ArtifactTier.STRONG_RELATIONAL,
    IdentityArtifactType.OWNER_MAILING_ADDRESS: ArtifactTier.STRONG_RELATIONAL,
    IdentityArtifactType.DEVELOPER_ENTITY: ArtifactTier.STRONG_RELATIONAL,
    IdentityArtifactType.CONSULTANT_ENTITY: ArtifactTier.STRONG_RELATIONAL,
    IdentityArtifactType.EXACT_SITE_ADDRESS: ArtifactTier.STRONG_RELATIONAL,
    IdentityArtifactType.LEGAL_DESCRIPTION: ArtifactTier.STRONG_RELATIONAL,
    IdentityArtifactType.PROJECT_TITLE: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.PROJECT_TITLE_FRAGMENT: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.LAND_USE_TYPE: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.ACREAGE: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.SQUARE_FOOTAGE: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.VALUATION: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.CITY_DISTRICT: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.HEARING_DATE: ArtifactTier.CONTEXTUAL,
    IdentityArtifactType.GENERIC_PROJECT_WORD: ArtifactTier.WEAK_ASSISTIVE,
    IdentityArtifactType.BROAD_DEVELOPER_NAME: ArtifactTier.WEAK_ASSISTIVE,
    IdentityArtifactType.PARTIAL_ADDRESS: ArtifactTier.WEAK_ASSISTIVE,
    IdentityArtifactType.NEIGHBORHOOD_NAME: ArtifactTier.WEAK_ASSISTIVE,
    IdentityArtifactType.INFORMAL_ALIAS: ArtifactTier.WEAK_ASSISTIVE,
}

ARTIFACT_TIER_WEIGHTS: dict[ArtifactTier, int] = {
    ArtifactTier.NEAR_UNIQUE: 48,
    ArtifactTier.STRONG_RELATIONAL: 27,
    ArtifactTier.CONTEXTUAL: 13,
    ArtifactTier.WEAK_ASSISTIVE: 4,
}


def artifact_tier(artifact_type: IdentityArtifactType) -> ArtifactTier:
    """Return the configured strength tier for an artifact type."""

    return ARTIFACT_TYPE_TIERS[artifact_type]


def artifact_weight(artifact_type: IdentityArtifactType) -> int:
    """Return the deterministic scoring weight for an artifact type."""

    return ARTIFACT_TIER_WEIGHTS[artifact_tier(artifact_type)]


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("artifact values must not be blank")
    return stripped


def _require_unique_values(values: Iterable[str], field_name: str) -> None:
    value_list = list(values)
    if len(value_list) != len(set(value_list)):
        raise ValueError(f"{field_name} must contain unique values")


class ArtifactObservation(BaseModel):
    """One provenance-bound observation of an identity artifact in a public source."""

    observation_id: str = Field(min_length=1)
    artifact_type: IdentityArtifactType
    raw_value: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_family: str | None = None
    source_record_id: str | None = None
    jurisdiction: str | None = None
    observed_field: str | None = None
    evidence_record_id: str | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    observed_at: datetime = Field(default_factory=utc_now)
    notes: str | None = None

    @field_validator("raw_value", "normalized_value")
    @classmethod
    def strip_artifact_values(cls, value: str) -> str:
        """Strip and reject blank artifact values."""

        return _strip_required(value)

    @property
    def tier(self) -> ArtifactTier:
        """Return the artifact's configured identity-resolution tier."""

        return artifact_tier(self.artifact_type)

    @property
    def weight(self) -> int:
        """Return the artifact's configured deterministic scoring weight."""

        return artifact_weight(self.artifact_type)


class IdentityFingerprint(BaseModel):
    """Artifact constellation attached to a candidate project identity."""

    fingerprint_id: str = Field(min_length=1)
    target_identity_id: str = Field(min_length=1)
    target_kind: ResolutionTargetKind = ResolutionTargetKind.PROJECT
    artifact_observations: list[ArtifactObservation] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    notes: str | None = None

    @model_validator(mode="after")
    def require_observations_and_unique_observation_ids(self) -> IdentityFingerprint:
        """Require at least one artifact observation and reject duplicate IDs."""

        if not self.artifact_observations:
            raise ValueError("identity fingerprint requires at least one artifact observation")
        observation_ids = [observation.observation_id for observation in self.artifact_observations]
        _require_unique_values(observation_ids, "artifact observation IDs")
        _require_unique_values(self.evidence_record_ids, "evidence record IDs")
        return self

    @property
    def artifact_types(self) -> set[IdentityArtifactType]:
        """Return the artifact types represented in this fingerprint."""

        return {observation.artifact_type for observation in self.artifact_observations}

    @property
    def near_unique_observations(self) -> list[ArtifactObservation]:
        """Return near-unique observations suitable as primary identity anchors."""

        return [
            observation
            for observation in self.artifact_observations
            if observation.tier == ArtifactTier.NEAR_UNIQUE
        ]


class ArtifactMatch(BaseModel):
    """Evidence-bound artifact match supporting convergence between identities."""

    artifact_type: IdentityArtifactType
    left_observation_id: str = Field(min_length=1)
    right_observation_id: str = Field(min_length=1)
    left_value: str = Field(min_length=1)
    right_value: str = Field(min_length=1)
    match_strength: int = Field(ge=0, le=100)
    source_families: list[str] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)

    @field_validator("left_value", "right_value")
    @classmethod
    def strip_match_values(cls, value: str) -> str:
        """Strip and reject blank match values."""

        return _strip_required(value)

    @model_validator(mode="after")
    def reject_self_match_and_duplicate_sources(self) -> ArtifactMatch:
        """Reject self matches and duplicate evidence/source references."""

        if self.left_observation_id == self.right_observation_id:
            raise ValueError("artifact match cannot compare an observation to itself")
        _require_unique_values(self.source_families, "source families")
        _require_unique_values(self.evidence_record_ids, "evidence record IDs")
        return self

    @property
    def tier(self) -> ArtifactTier:
        """Return the match tier derived from its artifact type."""

        return artifact_tier(self.artifact_type)

    @property
    def contribution(self) -> int:
        """Return this match's weighted score contribution."""

        return round(artifact_weight(self.artifact_type) * (self.match_strength / 100))


class ArtifactConflict(BaseModel):
    """Evidence-bound artifact conflict weighing against identity convergence."""

    artifact_type: IdentityArtifactType
    left_value: str = Field(min_length=1)
    right_value: str = Field(min_length=1)
    conflict_strength: int = Field(ge=0, le=100)
    evidence_record_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)

    @field_validator("left_value", "right_value")
    @classmethod
    def strip_conflict_values(cls, value: str) -> str:
        """Strip and reject blank conflict values."""

        return _strip_required(value)

    @model_validator(mode="after")
    def reject_duplicate_evidence_ids(self) -> ArtifactConflict:
        """Reject duplicate evidence IDs."""

        _require_unique_values(self.evidence_record_ids, "evidence record IDs")
        return self

    @property
    def tier(self) -> ArtifactTier:
        """Return the conflict tier derived from its artifact type."""

        return artifact_tier(self.artifact_type)

    @property
    def penalty(self) -> int:
        """Return this conflict's weighted score penalty."""

        return round(artifact_weight(self.artifact_type) * (self.conflict_strength / 100))


def calculate_resolution_score(
    supporting_matches: list[ArtifactMatch],
    conflicts: list[ArtifactConflict],
) -> int:
    """Calculate a deterministic convergence score from artifact support and conflicts."""

    support_score = sum(match.contribution for match in supporting_matches)
    conflict_penalty = sum(conflict.penalty for conflict in conflicts)
    source_families = {
        source_family
        for match in supporting_matches
        for source_family in match.source_families
        if source_family
    }
    independence_bonus = min(10, max(0, len(source_families) - 1) * 5)
    score = support_score + independence_bonus - conflict_penalty
    return max(0, min(100, score))


class IdentityResolutionCandidate(BaseModel):
    """Artifact-driven candidate match between two project identities."""

    candidate_id: str = Field(min_length=1)
    left_identity_id: str = Field(min_length=1)
    right_identity_id: str = Field(min_length=1)
    target_kind: ResolutionTargetKind = ResolutionTargetKind.PROJECT
    supporting_matches: list[ArtifactMatch] = Field(default_factory=list)
    conflicts: list[ArtifactConflict] = Field(default_factory=list)
    evidence_summary: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    review_required: bool = True

    @model_validator(mode="after")
    def validate_candidate_scope(self) -> IdentityResolutionCandidate:
        """Reject self-resolution candidates and candidates with no evaluable artifacts."""

        if self.left_identity_id == self.right_identity_id:
            raise ValueError("identity resolution candidate cannot compare an identity to itself")
        if not self.supporting_matches and not self.conflicts:
            raise ValueError("identity resolution candidate requires support or conflict artifacts")
        return self

    @property
    def resolution_score(self) -> int:
        """Return the deterministic convergence score."""

        return calculate_resolution_score(self.supporting_matches, self.conflicts)

    @property
    def has_near_unique_support(self) -> bool:
        """Return true when at least one near-unique artifact supports convergence."""

        return any(match.tier == ArtifactTier.NEAR_UNIQUE for match in self.supporting_matches)

    @property
    def has_near_unique_conflict(self) -> bool:
        """Return true when a near-unique artifact conflicts strongly."""

        return any(
            conflict.tier == ArtifactTier.NEAR_UNIQUE and conflict.conflict_strength >= 80
            for conflict in self.conflicts
        )

    @property
    def has_only_weak_support(self) -> bool:
        """Return true when all positive support is weak and no stronger artifacts exist."""

        return bool(self.supporting_matches) and all(
            match.tier == ArtifactTier.WEAK_ASSISTIVE for match in self.supporting_matches
        )

    @property
    def recommended_decision(self) -> ResolutionDecisionType:
        """Return the safe deterministic next action for this candidate."""

        if self.has_near_unique_conflict:
            if self.resolution_score < 70:
                return ResolutionDecisionType.REJECT_MATCH
            return ResolutionDecisionType.NEEDS_REVIEW
        if self.has_only_weak_support:
            return ResolutionDecisionType.QUEUE_FOLLOWUP_SEARCH
        if not self.supporting_matches:
            return ResolutionDecisionType.CREATE_NEW_IDENTITY
        if self.resolution_score >= 90 and self.has_near_unique_support and not self.conflicts:
            return ResolutionDecisionType.AUTO_LINK
        if self.resolution_score >= 70:
            return ResolutionDecisionType.NEEDS_REVIEW
        if self.resolution_score >= 35:
            return ResolutionDecisionType.QUEUE_FOLLOWUP_SEARCH
        return ResolutionDecisionType.CREATE_NEW_IDENTITY


class SourceLayoutMemory(BaseModel):
    """Governed memory describing where identity artifacts appear within a source."""

    source_layout_memory_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_family: str = Field(min_length=1)
    jurisdiction: str | None = None
    artifact_field_hints: dict[IdentityArtifactType, list[str]] = Field(default_factory=dict)
    status: MemoryLifecycleStatus = MemoryLifecycleStatus.CANDIDATE
    evidence_record_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    notes: str | None = None

    @model_validator(mode="after")
    def require_artifact_field_hints(self) -> SourceLayoutMemory:
        """Require source-layout memory to identify artifact locations."""

        if not self.artifact_field_hints:
            raise ValueError("source-layout memory requires at least one artifact field hint")
        for artifact_type, field_hints in self.artifact_field_hints.items():
            if not field_hints:
                raise ValueError(
                    f"artifact field hints for {artifact_type.value} must not be empty"
                )
            _require_unique_values(field_hints, f"artifact field hints for {artifact_type.value}")
        _require_unique_values(self.evidence_record_ids, "evidence record IDs")
        return self


class MemoryCandidate(BaseModel):
    """Governed reusable memory candidate created from artifact observations."""

    memory_id: str = Field(min_length=1)
    memory_kind: MemoryKind
    status: MemoryLifecycleStatus = MemoryLifecycleStatus.CANDIDATE
    proposed_value: str = Field(min_length=1)
    scope_jurisdiction: str | None = None
    scope_source_family: str | None = None
    supporting_observation_ids: list[str] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    promotion_requirements: list[str] = Field(default_factory=list)
    raw_evidence_overwrite_allowed: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    notes: str | None = None

    @field_validator("proposed_value")
    @classmethod
    def strip_proposed_value(cls, value: str) -> str:
        """Strip and reject blank proposed memory values."""

        return _strip_required(value)

    @model_validator(mode="after")
    def enforce_governed_memory_rules(self) -> MemoryCandidate:
        """Prevent raw-evidence overwrite and require evidence before promotion."""

        if self.raw_evidence_overwrite_allowed:
            raise ValueError("identity memory may never overwrite raw evidence")
        _require_unique_values(self.supporting_observation_ids, "supporting observation IDs")
        _require_unique_values(self.evidence_record_ids, "evidence record IDs")
        _require_unique_values(self.promotion_requirements, "promotion requirements")
        if self.status == MemoryLifecycleStatus.PROMOTED and not all(
            [self.supporting_observation_ids, self.evidence_record_ids, self.promotion_requirements]
        ):
            raise ValueError("promoted memory requires observations, evidence, and promotion rules")
        return self


class RippleEvent(BaseModel):
    """Explicit auditable downstream event generated by identity-resolution memory."""

    ripple_event_id: str = Field(min_length=1)
    event_type: RippleEventType
    triggering_observation_id: str | None = None
    triggering_candidate_id: str | None = None
    target_identity_id: str | None = None
    project_cluster_id: str | None = None
    queued_actions: list[ResolutionDecisionType] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    message: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    requires_user_attention: bool = False

    @model_validator(mode="after")
    def require_trigger_and_target(self) -> RippleEvent:
        """Require ripple events to identify both cause and affected target."""

        if not any([self.triggering_observation_id, self.triggering_candidate_id]):
            raise ValueError("ripple event requires a triggering observation or candidate")
        if not any([self.target_identity_id, self.project_cluster_id]):
            raise ValueError("ripple event requires a target identity or project cluster")
        _require_unique_values(self.evidence_record_ids, "evidence record IDs")
        return self
