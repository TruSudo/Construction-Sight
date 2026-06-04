"""ORM tables for ConstructionSight intelligence-layer records.

These tables persist the first-generation intelligence schemas as JSON payloads
while exposing stable IDs, statuses, and confidence fields for indexed lookup.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class IntelligenceEvidenceRecord(Base):
    """Persisted intelligence evidence record."""

    __tablename__ = "intelligence_evidence_records"
    __table_args__ = (UniqueConstraint("evidence_id", name="uq_intelligence_evidence_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    confidence_contribution: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class IntelligenceEntityRecord(Base):
    """Persisted intelligence entity identity."""

    __tablename__ = "intelligence_entities"
    __table_args__ = (UniqueConstraint("entity_id", name="uq_intelligence_entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    identity_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class IntelligenceRelationshipRecord(Base):
    """Persisted intelligence relationship assertion."""

    __tablename__ = "intelligence_relationships"
    __table_args__ = (UniqueConstraint("relationship_id", name="uq_intelligence_relationship_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relationship_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject_entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    object_entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relationship_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class IntelligenceProjectClusterRecord(Base):
    """Persisted intelligence project cluster."""

    __tablename__ = "intelligence_project_clusters"
    __table_args__ = (
        UniqueConstraint("project_cluster_id", name="uq_intelligence_project_cluster_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_cluster_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    project_name: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    cluster_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lifecycle_phase: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    cluster_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class IntelligenceOpportunityRecord(Base):
    """Persisted intelligence opportunity signal."""

    __tablename__ = "intelligence_opportunities"
    __table_args__ = (UniqueConstraint("opportunity_id", name="uq_intelligence_opportunity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opportunity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    opportunity_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_cluster_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class IntelligenceRuntimeEventRecord(Base):
    """Persisted runtime event."""

    __tablename__ = "intelligence_runtime_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_intelligence_runtime_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_service: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class IntelligenceWatchlistRecord(Base):
    """Persisted workspace watchlist item."""

    __tablename__ = "intelligence_watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_item_id", name="uq_intelligence_watchlist_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watchlist_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
