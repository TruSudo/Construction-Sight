"""Deterministic intelligence graph service.

This service is the first behavior layer above the intelligence schemas and
repository store. It intentionally performs no AI inference. It creates and
updates evidence-backed graph records while emitting runtime events that later
runtime/UI layers can consume.
"""

from __future__ import annotations

from constructionsight.intelligence.schemas import (
    EntityIdentity,
    EvidenceRecord,
    OpportunitySignal,
    ProjectCluster,
    RelationshipAssertion,
    RuntimeEvent,
    RuntimeEventSeverity,
    RuntimeEventType,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


class IntelligenceGraphService:
    """Service for deterministic intelligence graph writes and event emission."""

    def __init__(self, store: IntelligenceStore, *, source_service: str = "intelligence_graph_service") -> None:
        self.store = store
        self.source_service = source_service

    def record_evidence(self, evidence: EvidenceRecord) -> EvidenceRecord:
        """Persist an evidence record and emit a source-record event."""

        was_existing = any(record.evidence_id == evidence.evidence_id for record in self.store.list_evidence())
        self.store.upsert_evidence(evidence)
        self._emit_event(
            event_id=f"event:evidence:{evidence.evidence_id}",
            event_type=RuntimeEventType.SOURCE_RECORD_CHANGED if was_existing else RuntimeEventType.SOURCE_RECORD_DISCOVERED,
            severity=RuntimeEventSeverity.LOW,
            message=f"Evidence {'updated' if was_existing else 'recorded'} from {evidence.source_name}.",
            source_record_refs=[evidence.evidence_id],
            payload={
                "operation": "updated" if was_existing else "created",
                "evidence_id": evidence.evidence_id,
                "source_name": evidence.source_name,
                "record_type": evidence.record_type,
            },
        )
        return evidence

    def upsert_entity(self, entity: EntityIdentity) -> EntityIdentity:
        """Persist an entity identity and emit a create/update event."""

        was_existing = any(record.entity_id == entity.entity_id for record in self.store.list_entities())
        self.store.upsert_entity(entity)
        self._emit_event(
            event_id=f"event:entity:{entity.entity_id}",
            event_type=RuntimeEventType.ENTITY_MERGED if was_existing else RuntimeEventType.ENTITY_CREATED,
            severity=RuntimeEventSeverity.MEDIUM,
            message=f"Entity {'updated' if was_existing else 'recorded'}: {entity.canonical_name}.",
            entity_refs=[entity.entity_id],
            payload={
                "operation": "updated" if was_existing else "created",
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type.value,
                "canonical_name": entity.canonical_name,
                "identity_status": entity.identity_status.value,
                "confidence_score": entity.confidence_score,
            },
        )
        return entity

    def upsert_relationship(self, relationship: RelationshipAssertion) -> RelationshipAssertion:
        """Persist an evidence-backed relationship and emit a graph event."""

        was_existing = any(
            record.relationship_id == relationship.relationship_id
            for record in self.store.list_relationships()
        )
        self.store.upsert_relationship(relationship)
        self._emit_event(
            event_id=f"event:relationship:{relationship.relationship_id}",
            event_type=RuntimeEventType.RELATIONSHIP_UPDATED if was_existing else RuntimeEventType.RELATIONSHIP_CREATED,
            severity=RuntimeEventSeverity.HIGH,
            message=f"Relationship {'updated' if was_existing else 'recorded'}: {relationship.predicate}.",
            entity_refs=[relationship.subject_entity_id, relationship.object_entity_id],
            source_record_refs=relationship.supporting_evidence_ids,
            payload={
                "operation": "updated" if was_existing else "created",
                "relationship_id": relationship.relationship_id,
                "subject_entity_id": relationship.subject_entity_id,
                "predicate": relationship.predicate,
                "object_entity_id": relationship.object_entity_id,
                "relationship_status": relationship.relationship_status.value,
                "confidence_score": relationship.confidence_score,
            },
        )
        return relationship

    def upsert_project_cluster(self, cluster: ProjectCluster) -> ProjectCluster:
        """Persist a project cluster and emit a project-cluster event."""

        was_existing = any(
            record.project_cluster_id == cluster.project_cluster_id
            for record in self.store.list_project_clusters()
        )
        self.store.upsert_project_cluster(cluster)
        self._emit_event(
            event_id=f"event:project_cluster:{cluster.project_cluster_id}",
            event_type=RuntimeEventType.PROJECT_CLUSTER_UPDATED if was_existing else RuntimeEventType.PROJECT_CLUSTER_CREATED,
            severity=RuntimeEventSeverity.HIGH,
            message=f"Project cluster {'updated' if was_existing else 'recorded'}: {cluster.project_name or cluster.project_cluster_id}.",
            project_cluster_refs=[cluster.project_cluster_id],
            source_record_refs=cluster.evidence_record_ids,
            payload={
                "operation": "updated" if was_existing else "created",
                "project_cluster_id": cluster.project_cluster_id,
                "project_name": cluster.project_name,
                "jurisdiction": cluster.jurisdiction,
                "cluster_status": cluster.cluster_status.value,
                "lifecycle_phase": cluster.lifecycle_phase.value,
                "cluster_confidence": cluster.cluster_confidence,
            },
        )
        return cluster

    def upsert_opportunity(self, opportunity: OpportunitySignal) -> OpportunitySignal:
        """Persist an opportunity signal and emit an opportunity event."""

        was_existing = any(
            record.opportunity_id == opportunity.opportunity_id
            for record in self.store.list_opportunities()
        )
        self.store.upsert_opportunity(opportunity)
        self._emit_event(
            event_id=f"event:opportunity:{opportunity.opportunity_id}",
            event_type=RuntimeEventType.OPPORTUNITY_SIGNAL_CREATED,
            severity=RuntimeEventSeverity.MEDIUM,
            message=f"Opportunity signal {'updated' if was_existing else 'recorded'}: {opportunity.category.value}.",
            project_cluster_refs=[opportunity.project_cluster_id] if opportunity.project_cluster_id else [],
            entity_refs=opportunity.related_entity_ids,
            source_record_refs=opportunity.evidence_record_ids,
            payload={
                "operation": "updated" if was_existing else "created",
                "opportunity_id": opportunity.opportunity_id,
                "category": opportunity.category.value,
                "opportunity_status": opportunity.opportunity_status.value,
                "project_cluster_id": opportunity.project_cluster_id,
                "confidence_score": opportunity.confidence_score,
            },
        )
        return opportunity

    def _emit_event(
        self,
        *,
        event_id: str,
        event_type: RuntimeEventType,
        severity: RuntimeEventSeverity,
        message: str,
        payload: dict[str, object],
        entity_refs: list[str] | None = None,
        project_cluster_refs: list[str] | None = None,
        source_record_refs: list[str] | None = None,
    ) -> RuntimeEvent:
        """Persist a runtime event for a graph operation."""

        event = RuntimeEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            source_service=self.source_service,
            entity_refs=entity_refs or [],
            project_cluster_refs=project_cluster_refs or [],
            source_record_refs=source_record_refs or [],
            payload=payload,
            message=message,
        )
        self.store.add_runtime_event(event)
        return event
