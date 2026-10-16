"""Shared investigation writes over the existing evidence, graph and revision store.

Source-anchored investigations are unresolved accounts, not verified project identities.
Correlation uses the existing artifact resolver and never merges investigations.
The caller owns the outer transaction; a failed observation rolls back its own writes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constructionsight.contractor_identity_service import build_contractor_identity
from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.intelligence.artifact_identity import (
    ArtifactObservation,
    IdentityArtifactType,
    IdentityFingerprint,
    IdentityResolutionCandidate,
    ResolutionTargetKind,
    canonical_artifact_observation_id,
    canonical_identity_fingerprint_id,
    normalize_artifact_value,
)
from constructionsight.intelligence.artifact_resolution_service import ArtifactResolutionService
from constructionsight.intelligence.graph_service import IntelligenceGraphService
from constructionsight.intelligence.schemas import (
    EntityIdentity,
    EntityType,
    EvidenceRecord,
    ProjectCluster,
    ProjectClusterStatus,
    RelationshipAssertion,
    RelationshipStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from constructionsight.storage.database import ensure_database_transaction
from constructionsight.storage.intelligence_store import IntelligenceStore


def _identity(namespace: str, value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"{namespace}:{hashlib.sha256(canonical.encode()).hexdigest()}"


def source_record_identity(evidence: EvidenceRecord) -> str:
    return _identity(
        "source-record",
        [
            evidence.source_family,
            evidence.source_name,
            evidence.source_record_id,
        ],
    )


def observation_receipt_identity(source_id: str, evidence_id: str) -> str:
    return _identity("event:investigation-observation", [source_id, evidence_id])


class InvestigationObservation(BaseModel):
    """A source-specific normalization, bound to immutable retained evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence: EvidenceRecord
    title: str | None = None
    county: str | None = None
    artifacts: dict[IdentityArtifactType, list[str]] = Field(default_factory=dict)
    parties: list[Entity] = Field(default_factory=list, max_length=250)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode="after")
    def require_source_identity(self) -> InvestigationObservation:
        # Revalidate even models constructed or mutated outside Pydantic validation.
        evidence = EvidenceRecord.model_validate(self.evidence.model_dump(mode="json"))
        for value in (evidence.source_family, evidence.source_record_id, evidence.source_name):
            if not value or not value.strip():
                raise ValueError("observation requires source family, name and record identity")
        for timestamp in (evidence.retrieved_at, evidence.observed_at):
            if timestamp is not None and timestamp.utcoffset() is None:
                raise ValueError("observation timestamps must include a timezone")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("a geographic observation requires both coordinates")
        for values in self.artifacts.values():
            if not values or any(not value.strip() for value in values):
                raise ValueError("artifact values must be nonempty source claims")
            if len(values) != len(set(values)):
                raise ValueError("duplicate artifact values are not allowed")
        if sum(map(len, self.artifacts.values())) > 500:
            raise ValueError("an observation may contain at most 500 identity artifacts")
        return self

    @property
    def source_entity_id(self) -> str:
        return source_record_identity(self.evidence)

    @property
    def investigation_id(self) -> str:
        return _identity("investigation", self.source_entity_id)

    @property
    def receipt_id(self) -> str:
        return observation_receipt_identity(self.source_entity_id, self.evidence.evidence_id)

    @property
    def effective_at(self) -> datetime:
        return self.evidence.observed_at or self.evidence.retrieved_at


class NoCorrelationEvidence(ValueError):
    """The retained inputs do not establish a supported candidate."""


class ReviewedCorrelation(ValueError):
    """Automatic correlation cannot change an existing reviewed decision."""


class InvestigationService:
    """Compose existing stores without a second matching engine or database."""

    def __init__(self, store: IntelligenceStore) -> None:
        self.store = store
        self.graph = IntelligenceGraphService(store, source_service="investigation_service")

    def _begin_savepoint(self) -> None:
        ensure_database_transaction(self.store.session)

    def ingest(self, observation: InvestigationObservation) -> ProjectCluster:
        """Atomically retain an observation, source identity, investigation and event."""

        observation = InvestigationObservation.model_validate(
            observation.model_dump(mode="json", round_trip=True)
        )
        self._begin_savepoint()
        previous_receipt = self.store.get_runtime_event(observation.receipt_id)
        payload = observation.model_dump(mode="json", round_trip=True)
        if previous_receipt is not None:
            if previous_receipt.payload != payload:
                raise ValueError("retained observation cannot be rebound to changed normalization")
            cluster = self.store.get_project_cluster(observation.investigation_id)
            if cluster is None:
                raise ValueError("observation receipt has no investigation")
            # Upgrade derived projections without recreating retained source facts.
            with self.store.session.begin_nested():
                self._update_source_parties(self.current_observation(observation.source_entity_id))
            return cluster

        self._begin_savepoint()
        with self.store.session.begin_nested():
            self.graph.record_evidence(observation.evidence)
            cluster = self.store.get_project_cluster(observation.investigation_id)
            entity = self.store.get_entity(observation.source_entity_id)
            latest = entity is None or observation.effective_at >= entity.last_seen
            evidence_ids = sorted(
                set(
                    (cluster.evidence_record_ids if cluster else [])
                    + [observation.evidence.evidence_id]
                )
            )
            if cluster is None:
                cluster = ProjectCluster(
                    project_cluster_id=observation.investigation_id,
                    evidence_record_ids=evidence_ids,
                    cluster_status=ProjectClusterStatus.STANDALONE,
                    first_seen=observation.effective_at,
                    last_seen=observation.effective_at,
                    last_updated=observation.evidence.retrieved_at,
                )
            changes: dict[str, Any] = {
                "evidence_record_ids": evidence_ids,
                "first_seen": min(cluster.first_seen, observation.effective_at),
                "last_seen": max(cluster.last_seen, observation.effective_at),
                "last_updated": max(cluster.last_updated, observation.evidence.retrieved_at),
            }
            if latest:
                changes.update(
                    project_name=observation.title,
                    normalized_address=next(
                        iter(
                            observation.artifacts.get(IdentityArtifactType.EXACT_SITE_ADDRESS, [])
                        ),
                        None,
                    ),
                    apns=observation.artifacts.get(IdentityArtifactType.APN, []),
                    jurisdiction=observation.evidence.jurisdiction,
                )
            cluster = ProjectCluster.model_validate(cluster.model_copy(update=changes).model_dump())
            self.graph.upsert_project_cluster(cluster)
            if entity is None:
                entity = EntityIdentity(
                    entity_id=observation.source_entity_id,
                    entity_type={
                        "ceqa": EntityType.CEQA_RECORD,
                        "permit": EntityType.PERMIT,
                        "parcel": EntityType.PARCEL,
                        "planning": EntityType.PLANNING_CASE,
                    }.get(observation.evidence.record_type, EntityType.DOCUMENT),
                    canonical_name=observation.title or str(observation.evidence.source_record_id),
                    first_seen=observation.effective_at,
                    last_seen=observation.effective_at,
                )
            entity_changes: dict[str, Any] = {
                "evidence_record_ids": evidence_ids,
                "first_seen": min(entity.first_seen, observation.effective_at),
                "last_seen": max(entity.last_seen, observation.effective_at),
            }
            if latest:
                entity_changes.update(
                    canonical_name=observation.title or str(observation.evidence.source_record_id),
                    identifiers={"current_observation_receipt": observation.receipt_id},
                    source_names=[observation.evidence.source_name],
                    related_source_record_ids=[str(observation.evidence.source_record_id)],
                )
            self.graph.upsert_entity(
                EntityIdentity.model_validate(entity.model_copy(update=entity_changes).model_dump())
            )
            self.graph.upsert_relationship(
                RelationshipAssertion(
                    relationship_id=_identity(
                        "relationship:source-investigation", observation.source_entity_id
                    ),
                    subject_entity_id=observation.source_entity_id,
                    predicate="source_record_for_unresolved_investigation",
                    object_entity_id=observation.investigation_id,
                    relationship_status=RelationshipStatus.UNRESOLVED,
                    supporting_evidence_ids=evidence_ids,
                    evidence_summary=(
                        "Source record anchors an investigation; project identity unverified."
                    ),
                    first_seen=cluster.first_seen,
                    last_seen=cluster.last_seen,
                )
            )
            if latest:
                self._update_source_parties(observation)
                related = {
                    relationship.relationship_id: relationship
                    for target in (observation.investigation_id, observation.source_entity_id)
                    for relationship in self.store.list_relationships_for_target(target)
                }
                for relationship in related.values():
                    if (
                        relationship.predicate
                        in {
                            "possible_same_project_requires_review",
                            "parcel_location_candidate",
                        }
                        and observation.evidence.evidence_id
                        not in relationship.supporting_evidence_ids
                    ):
                        if relationship.relationship_status not in {
                            RelationshipStatus.POSSIBLE,
                            RelationshipStatus.CONFLICTING,
                        }:
                            if relationship.relationship_status is not RelationshipStatus.STALE:
                                self._request_relationship_review(relationship, observation)
                            continue
                        self.graph.upsert_relationship(
                            RelationshipAssertion.model_validate(
                                relationship.model_copy(
                                    update={
                                        "relationship_status": RelationshipStatus.STALE,
                                    }
                                ).model_dump()
                            )
                        )
            self.store.add_runtime_event(
                RuntimeEvent(
                    event_id=observation.receipt_id,
                    event_type=RuntimeEventType.SOURCE_RECORD_CHANGED,
                    source_service="investigation_observation",
                    created_at=observation.evidence.retrieved_at,
                    entity_refs=[observation.source_entity_id],
                    project_cluster_refs=[observation.investigation_id],
                    source_record_refs=[observation.evidence.evidence_id],
                    payload=payload,
                    message="Source observation incorporated; identity remains unverified.",
                )
            )
        return cluster

    def _update_source_parties(self, observation: InvestigationObservation) -> None:
        active_relationships = set()
        for party in observation.parties:
            party_id = _identity("source-party", [observation.source_entity_id, party.entity_key])
            relationship_id = _identity("relationship:source-party", party_id)
            previous = self.store.get_relationship(relationship_id)
            active_relationships.add(relationship_id)
            if previous is not None and previous.relationship_status not in {
                RelationshipStatus.POSSIBLE,
                RelationshipStatus.STALE,
            }:
                if observation.evidence.evidence_id not in previous.supporting_evidence_ids:
                    self._request_relationship_review(previous, observation)
                continue
            existing = self.store.get_entity(party_id)
            identifiers = {"source_entity_key": party.entity_key}
            if party.license_number:
                identifiers["source_claimed_license_number"] = party.license_number
            if (
                party.role in {PartyRole.CONTRACTOR, PartyRole.GENERAL_CONTRACTOR}
                and party.state.upper() == "CA"
            ):
                assessment = build_contractor_identity(
                    display_name=party.name,
                    license_number=party.license_number,
                    county=party.county or observation.county,
                ).model_copy(update={"observed_at": observation.effective_at})
                assessment_id = _identity(
                    "event:source-contractor-assessment",
                    [
                        party_id,
                        observation.receipt_id,
                        assessment.model_dump(mode="json"),
                    ],
                )
                self.store.add_runtime_event(
                    RuntimeEvent(
                        event_id=assessment_id,
                        event_type=RuntimeEventType.ENTITY_UPDATED,
                        source_service="investigation_contractor_assessment",
                        created_at=observation.evidence.retrieved_at,
                        source_record_refs=[observation.evidence.evidence_id],
                        payload={
                            "candidate": assessment.model_dump(mode="json"),
                            "source_party_id": party_id,
                            "accepted_entity_merge": False,
                            "license_independently_verified": False,
                        },
                        message="Contractor assessment retained; no verification granted.",
                    )
                )
                identifiers["contractor_assessment_event"] = assessment_id
            kind = next(
                (item for item in EntityType if item.value == party.role.value), EntityType.UNKNOWN
            )
            entity = EntityIdentity(
                entity_id=party_id,
                entity_type=kind,
                canonical_name=party.name,
                identifiers=identifiers,
                addresses=[party.business_address] if party.business_address else [],
                jurisdictions=[party.jurisdiction] if party.jurisdiction else [],
                evidence_record_ids=[observation.evidence.evidence_id],
                source_names=[observation.evidence.source_name],
                related_source_record_ids=[str(observation.evidence.source_record_id)],
                first_seen=existing.first_seen if existing else observation.effective_at,
                last_seen=observation.effective_at,
            )
            self.graph.upsert_entity(entity)
            self.graph.upsert_relationship(
                RelationshipAssertion(
                    relationship_id=relationship_id,
                    subject_entity_id=party_id,
                    object_entity_id=observation.investigation_id,
                    predicate=f"source_claimed_{party.role.value}",
                    relationship_status=RelationshipStatus.POSSIBLE,
                    supporting_evidence_ids=[observation.evidence.evidence_id],
                    evidence_summary="Source-claimed participant role; not independently verified.",
                    first_seen=previous.first_seen if previous else observation.effective_at,
                    last_seen=observation.effective_at,
                )
            )
        for relationship in self.store.list_relationships_for_target(observation.investigation_id):
            if (
                relationship.predicate.startswith("source_claimed_")
                and relationship.relationship_id not in active_relationships
            ):
                if relationship.relationship_status is not RelationshipStatus.POSSIBLE:
                    if relationship.relationship_status is not RelationshipStatus.STALE:
                        self._request_relationship_review(relationship, observation)
                    continue
                self.graph.upsert_relationship(
                    RelationshipAssertion.model_validate(
                        relationship.model_copy(
                            update={
                                "relationship_status": RelationshipStatus.STALE,
                            }
                        ).model_dump()
                    )
                )

    def _request_relationship_review(
        self,
        relationship: RelationshipAssertion,
        observation: InvestigationObservation,
    ) -> None:
        self.store.add_runtime_event(
            RuntimeEvent(
                event_id=_identity(
                    "event:relationship-review",
                    [
                        relationship.relationship_id,
                        observation.receipt_id,
                    ],
                ),
                event_type=RuntimeEventType.RELATIONSHIP_UPDATED,
                source_service="investigation_review_queue",
                created_at=observation.evidence.retrieved_at,
                project_cluster_refs=[observation.investigation_id],
                source_record_refs=[observation.evidence.evidence_id],
                payload={
                    "relationship_id": relationship.relationship_id,
                    "reason": "New source observation requires review of a preserved decision.",
                },
                message="Review required; the existing relationship decision was preserved.",
                requires_user_attention=True,
            )
        )

    def current_observation(self, source_entity_id: str) -> InvestigationObservation:
        entity = self.store.get_entity(source_entity_id)
        if entity is None:
            raise ValueError("unknown source record")
        receipt = self.store.get_runtime_event(
            entity.identifiers.get("current_observation_receipt", "")
        )
        if receipt is None:
            raise ValueError("source record has no retained observation receipt")
        return InvestigationObservation.model_validate(receipt.payload)

    def correlate(self, left_source_id: str, right_source_id: str) -> IdentityResolutionCandidate:
        """Retain an explainable candidate; common location never verifies identity."""

        self._begin_savepoint()
        left = self.current_observation(left_source_id)
        right = self.current_observation(right_source_id)
        county = (left.county or "").strip().casefold().removesuffix(" county")
        other_county = (right.county or "").strip().casefold().removesuffix(" county")
        if not county or county != other_county:
            raise NoCorrelationEvidence("correlation requires the same explicitly known county")
        local_scope = bool(left.evidence.jurisdiction) and (
            left.evidence.jurisdiction == right.evidence.jurisdiction
        )
        candidate = ArtifactResolutionService().resolve_fingerprints(
            self._fingerprint(left, local_scope), self._fingerprint(right, local_scope)
        )
        if not candidate.supporting_matches:
            raise NoCorrelationEvidence(
                "conflicting identifiers alone do not establish a candidate relationship"
            )
        evidence_ids = sorted({left.evidence.evidence_id, right.evidence.evidence_id})
        status = (
            RelationshipStatus.CONFLICTING if candidate.conflicts else RelationshipStatus.POSSIBLE
        )
        relationship_id = _identity("relationship:investigation-candidate", candidate.candidate_id)
        previous = self.store.get_relationship(relationship_id)
        # A reviewed relationship must not be silently reopened by automatic processing.
        if previous is not None and previous.relationship_status not in {
            RelationshipStatus.POSSIBLE,
            RelationshipStatus.CONFLICTING,
            RelationshipStatus.STALE,
        }:
            raise ReviewedCorrelation(
                "reviewed relationship requires the authorized review workflow"
            )
        candidate = candidate.model_copy(
            update={
                "created_at": max(left.evidence.retrieved_at, right.evidence.retrieved_at),
            }
        )
        self._begin_savepoint()
        with self.store.session.begin_nested():
            self.graph.upsert_relationship(
                RelationshipAssertion(
                    relationship_id=relationship_id,
                    subject_entity_id=candidate.left_identity_id,
                    predicate="possible_same_project_requires_review",
                    object_entity_id=candidate.right_identity_id,
                    relationship_status=status,
                    confidence_score=candidate.resolution_score,
                    supporting_evidence_ids=evidence_ids,
                    contradictory_evidence_ids=evidence_ids if candidate.conflicts else [],
                    evidence_summary=candidate.evidence_summary,
                    first_seen=previous.first_seen
                    if previous
                    else min(left.effective_at, right.effective_at),
                    last_seen=max(left.effective_at, right.effective_at),
                )
            )
            self.store.add_runtime_event(
                RuntimeEvent(
                    event_id=_identity(
                        "event:investigation-candidate",
                        [
                            candidate.candidate_id,
                            evidence_ids,
                        ],
                    ),
                    event_type=RuntimeEventType.RELATIONSHIP_UPDATED,
                    source_service="investigation_correlation",
                    created_at=candidate.created_at,
                    project_cluster_refs=[candidate.left_identity_id, candidate.right_identity_id],
                    source_record_refs=evidence_ids,
                    payload=candidate.model_dump(mode="json"),
                    message="Artifact candidate retained; no identities merged or verified.",
                )
            )
        return candidate

    @staticmethod
    def _fingerprint(
        observation: InvestigationObservation,
        local_scope: bool,
    ) -> IdentityFingerprint:
        evidence = observation.evidence
        artifacts: list[ArtifactObservation] = []
        for kind, values in sorted(observation.artifacts.items()):
            if (
                kind
                in {IdentityArtifactType.PERMIT_NUMBER, IdentityArtifactType.PLANNING_CASE_NUMBER}
                and not local_scope
            ):
                continue
            for value in values:
                normalized = normalize_artifact_value(kind, value)
                artifacts.append(
                    ArtifactObservation(
                        observation_id=canonical_artifact_observation_id(
                            artifact_type=kind,
                            normalized_value=normalized,
                            source_name=evidence.source_name,
                            source_family=evidence.source_family,
                            source_record_id=evidence.source_record_id,
                            jurisdiction=evidence.jurisdiction,
                            observed_field=kind.value,
                            evidence_record_id=evidence.evidence_id,
                        ),
                        artifact_type=kind,
                        normalized_value=normalized,
                        source_name=evidence.source_name,
                        source_family=evidence.source_family,
                        source_record_id=evidence.source_record_id,
                        jurisdiction=evidence.jurisdiction,
                        observed_field=kind.value,
                        evidence_record_id=evidence.evidence_id,
                        raw_value=value,
                        observed_at=observation.effective_at,
                    )
                )
        return IdentityFingerprint(
            fingerprint_id=canonical_identity_fingerprint_id(
                target_identity_id=observation.investigation_id,
                target_kind=ResolutionTargetKind.PROJECT,
                observation_ids=[item.observation_id for item in artifacts],
                evidence_record_ids=[evidence.evidence_id],
            ),
            target_identity_id=observation.investigation_id,
            artifact_observations=artifacts,
            evidence_record_ids=[evidence.evidence_id],
        )
