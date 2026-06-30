"""ORM tables for movement and identity records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class PermitSnapshotRecord(Base):
    """Persisted source-neutral permit snapshot."""

    __tablename__ = "permit_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_id", name="uq_permit_snapshots_snapshot_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    permit_number: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    site_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    observed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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


class PermitTransitionRecord(Base):
    """Persisted source-neutral permit transition."""

    __tablename__ = "permit_transitions"
    __table_args__ = (
        UniqueConstraint("transition_id", name="uq_permit_transitions_transition_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    transition_kind: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    field_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    opportunity_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detected_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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


class ContractorIdentityRecord(Base):
    """Persisted contractor identity."""

    __tablename__ = "contractor_identities"
    __table_args__ = (
        UniqueConstraint("contractor_key", name="uq_contractor_identities_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contractor_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
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


class DecisionRecordRow(Base):
    """Persisted public decision record."""

    __tablename__ = "decision_records"
    __table_args__ = (UniqueConstraint("decision_key", name="uq_decision_records_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_kind: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decision_kind: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    apn: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
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
