"""ORM tables for serialized result-ledger authority and audit history."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class ResultAuthorityHeadRow(Base):
    """One compare-and-swap authority pointer for each result workflow."""

    __tablename__ = "result_authority_heads"
    __table_args__ = (UniqueConstraint("workflow_id", name="uq_result_authority_heads_workflow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_ledger_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
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


class ResultAuthorityEventRow(Base):
    """One immutable audit event for each authoritative ledger revision."""

    __tablename__ = "result_authority_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_result_authority_events_id"),
        UniqueConstraint(
            "workflow_id",
            "revision",
            name="uq_result_authority_events_workflow_revision",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    previous_ledger_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
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
