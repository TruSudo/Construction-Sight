"""SQLAlchemy ORM models for ConstructionSight."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class SourceRecord(Base):
    """Persisted public-source registry record."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("source_name", "public_url", name="uq_sources_name_url"),)

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
    extraction_difficulty: Mapped[str] = mapped_column(
        String(64), nullable=False, default="unknown"
    )
    update_frequency: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="unverified"
    )
    provenance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    verification_results: Mapped[list[VerificationRecord]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class VerificationRecord(Base):
    """Persisted source-verification result."""

    __tablename__ = "source_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id"), nullable=True, index=True
    )

    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    public_url: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    url_reachable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    portal_type_detected: Mapped[str] = mapped_column(
        String(128), nullable=False, default="unknown"
    )
    public_search_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    login_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    permit_details_visible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    agenda_packets_visible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pdfs_downloadable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    contractor_owner_applicant_fields_visible: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    evidence_snapshot_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_observations_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    source: Mapped[SourceRecord | None] = relationship(back_populates="verification_results")
