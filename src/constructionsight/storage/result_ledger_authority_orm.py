"""SQLAlchemy persistence for authoritative result-ledger state and history."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


class ResultLedgerAuthorityRecordRow(Base):
    """Current authoritative result-ledger pointer for one workflow."""

    __tablename__ = "result_ledger_authorities"
    __table_args__ = (
        UniqueConstraint("authority_id", name="uq_result_ledger_authorities_id"),
        UniqueConstraint("workflow_id", name="uq_result_ledger_authorities_workflow"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    authority_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_ledger_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class ResultLedgerAuthorityEventRow(Base):
    """Append-only authoritative result-ledger pointer event."""

    __tablename__ = "result_ledger_authority_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_result_ledger_authority_events_id"),
        UniqueConstraint(
            "workflow_id",
            "revision",
            name="uq_result_ledger_authority_events_revision",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    previous_ledger_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    current_ledger_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    observed_created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
