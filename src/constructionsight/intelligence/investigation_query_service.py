"""Read shared investigation accounts without creating an alternative source of truth."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

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
from constructionsight.storage.intelligence_orm import (
    IntelligenceProjectClusterRecord,
    IntelligenceRelationshipRecord,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


class InvestigationQueryService:
    """Bounded dossiers from the same committed graph, evidence and revision store."""

    def __init__(self, store: IntelligenceStore) -> None:
        self.store = store

    def inventory(self, *, after: str | None = None, limit: int = 50) -> dict[str, Any]:
        """Return a bounded canonical inventory; reviewed aliases never create duplicate rows."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("inventory limit must be between 1 and 100")
        if after is not None and (not after.strip() or len(after) > 255):
            raise ValueError("invalid inventory cursor")
        ensure_database_transaction(self.store.session)
        aliases = select(IntelligenceRelationshipRecord.subject_entity_id).where(
            IntelligenceRelationshipRecord.predicate == "reviewed_investigation_alias",
            IntelligenceRelationshipRecord.relationship_status.in_(
                [value.value for value in ACTIVE_INVESTIGATION_CONTEXT_STATUSES]
            ),
        )
        predicate = ~IntelligenceProjectClusterRecord.project_cluster_id.in_(aliases)
        total = (
            self.store.session.scalar(
                select(func.count()).select_from(IntelligenceProjectClusterRecord).where(predicate)
            )
            or 0
        )
        statement = select(IntelligenceProjectClusterRecord.project_cluster_id).where(predicate)
        if after is not None:
            statement = statement.where(IntelligenceProjectClusterRecord.project_cluster_id > after)
        identities = list(
            self.store.session.scalars(
                statement.order_by(IntelligenceProjectClusterRecord.project_cluster_id).limit(
                    limit + 1
                )
            )
        )
        rows = []
        for identity in identities[:limit]:
            dossier = self.dossier(identity, evidence_limit=1)
            observations = dossier["source_observations"]
            rows.append(
                {
                    "investigation_id": identity,
                    "title": dossier["investigation"]["project_name"],
                    "counties": sorted({item["county"] for item in observations if item["county"]}),
                    "points": dossier["source_claimed_points"],
                    "source_records": [
                        {
                            "source_name": item["evidence"]["source_name"],
                            "source_family": item["evidence"]["source_family"],
                            "source_record_id": item["evidence"]["source_record_id"],
                        }
                        for item in observations
                    ],
                    "assessment": dossier["assessment"],
                    "pending_association_reviews": dossier["pending_association_reviews"],
                    "sources_truncated": dossier["sources_truncated"],
                }
            )
        return {
            "schema_version": "constructionsight.investigation-inventory/v1",
            "event_cursor": self.store.runtime_event_cursor(),
            "total": total,
            "rows": rows,
            "has_more": len(identities) > limit,
            "next_cursor": identities[limit - 1] if len(identities) > limit else None,
            "mapped_on_page": sum(bool(row["points"]) for row in rows),
            "unmapped_on_page": [row["investigation_id"] for row in rows if not row["points"]],
        }

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
        sources_truncated = len(source_ids) > 50
        source_ids = source_ids[:50]
        source_entities = {}
        for identity in source_ids:
            source_entity = self.store.get_entity(identity)
            if source_entity is None:
                raise ValueError("investigation references a missing source identity")
            source_entities[identity] = source_entity
        all_evidence_ids = list(
            dict.fromkeys(
                cluster.evidence_record_ids
                + [
                    identity
                    for entity in source_entities.values()
                    for identity in entity.evidence_record_ids
                ]
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
        source_service = InvestigationService(self.store)
        current = [source_service.current_observation(identity) for identity in source_ids]
        location_assessments = []
        party_contexts: list[dict[str, Any]] = []
        parties_truncated = False
        for observation in current:
            role_page = self.store.list_relationships_for_target(
                observation.investigation_id, limit=501
            )
            if len(role_page) > 500:
                parties_truncated = True
            for role in role_page[:500]:
                if not role.predicate.startswith("source_claimed_") or role.relationship_status in {
                    RelationshipStatus.STALE,
                    RelationshipStatus.SUPERSEDED,
                    RelationshipStatus.REJECTED,
                }:
                    continue
                if len(party_contexts) >= 500:
                    parties_truncated = True
                    break
                party_entity = self.store.get_entity(role.subject_entity_id)
                if party_entity is None:
                    raise ValueError("source participant is missing its persisted graph context")
                assessment_id = party_entity.identifiers.get("contractor_assessment_event")
                assessment = self.store.get_runtime_event(assessment_id) if assessment_id else None
                if assessment_id and assessment is None:
                    raise ValueError("source contractor assessment receipt is missing")
                party_contexts.append(
                    {
                        "entity": party_entity.model_dump(mode="json"),
                        "source_id": observation.source_entity_id,
                        "relationship": role.model_dump(mode="json"),
                        "canonical_investigation_id": canonical_investigation_id(
                            self.store, role.object_entity_id
                        ),
                        "review_required": observation.evidence.evidence_id
                        not in role.supporting_evidence_ids,
                        "contractor_assessment": assessment.payload if assessment else None,
                    }
                )
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
        # Correlation edges join investigation identities, not source records.
        # Inspect their retained source context without merging unreviewed claims
        # into this investigation's evidence, timeline or commercial assessment.
        candidate_links: list[dict[str, Any]] = []
        candidates_truncated = False
        for relation in relationships:
            if (
                relation.predicate != "possible_same_project_requires_review"
                or relation.relationship_status
                in {
                    RelationshipStatus.REJECTED,
                    RelationshipStatus.SUPERSEDED,
                    RelationshipStatus.STALE,
                }
            ):
                continue
            if len(candidate_links) >= 250:
                candidates_truncated = True
                break
            other_id = (
                relation.object_entity_id
                if relation.subject_entity_id == investigation_id
                else relation.subject_entity_id
            )
            other_canonical = canonical_investigation_id(self.store, other_id)
            if other_canonical == investigation_id:
                continue
            if self.store.get_project_cluster(other_canonical) is None:
                raise ValueError("candidate relationship references a missing investigation")
            adjacent = self.store.list_relationships_for_target(other_canonical, limit=251)
            external_ids = list(
                dict.fromkeys(
                    edge.subject_entity_id
                    for edge in adjacent
                    if edge.object_entity_id == other_canonical
                    and (
                        edge.predicate == "source_record_for_unresolved_investigation"
                        or (
                            edge.predicate == "reviewed_source_context"
                            and edge.relationship_status
                            in ACTIVE_INVESTIGATION_CONTEXT_STATUSES
                        )
                    )
                )
            )
            candidate_sources_truncated = len(adjacent) > 250 or len(external_ids) > 10
            candidate_sources: list[dict[str, Any]] = []
            for source_id in external_ids[:10]:
                other = source_service.current_observation(source_id)
                candidate_sources.append(
                    {
                        "source_id": source_id,
                        "source_family": other.evidence.source_family,
                        "source_record_id": other.evidence.source_record_id,
                        "evidence_id": other.evidence.evidence_id,
                        "effective_at": other.effective_at.isoformat(),
                        "time_basis": (
                            "source_observed_at"
                            if other.evidence.observed_at
                            else "retention_time_only"
                        ),
                        "limitations": other.evidence.limitations,
                    }
                )
            candidate_links.append(
                {
                    "relationship_id": relation.relationship_id,
                    "candidate_investigation_id": other_canonical,
                    "candidate_sources": candidate_sources,
                    "candidate_sources_truncated": candidate_sources_truncated,
                    "relationship_status": relation.relationship_status.value,
                    "supporting_evidence_ids": relation.supporting_evidence_ids,
                    "contradictory_evidence_ids": relation.contradictory_evidence_ids,
                    "evidence_summary": relation.evidence_summary,
                    "identity_verified": False,
                    "membership_confirmed": False,
                }
            )
        candidate_links.sort(key=lambda item: item["relationship_id"])
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
        if candidate_links:
            gaps.append(
                "Cross-source project candidates require identity review before shared membership."
            )
        if any(item["contradictory_evidence_ids"] for item in candidate_links):
            gaps.append("Conflicting cross-source candidate evidence requires investigation.")
        if candidates_truncated:
            gaps.append("Candidate associations exceed the bounded dossier review page.")
        if any(link["candidate_sources_truncated"] for link in candidate_links):
            gaps.append("Some candidate source context exceeds the bounded evidence preview.")
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
        if sources_truncated or len(page) > 1000 or len(all_evidence_ids) > evidence_limit:
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
            "source_parties": party_contexts,
            "parties_truncated": parties_truncated,
            "pending_association_reviews": pending_reviews,
            "candidate_source_links": candidate_links,
            "candidate_links_truncated": candidates_truncated,
            "sources_truncated": sources_truncated,
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
