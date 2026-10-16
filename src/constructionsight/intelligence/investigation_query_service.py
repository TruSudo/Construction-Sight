"""Read shared investigation accounts without creating an alternative source of truth."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from constructionsight.intelligence.investigation_service import (
    InvestigationService,
    observation_receipt_identity,
    source_record_identity,
)
from constructionsight.intelligence.relationship_query_service import (
    ACTIVE_INVESTIGATION_CONTEXT_STATUSES,
    canonical_investigation_id,
)
from constructionsight.intelligence.schemas import LifecyclePhase, RelationshipStatus
from constructionsight.storage.database import ensure_database_transaction
from constructionsight.storage.intelligence_store import IntelligenceStore


class InvestigationQueryService:
    """Bounded dossiers from the same committed graph, evidence and revision store."""

    def __init__(self, store: IntelligenceStore) -> None:
        self.store = store

    def dossier(self, investigation_id: str, *, evidence_limit: int = 250) -> dict[str, Any]:
        if type(evidence_limit) is not int or not 1 <= evidence_limit <= 1000:
            raise ValueError("evidence_limit must be between 1 and 1000")
        ensure_database_transaction(self.store.session)
        requested_id = investigation_id
        investigation_id = canonical_investigation_id(self.store, investigation_id)
        cluster = self.store.get_project_cluster(investigation_id)
        if cluster is None:
            raise ValueError("unknown investigation")
        page = self.store.list_relationships_for_target(investigation_id, limit=1001)
        relationships = page[:1000]
        all_evidence_ids = list(
            dict.fromkeys(
                cluster.evidence_record_ids
                + [
                    identity
                    for relationship in relationships
                    for identity in (
                        relationship.supporting_evidence_ids
                        + relationship.contradictory_evidence_ids
                    )
                ]
            )
        )
        evidence_ids = all_evidence_ids[:evidence_limit]
        evidence = [self.store.get_evidence(identity) for identity in evidence_ids]
        if any(item is None for item in evidence):
            raise ValueError("investigation references missing retained evidence")
        source_ids = list(
            dict.fromkeys(
                [
                    relation.subject_entity_id
                    for relation in relationships
                    if (
                        relation.predicate == "source_record_for_unresolved_investigation"
                        or (
                            relation.predicate == "reviewed_source_context"
                            and relation.relationship_status
                            in ACTIVE_INVESTIGATION_CONTEXT_STATUSES
                        )
                    )
                ]
            )
        )
        source_service = InvestigationService(self.store)
        current = [source_service.current_observation(identity) for identity in source_ids]
        location_assessments = []
        for source_id in source_ids:
            entity = self.store.get_entity(source_id)
            if entity is None:
                raise ValueError("investigation references a missing source identity")
            event_id = entity.identifiers.get("current_location_assessment")
            if event_id:
                event = self.store.get_runtime_event(event_id)
                if event is None:
                    raise ValueError("source location assessment receipt is missing")
                location_assessments.append(event.payload)
        chronology: list[dict[str, Any]] = []
        for item in evidence:
            if item is None:
                continue
            source_id = source_record_identity(item)
            if source_id not in source_ids:
                continue
            receipt = self.store.get_runtime_event(
                observation_receipt_identity(source_id, item.evidence_id)
            )
            if receipt is not None:
                chronology.append(
                    {
                        "event_id": receipt.event_id,
                        "retained_at": receipt.created_at.isoformat(),
                        "effective_at": (item.observed_at or item.retrieved_at).isoformat(),
                        "time_basis": "source_observed_at"
                        if item.observed_at
                        else "retention_time_only",
                        "evidence_id": item.evidence_id,
                        "source_id": source_id,
                        "observation": receipt.payload,
                    }
                )
        chronology.sort(
            key=lambda item: (
                datetime.fromisoformat(item["effective_at"]).astimezone(UTC),
                item["event_id"],
            )
        )
        gaps = [
            "Project/site identity has not been independently verified.",
            "Commercial authority and buyer readiness have not been established.",
        ]
        if cluster.lifecycle_phase is LifecyclePhase.UNKNOWN:
            gaps.append("Current physical construction activity is unknown.")
        families = sorted(
            {item.evidence.source_family for item in current if item.evidence.source_family}
        )
        if len(families) < 2:
            gaps.append("No corroborated multi-source investigation membership established.")
        points = [
            {
                "latitude": item.latitude,
                "longitude": item.longitude,
                "evidence_id": item.evidence.evidence_id,
                "certainty": "source_claimed",
            }
            for item in current
            if item.latitude is not None and item.longitude is not None
        ]
        if not points:
            gaps.append("No complete retained geographic point; keep in unmapped review queue.")
        contradictions = [
            relation
            for relation in relationships
            if relation.relationship_status
            not in {
                RelationshipStatus.REJECTED,
                RelationshipStatus.SUPERSEDED,
            }
            and (
                relation.relationship_status is RelationshipStatus.CONFLICTING
                or relation.contradictory_evidence_ids
            )
        ]
        if contradictions:
            gaps.append("Unresolved conflicting identity artifacts require review.")
        pending_reviews = []
        for relationship in relationships:
            if (
                relationship.predicate != "possible_same_project_requires_review"
                or relationship.relationship_status is not RelationshipStatus.PROBABLE
                or not relationship.enrichment_run_id
            ):
                continue
            review = self.store.get_runtime_event(relationship.enrichment_run_id)
            if review is None or review.source_service != "investigation_identity_review":
                continue
            for source_id, retained_revisions in review.payload.get("source_revisions", {}).items():
                entity = self.store.get_entity(source_id)
                if entity is None or entity.evidence_record_ids != retained_revisions:
                    pending_reviews.append(relationship.relationship_id)
                    break
        if pending_reviews:
            gaps.append(
                "Source evidence changed since the reviewed association; reassessment required."
            )
        if len(page) > 1000 or len(all_evidence_ids) > evidence_limit:
            gaps.append("This bounded dossier is incomplete; request additional retained records.")
        evidence_source_ids = {
            item.evidence_id: source_record_identity(item) for item in evidence if item is not None
        }
        return {
            "schema_version": "constructionsight.investigation-dossier/v1",
            "requested_investigation_id": requested_id,
            "investigation": cluster.model_dump(mode="json"),
            "event_cursor": self.store.runtime_event_cursor(),
            "evidence": [item.model_dump(mode="json") for item in evidence if item is not None],
            "evidence_context": {
                identity: (
                    "investigation_source"
                    if identity in cluster.evidence_record_ids
                    else (
                        "reviewed_source_context"
                        if (evidence_source_ids.get(identity) in source_ids)
                        else "cited_relationship_evidence_only"
                    )
                )
                for identity in evidence_ids
            },
            "evidence_truncated": len(all_evidence_ids) > evidence_limit,
            "location_assessments": location_assessments,
            "pending_association_reviews": pending_reviews,
            "source_observations": [
                item.model_dump(mode="json", round_trip=True) for item in current
            ],
            "relationships": [item.model_dump(mode="json") for item in relationships],
            "relationships_truncated": len(page) > 1000,
            "contradictions": [item.model_dump(mode="json") for item in contradictions],
            "chronology": chronology,
            "source_claimed_points": points,
            "assessment": {
                "evidence_certainty": "source_claimed_with_content_integrity",
                "identity_status": cluster.cluster_status.value,
                "identity_independently_verified": False,
                "investigation_completeness": "partial",
                "gaps": gaps,
                "construction_activity": cluster.lifecycle_phase.value,
                "commercial_readiness": "unassessed",
                "commercial_authority_granted": False,
            },
        }
