"""Repository layer for persisted intelligence-domain records."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from constructionsight.intelligence import (
    EntityIdentity,
    EvidenceRecord,
    IdentityStatus,
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

    @staticmethod
    def _apply_limit(statement: Any, limit: int | None) -> Any:
        """Apply an explicit positive limit; None means complete results."""

        if limit is None:
            return statement
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("intelligence query limit must be a positive integer or None")
        return statement.limit(limit)

    def _require_evidence_ids(self, evidence_ids: list[str], *, label: str) -> None:
        """Require every evidence reference to resolve to retained evidence."""

        if not evidence_ids:
            raise ValueError(f"{label} requires retained evidence references")
        self._flush()
        required = set(evidence_ids)
        observed = set(
            self.session.scalars(
                select(IntelligenceEvidenceRecord.evidence_id).where(
                    IntelligenceEvidenceRecord.evidence_id.in_(sorted(required))
                )
            ).all()
        )
        missing = sorted(required - observed)
        if missing:
            raise ValueError(f"{label} references missing evidence: {missing}")

    def _require_entity_ids(self, entity_ids: list[str], *, label: str) -> None:
        """Require every entity reference to resolve to a persisted entity."""

        if not entity_ids:
            return
        self._flush()
        required = set(entity_ids)
        observed = set(
            self.session.scalars(
                select(IntelligenceEntityRecord.entity_id).where(
                    IntelligenceEntityRecord.entity_id.in_(sorted(required))
                )
            ).all()
        )
        missing = sorted(required - observed)
        if missing:
            raise ValueError(f"{label} references missing entities: {missing}")

    def _require_graph_target(self, target_id: str, *, label: str) -> None:
        """Require a relationship endpoint to resolve to an entity or project cluster."""

        self._flush()
        entity = self.session.scalar(
            select(IntelligenceEntityRecord.id).where(
                IntelligenceEntityRecord.entity_id == target_id
            )
        )
        if entity is not None:
            return
        project = self.session.scalar(
            select(IntelligenceProjectClusterRecord.id).where(
                IntelligenceProjectClusterRecord.project_cluster_id == target_id
            )
        )
        if project is None:
            raise ValueError(f"{label} references missing graph target: {target_id}")

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

    def get_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        """Return one exact evidence record."""

        record = self.session.scalar(
            select(IntelligenceEvidenceRecord).where(
                IntelligenceEvidenceRecord.evidence_id == evidence_id
            )
        )
        return (
            _json_to_model(record.payload_json, EvidenceRecord)
            if record is not None
            else None
        )

    def list_evidence(self, *, limit: int | None = None) -> list[EvidenceRecord]:
        """Return persisted evidence records; None means the complete set."""

        statement = select(IntelligenceEvidenceRecord).order_by(
            IntelligenceEvidenceRecord.id.desc()
        )
        records = self.session.scalars(self._apply_limit(statement, limit)).all()
        return [_json_to_model(record.payload_json, EvidenceRecord) for record in records]

    def upsert_entity(self, entity: EntityIdentity) -> IntelligenceEntityRecord:
        """Insert or update an intelligence entity identity."""

        if entity.identity_status is not IdentityStatus.UNRESOLVED:
            self._require_evidence_ids(
                entity.evidence_record_ids,
                label=f"entity {entity.entity_id}",
            )
        elif entity.evidence_record_ids:
            self._require_evidence_ids(
                entity.evidence_record_ids,
                label=f"entity {entity.entity_id}",
            )
        record = self.session.scalar(
            select(IntelligenceEntityRecord).where(
                IntelligenceEntityRecord.entity_id == entity.entity_id
            )
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

    def get_entity(self, entity_id: str) -> EntityIdentity | None:
        """Return one exact entity identity."""

        record = self.session.scalar(
            select(IntelligenceEntityRecord).where(
                IntelligenceEntityRecord.entity_id == entity_id
            )
        )
        return (
            _json_to_model(record.payload_json, EntityIdentity)
            if record is not None
            else None
        )

    def list_entities(self, *, limit: int | None = None) -> list[EntityIdentity]:
        """Return persisted entity identities; None means the complete set."""

        statement = select(IntelligenceEntityRecord).order_by(
            IntelligenceEntityRecord.id.desc()
        )
        records = self.session.scalars(self._apply_limit(statement, limit)).all()
        return [_json_to_model(record.payload_json, EntityIdentity) for record in records]

    def list_entities_by_ids(self, entity_ids: set[str]) -> list[EntityIdentity]:
        """Return all persisted entities matching the requested identifiers."""

        if not entity_ids:
            return []
        records = self.session.scalars(
            select(IntelligenceEntityRecord)
            .where(IntelligenceEntityRecord.entity_id.in_(sorted(entity_ids)))
            .order_by(IntelligenceEntityRecord.entity_id)
        ).all()
        return [_json_to_model(record.payload_json, EntityIdentity) for record in records]

    def upsert_relationship(
        self,
        relationship: RelationshipAssertion,
    ) -> IntelligenceRelationshipRecord:
        """Insert or update an intelligence relationship assertion."""

        self._require_evidence_ids(
            relationship.supporting_evidence_ids,
            label=f"relationship {relationship.relationship_id}",
        )
        if relationship.contradictory_evidence_ids:
            self._require_evidence_ids(
                relationship.contradictory_evidence_ids,
                label=f"relationship {relationship.relationship_id} contradictions",
            )
        self._require_graph_target(
            relationship.subject_entity_id,
            label=f"relationship {relationship.relationship_id} subject",
        )
        self._require_graph_target(
            relationship.object_entity_id,
            label=f"relationship {relationship.relationship_id} object",
        )
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

    def get_relationship(self, relationship_id: str) -> RelationshipAssertion | None:
        """Return one exact relationship assertion."""

        record = self.session.scalar(
            select(IntelligenceRelationshipRecord).where(
                IntelligenceRelationshipRecord.relationship_id == relationship_id
            )
        )
        return (
            _json_to_model(record.payload_json, RelationshipAssertion)
            if record is not None
            else None
        )

    def list_relationships(self, *, limit: int | None = None) -> list[RelationshipAssertion]:
        """Return relationships; None means the complete set."""

        statement = select(IntelligenceRelationshipRecord).order_by(
            IntelligenceRelationshipRecord.id.desc()
        )
        records = self.session.scalars(self._apply_limit(statement, limit)).all()
        return [_json_to_model(record.payload_json, RelationshipAssertion) for record in records]

    def list_relationships_for_target(self, target_id: str) -> list[RelationshipAssertion]:
        """Return all relationships connected to one entity or project target."""

        records = self.session.scalars(
            select(IntelligenceRelationshipRecord)
            .where(
                or_(
                    IntelligenceRelationshipRecord.subject_entity_id == target_id,
                    IntelligenceRelationshipRecord.object_entity_id == target_id,
                )
            )
            .order_by(IntelligenceRelationshipRecord.id.desc())
        ).all()
        return [_json_to_model(record.payload_json, RelationshipAssertion) for record in records]

    def upsert_project_cluster(self, cluster: ProjectCluster) -> IntelligenceProjectClusterRecord:
        """Insert or update an intelligence project cluster."""

        self._require_evidence_ids(
            cluster.evidence_record_ids,
            label=f"project cluster {cluster.project_cluster_id}",
        )
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

    def get_project_cluster(self, project_cluster_id: str) -> ProjectCluster | None:
        """Return one exact project cluster."""

        record = self.session.scalar(
            select(IntelligenceProjectClusterRecord).where(
                IntelligenceProjectClusterRecord.project_cluster_id == project_cluster_id
            )
        )
        return (
            _json_to_model(record.payload_json, ProjectCluster)
            if record is not None
            else None
        )

    def list_project_clusters(self, *, limit: int | None = None) -> list[ProjectCluster]:
        """Return project clusters; None means the complete set."""

        statement = select(IntelligenceProjectClusterRecord).order_by(
            IntelligenceProjectClusterRecord.id.desc()
        )
        records = self.session.scalars(self._apply_limit(statement, limit)).all()
        return [_json_to_model(record.payload_json, ProjectCluster) for record in records]

    def list_project_clusters_by_ids(self, project_ids: set[str]) -> list[ProjectCluster]:
        """Return all project clusters matching the requested identifiers."""

        if not project_ids:
            return []
        records = self.session.scalars(
            select(IntelligenceProjectClusterRecord)
            .where(
                IntelligenceProjectClusterRecord.project_cluster_id.in_(
                    sorted(project_ids)
                )
            )
            .order_by(IntelligenceProjectClusterRecord.project_cluster_id)
        ).all()
        return [_json_to_model(record.payload_json, ProjectCluster) for record in records]

    def upsert_opportunity(self, opportunity: OpportunitySignal) -> IntelligenceOpportunityRecord:
        """Insert or update an intelligence opportunity signal."""

        self._require_evidence_ids(
            opportunity.evidence_record_ids,
            label=f"opportunity {opportunity.opportunity_id}",
        )
        if opportunity.project_cluster_id is not None:
            self._flush()
            project = self.session.scalar(
                select(IntelligenceProjectClusterRecord.id).where(
                    IntelligenceProjectClusterRecord.project_cluster_id
                    == opportunity.project_cluster_id
                )
            )
            if project is None:
                raise ValueError(
                    f"opportunity {opportunity.opportunity_id} references missing "
                    f"project cluster: {opportunity.project_cluster_id}"
                )
        entity_ids = list(opportunity.related_entity_ids)
        if opportunity.site_entity_id is not None:
            entity_ids.append(opportunity.site_entity_id)
        self._require_entity_ids(
            entity_ids,
            label=f"opportunity {opportunity.opportunity_id}",
        )
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

    def get_opportunity(self, opportunity_id: str) -> OpportunitySignal | None:
        """Return one exact opportunity signal."""

        record = self.session.scalar(
            select(IntelligenceOpportunityRecord).where(
                IntelligenceOpportunityRecord.opportunity_id == opportunity_id
            )
        )
        return (
            _json_to_model(record.payload_json, OpportunitySignal)
            if record is not None
            else None
        )

    def list_opportunities(self, *, limit: int | None = None) -> list[OpportunitySignal]:
        """Return opportunities; None means the complete set."""

        statement = select(IntelligenceOpportunityRecord).order_by(
            IntelligenceOpportunityRecord.id.desc()
        )
        records = self.session.scalars(self._apply_limit(statement, limit)).all()
        return [_json_to_model(record.payload_json, OpportunitySignal) for record in records]

    def list_opportunities_for_project(self, project_cluster_id: str) -> list[OpportunitySignal]:
        """Return all opportunities directly linked to one project cluster."""

        records = self.session.scalars(
            select(IntelligenceOpportunityRecord)
            .where(
                IntelligenceOpportunityRecord.project_cluster_id == project_cluster_id
            )
            .order_by(IntelligenceOpportunityRecord.id.desc())
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
        record.target_type = (
            item.target_type.value if hasattr(item.target_type, "value") else str(item.target_type)
        )
        record.target_id = item.target_id
        record.status = item.status.value
        record.priority = item.priority
        record.payload_json = _model_to_json(item)
        self._flush()
        return record

    def list_watchlist_items(
        self, *, workspace_id: str | None = None, limit: int = 100
    ) -> list[WatchlistItem]:
        """Return latest watchlist items, optionally filtered by workspace."""

        statement: Any = select(IntelligenceWatchlistRecord).order_by(
            IntelligenceWatchlistRecord.id.desc()
        )
        if workspace_id is not None:
            statement = statement.where(IntelligenceWatchlistRecord.workspace_id == workspace_id)
        records = self.session.scalars(statement.limit(limit)).all()
        return [_json_to_model(record.payload_json, WatchlistItem) for record in records]
