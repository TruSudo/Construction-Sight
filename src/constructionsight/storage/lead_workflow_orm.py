"""ORM tables for post-enrichment lead workflow records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class OpportunityEnrichmentReportRecord(Base):
    """Persisted opportunity enrichment report."""

    __tablename__ = "opportunity_enrichment_reports"
    __table_args__ = (
        UniqueConstraint("report_id", name="uq_opportunity_enrichment_reports_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    base_candidate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    confidence_band: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scoring_profile_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scoring_profile_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    next_action: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
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


class LeadReviewPackageRecord(Base):
    """Persisted lead review package."""

    __tablename__ = "lead_review_packages"
    __table_args__ = (
        UniqueConstraint("package_id", name="uq_lead_review_packages_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    base_candidate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
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


class LeadFingerprintRecord(Base):
    """Persisted lead duplicate-detection fingerprint."""

    __tablename__ = "lead_fingerprints"
    __table_args__ = (
        UniqueConstraint("fingerprint_key", name="uq_lead_fingerprints_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    base_candidate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    site_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_record_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    normalized_title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
    )
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
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


class LeadDuplicateResultRecord(Base):
    """Persisted lead duplicate check result."""

    __tablename__ = "lead_duplicate_results"
    __table_args__ = (
        UniqueConstraint("result_id", name="uq_lead_duplicate_results_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_fingerprint_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    base_candidate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
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


class LeadWorkflowRecordRow(Base):
    """Persisted lead workflow record."""

    __tablename__ = "lead_workflows"
    __table_args__ = (
        UniqueConstraint("workflow_id", name="uq_lead_workflows_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    package_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    base_candidate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    fingerprint_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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


class LeadWorkflowEventRecord(Base):
    """Persisted lead workflow event."""

    __tablename__ = "lead_workflow_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_lead_workflow_events_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    current_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
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


class ResultLedgerRecordRow(Base):
    """Persisted result ledger row."""

    __tablename__ = "result_ledgers"
    __table_args__ = (
        UniqueConstraint("ledger_id", name="uq_result_ledgers_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ledger_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    package_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decided_date: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    gross_value: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    gross_value_minor: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    share_status: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    share_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
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


class ResultShareRecordRow(Base):
    """Persisted calculated result-share record."""

    __tablename__ = "result_share_records"
    __table_args__ = (
        UniqueConstraint("share_record_id", name="uq_result_share_records_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gross_value: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    gross_value_minor: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    share_rate: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    share_rate_ppm: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    share_value: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    share_value_minor: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
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
