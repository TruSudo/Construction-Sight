"""ORM models for normalized ConstructionSight domain records.

These tables intentionally store normalized public-record objects separately from
source registry records. They provide a stable persistence target for adapters
without forcing adapter-specific fields into the core registry tables.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


class SiteRecord(Base):
    """Persisted normalized site or parcel record."""

    __tablename__ = "domain_sites"
    __table_args__ = (UniqueConstraint("site_key", name="uq_domain_sites_site_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, default="CA", index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    apn: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot_size_acres: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class EntityRecord(Base):
    """Persisted normalized named-entity record."""

    __tablename__ = "domain_entities"
    __table_args__ = (UniqueConstraint("entity_key", name="uq_domain_entities_entity_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown", index=True)
    license_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    business_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    county: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, default="CA", index=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class PermitDomainRecord(Base):
    """Persisted normalized permit record."""

    __tablename__ = "domain_permits"
    __table_args__ = (UniqueConstraint("permit_key", name="uq_domain_permits_permit_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    permit_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    permit_number: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    permit_type: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    applied_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    finaled_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    valuation: Mapped[float | None] = mapped_column(Float, nullable=True)
    square_feet: Mapped[float | None] = mapped_column(Float, nullable=True)
    site_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class PlanningDomainRecord(Base):
    """Persisted normalized planning case record."""

    __tablename__ = "domain_planning_cases"
    __table_args__ = (UniqueConstraint("case_key", name="uq_domain_planning_cases_case_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    case_number: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    case_type: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    filed_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    hearing_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    approval_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class CeqaDomainRecord(Base):
    """Persisted normalized CEQA record."""

    __tablename__ = "domain_ceqa_records"
    __table_args__ = (UniqueConstraint("ceqa_key", name="uq_domain_ceqa_records_ceqa_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ceqa_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    county: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lead_agency: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    document_type: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    state_clearinghouse_number: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    project_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class AgendaDomainRecord(Base):
    """Persisted normalized agenda item record."""

    __tablename__ = "domain_agenda_items"
    __table_args__ = (UniqueConstraint("agenda_key", name="uq_domain_agenda_items_agenda_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agenda_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    meeting_body: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    item_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_urls_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    site_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class DocumentDomainRecord(Base):
    """Persisted normalized document record."""

    __tablename__ = "domain_documents"
    __table_args__ = (UniqueConstraint("document_key", name="uq_domain_documents_document_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    text_extract: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class RelationshipDomainRecord(Base):
    """Persisted normalized relationship record."""

    __tablename__ = "domain_relationships"
    __table_args__ = (
        UniqueConstraint("relationship_key", name="uq_domain_relationships_relationship_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    relationship_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
