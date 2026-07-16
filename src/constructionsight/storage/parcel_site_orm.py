"""ORM tables for parcel core, longitudinal evidence, assurance, and resolution."""

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
    __table_args__ = (UniqueConstraint("parcel_record_id", name="uq_parcel_core_records_id"),)

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


class ParcelSourceEvidenceRow(Base):
    """Persisted immutable official evidence for one parcel source."""

    __tablename__ = "parcel_source_evidence"
    __table_args__ = (UniqueConstraint("evidence_id", name="uq_parcel_source_evidence_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    evidence_kind: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    observed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field_role_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelSourceVerificationProfileRow(Base):
    """Persisted immutable parcel source verification profile."""

    __tablename__ = "parcel_source_verification_profiles"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            name="uq_parcel_source_verification_profiles_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    coverage_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    observed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    schema_field_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    authoritative_field_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelCountyCoverageReportRow(Base):
    """Persisted immutable countywide parcel coverage-gap report."""

    __tablename__ = "parcel_county_coverage_reports"
    __table_args__ = (UniqueConstraint("report_id", name="uq_parcel_county_coverage_reports_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    county_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    profile_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gap_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_generated_at: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelArcGISCapabilitySnapshotRow(Base):
    """Persisted immutable ArcGIS layer capability snapshot."""

    __tablename__ = "parcel_arcgis_capability_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            name="uq_parcel_arcgis_capability_snapshots_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    observed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    advertised_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    field_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    max_record_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelArcGISProbePlanRow(Base):
    """Persisted immutable bounded ArcGIS probe plan."""

    __tablename__ = "parcel_arcgis_probe_plans"
    __table_args__ = (UniqueConstraint("plan_id", name="uq_parcel_arcgis_probe_plans_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_generated_at: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelArcGISProbeObservationRow(Base):
    """Persisted immutable ArcGIS probe response observation."""

    __tablename__ = "parcel_arcgis_probe_observations"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            name="uq_parcel_arcgis_probe_observations_id",
        ),
        UniqueConstraint(
            "request_id",
            name="uq_parcel_arcgis_probe_observations_request",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    probe_kind: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    observed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelArcGISBulkManifestRow(Base):
    """Persisted immutable count-reconciled ArcGIS bulk rehearsal manifest."""

    __tablename__ = "parcel_arcgis_bulk_manifests"
    __table_args__ = (UniqueConstraint("manifest_id", name="uq_parcel_arcgis_bulk_manifests_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    manifest_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expected_record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    retrieved_record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_completed_at: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelArcGISAcquisitionAssessmentRow(Base):
    """Persisted immutable ArcGIS acquisition readiness assessment."""

    __tablename__ = "parcel_arcgis_acquisition_assessments"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            name="uq_parcel_arcgis_acquisition_assessments_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    bulk_acquisition_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
    )
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gap_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_generated_at: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelArcGISBoundedProofBundleRow(Base):
    """Persisted self-contained bounded ArcGIS proof artifact."""

    __tablename__ = "parcel_arcgis_bounded_proof_bundles"
    __table_args__ = (
        UniqueConstraint(
            "bundle_id",
            name="uq_parcel_arcgis_bounded_proof_bundles_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    assessment_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_created_at: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelRecordObservationRow(Base):
    """Persisted append-only observation of one canonical parcel record."""

    __tablename__ = "parcel_record_observations"
    __table_args__ = (UniqueConstraint("observation_id", name="uq_parcel_record_observations_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parcel_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_record_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    normalized_apn: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_effective_at: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    observed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelCurrentSelectionReportRow(Base):
    """Persisted immutable report of governed parcel current selection."""

    __tablename__ = "parcel_current_selection_reports"
    __table_args__ = (
        UniqueConstraint(
            "selection_report_id",
            name="uq_parcel_current_selection_reports_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    selection_report_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    normalized_apn: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requires_human_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    current_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    ambiguous_source_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    observed_generated_at: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )


class ParcelAssuranceReportRow(Base):
    """Persisted field-level parcel assurance report."""

    __tablename__ = "parcel_assurance_reports"
    __table_args__ = (UniqueConstraint("report_id", name="uq_parcel_assurance_reports_id"),)

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
    __table_args__ = (UniqueConstraint("resolution_id", name="uq_site_resolution_results_id"),)

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
