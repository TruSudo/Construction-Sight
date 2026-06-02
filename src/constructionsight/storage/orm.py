"""SQLAlchemy ORM models for ConstructionSight."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class SourceRecord(Base):
    """Persisted public-source registry record."""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("source_name", "public_url", name="uq_sources_name_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    jurisdiction_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, default="CA", index=True)
    jurisdiction_type: Mapped[str] = mapped_column(String(64), nullable=False)

    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform_family: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    public_url: Mapped[str] = mapped_column(Text, nullable=False)
    record_categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    search_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_difficulty: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    update_frequency: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(String(64), nullable=False, default="unverified")
    provenance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
