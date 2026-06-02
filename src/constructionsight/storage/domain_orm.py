"""ORM models for normalized ConstructionSight domain records.

These tables intentionally store normalized public-record objects separately from
source registry records. They provide a stable persistence target for adapters
without forcing adapter-specific fields into the core registry tables.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=func.now())


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=func.now())


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=func.now())


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=func.now())
