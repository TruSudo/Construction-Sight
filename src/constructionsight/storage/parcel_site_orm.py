"""ORM tables for parcel core and site-resolution records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class ParcelCoreRecordRow(Base):
    """Persisted canonical parcel core record."""

    __tablename__ = "parcel_core_records"
    __table_args__ = (
        UniqueConstraint("parcel_record_id", name="uq_parcel_core_records_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_record_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    apn: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    normalized_apn: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    normalized_address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
    )
    jurisdiction: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    zoning: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    land_use: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    acreage: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    geometry_kind: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    geometry_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    centroid_latitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    centroid_longitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    envelope_min_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    envelope_min_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    envelope_max_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    envelope_max_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    spatial_reference: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    observed_created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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


class ParcelAssuranceReportRow(Base):
    """Persisted field-level parcel assurance report."""

    __tablename__ = "parcel_assurance_reports"
    __table_args__ = (
        UniqueConstraint("report_id", name="uq_parcel_assurance_reports_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_apn: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requires_human_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    independent_lineage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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


class SiteResolutionResultRow(Base):
    """Persisted source-neutral site-resolution result."""

    __tablename__ = "site_resolution_results"
    __table_args__ = (
        UniqueConstraint("resolution_id", name="uq_site_resolution_results_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resolution_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    evidence_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    primary_site_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    limitation_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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
