"""Repository layer for persisted intelligence-domain records."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.intelligence import (
    EntityIdentity,
    EvidenceRecord,
    OpportunitySignal,
    ProjectCluster,
    RelationshipAssertion,
    RuntimeEvent,
    WatchlistItem,
)
from constructionsight.storage.intelligence_orm import (
    IntelligenceEntityRecord,
    IntelligenceEvidenceRecord,
    IntelligenceOpportunityRecord,
    IntelligenceProjectClusterRecord,
    IntelligenceRelationshipRecord,
    IntelligenceRuntimeEventRecord,
    IntelligenceWatchlistRecord,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _model_to_json(model: BaseModel) -> str:
    """Serialize a Pydantic model to deterministic JSON."""

    return model.model_dump_json(exclude_none=False)


def _json_to_model(payload_json: str, model_type: type[ModelT]) -> ModelT:
    """Deserialize an ORM payload JSON string into a Pydantic model."""

    return model_type.model_validate(json.loads(payload_json))


class IntelligenceStore:
    """Persistence repository for intelligence-domain schema objects."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _stage_new_record(self, record: Any) -> None:
        """Stage a new ORM record without flushing incomplete required fields."""

        self.session.add(record)

    def _flush(self) -> None:
        """Flush upserted rows so same-session lookups can see them."""

        self.session.flush()

    def upsert_evidence(self, evidence: EvidenceRecord) -> IntelligenceEvidenceRecord:
        """Insert or update an intelligence evidence record."""

        record = self.session.scalar(
            select(IntelligenceEvidenceRecord).where(
                IntelligenceEvidenceRecord.evidence_id == evidence.evidence_id
            )
        )
        if record is None:
            record = IntelligenceEvidenceRecord(evidence_id=evidence.evidence_id)
            self._stage_new_record(record)
        record.source_name = evidence.source_name
        record.record_type = evidence.record_type
        record.confidence_contribution = evidence.confidence_contribution
        record.payload_json = _model_to_json(evidence)
        self._flush()
        return record

    def list_evidence(self, *, limit: int = 100) -> list[EvidenceRecord]:
        """Return latest persisted evidence records."""

        records = self.session.scalars(
            select(IntelligenceEvidenceRecord)
            .order_by(IntelligenceEvidenceRecord.id.desc())
            .limit(limit)
        ).all()
        return [_json_to_model(record.payload_json, EvidenceRecord) for record in records]

    def upsert_entity(self, entity: EntityIdentity) -> IntelligenceEntityRecord:
        """Insert or update an intelligence entity identity."""

        record = self.session.scalar(
            select(IntelligenceEntityRecord).where(IntelligenceEntityRecord.entity_id == entity.entity_id)
        )
        if record is None:
            record = IntelligenceEntityRecord(entity_id=entity.entity_id)
            self._stage_new_record(record)
        record.entity_type = entity.entity_type.value
        record.canonical_name = entity.canonical_name
        record.identity_status = entity.identity_status.value
        record.confidence_score = entity.confidence_score
        record.payload_json = _model_to_json(entity)
        self._flush()
        return record

    def list_entities(self, *, limit: int = 100) -> list[EntityIdentity]:
        """Return latest persisted entity identities."""

        records = self.session.scalars(
            select(IntelligenceEntityRecord).order_by(IntelligenceEntityRecord.id.desc()).limit(limit)
        ).all()
        return [_json_to_model(record.payload_json, EntityIdentity) for record in records]

    def upsert_relationship(
        self,
        relationship: RelationshipAssertion,
    ) -> IntelligenceRelationshipRecord:
        """Insert or update an intelligence relationship assertion."""

        record = self.session.scalar(
            select(IntelligenceRelationshipRecord).where(
                IntelligenceRelationshipRecord.relationship_id == relationship.relationship_id
            )
        )
        if record is None:
            record = IntelligenceRelationshipRecord(relationship_id=relationship.relationship_id)
            self._stage_new_record(record)
        record.subject_entity_id = relationship.subject_entity_id
        record.predicate = relationship.predicate
        record.object_entity_id = relationship.object_entity_id
        record.relationship_status = relationship.relationship_status.value
        record.confidence_score = relationship.confidence_score
        record.payload_json = _model_to_json(relationship)
        self._flush()
        return record

    def list_relationships(self, *, limit: int = 100) -> list[RelationshipAssertion]:
        """Return latest persisted relationship assertions."""

        records = self.session.scalars(
            select(IntelligenceRelationshipRecord)
            .order_by(IntelligenceRelationshipRecord.id.desc())
            .limit(limit)
        ).all()
        return [_json_to_model(record.payload_json, RelationshipAssertion) for record in records]

    def upsert_project_cluster(self, cluster: ProjectCluster) -> IntelligenceProjectClusterRecord:
        """Insert or update an intelligence project cluster."""

        record = self.session.scalar(
            select(IntelligenceProjectClusterRecord).where(
                IntelligenceProjectClusterRecord.project_cluster_id == cluster.project_cluster_id
            )
        )
        if record is None:
            record = IntelligenceProjectClusterRecord(project_cluster_id=cluster.project_cluster_id)
            self._stage_new_record(record)
        record.project_name = cluster.project_name
        record.jurisdiction = cluster.jurisdiction
        record.cluster_status = cluster.cluster_status.value
        record.lifecycle_phase = cluster.lifecycle_phase.value
        record.cluster_confidence = cluster.cluster_confidence
        record.payload_json = _model_to_json(cluster)
        self._flush()
        return record

    def list_project_clusters(self, *, limit: int = 100) -> list[ProjectCluster]:
        """Return latest persisted project clusters."""

        records = self.session.scalars(
            select(IntelligenceProjectClusterRecord)
            .order_by(IntelligenceProjectClusterRecord.id.desc())
            .limit(limit)
        ).all()
        return [_json_to_model(record.payload_json, ProjectCluster) for record in records]

    def upsert_opportunity(self, opportunity: OpportunitySignal) -> IntelligenceOpportunityRecord:
        """Insert or update an intelligence opportunity signal."""

        record = self.session.scalar(
            select(IntelligenceOpportunityRecord).where(
                IntelligenceOpportunityRecord.opportunity_id == opportunity.opportunity_id
            )
        )
        if record is None:
            record = IntelligenceOpportunityRecord(opportunity_id=opportunity.opportunity_id)
            self._stage_new_record(record)
        record.category = opportunity.category.value
        record.opportunity_status = opportunity.opportunity_status.value
        record.project_cluster_id = opportunity.project_cluster_id
        record.confidence_score = opportunity.confidence_score
        record.payload_json = _model_to_json(opportunity)
        self._flush()
        return record

    def list_opportunities(self, *, limit: int = 100) -> list[OpportunitySignal]:
        """Return latest persisted opportunity signals."""

        records = self.session.scalars(
            select(IntelligenceOpportunityRecord)
            .order_by(IntelligenceOpportunityRecord.id.desc())
            .limit(limit)
        ).all()
        return [_json_to_model(record.payload_json, OpportunitySignal) for record in records]

    def add_runtime_event(self, event: RuntimeEvent) -> IntelligenceRuntimeEventRecord:
        """Persist a runtime event.

        Runtime events are append-oriented. If the same event ID already exists,
        the existing record is updated to preserve idempotent test/runtime behavior.
        """

        record = self.session.scalar(
            select(IntelligenceRuntimeEventRecord).where(
                IntelligenceRuntimeEventRecord.event_id == event.event_id
            )
        )
        if record is None:
            record = IntelligenceRuntimeEventRecord(event_id=event.event_id)
            self._stage_new_record(record)
        record.event_type = event.event_type.value
        record.severity = event.severity.value
        record.source_service = event.source_service
        record.message = event.message
        record.payload_json = _model_to_json(event)
        self._flush()
        return record

    def list_runtime_events(self, *, limit: int = 100) -> list[RuntimeEvent]:
        """Return latest runtime events."""

        records = self.session.scalars(
            select(IntelligenceRuntimeEventRecord)
            .order_by(IntelligenceRuntimeEventRecord.id.desc())
            .limit(limit)
        ).all()
        return [_json_to_model(record.payload_json, RuntimeEvent) for record in records]

    def upsert_watchlist_item(self, item: WatchlistItem) -> IntelligenceWatchlistRecord:
        """Insert or update a workspace watchlist item."""

        record = self.session.scalar(
            select(IntelligenceWatchlistRecord).where(
                IntelligenceWatchlistRecord.watchlist_item_id == item.watchlist_item_id
            )
        )
        if record is None:
            record = IntelligenceWatchlistRecord(watchlist_item_id=item.watchlist_item_id)
            self._stage_new_record(record)
        record.workspace_id = item.workspace_id
        record.target_type = item.target_type.value if hasattr(item.target_type, "value") else str(item.target_type)
        record.target_id = item.target_id
        record.status = item.status.value
        record.priority = item.priority
        record.payload_json = _model_to_json(item)
        self._flush()
        return record

    def list_watchlist_items(self, *, workspace_id: str | None = None, limit: int = 100) -> list[WatchlistItem]:
        """Return latest watchlist items, optionally filtered by workspace."""

        statement: Any = select(IntelligenceWatchlistRecord).order_by(
            IntelligenceWatchlistRecord.id.desc()
        )
        if workspace_id is not None:
            statement = statement.where(IntelligenceWatchlistRecord.workspace_id == workspace_id)
        records = self.session.scalars(statement.limit(limit)).all()
        return [_json_to_model(record.payload_json, WatchlistItem) for record in records]
