"""Append-only operator staging evidence, separate from approved commercial leads."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from constructionsight.storage.orm import Base


class SourceCandidateDocketRow(Base):
    """One immutable-by-supported-API normalized source review snapshot."""

    __tablename__ = "source_candidate_review_docket"
    __table_args__ = (
        UniqueConstraint("stage_id", name="uq_source_candidate_docket_stage"),
        UniqueConstraint("preview_id", name="uq_source_candidate_docket_preview"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    preview_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    record_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_json: Mapped[str] = mapped_column(Text, nullable=False)
    preview_payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_integrity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    authorization_decision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_audit_identity: Mapped[str] = mapped_column(Text, nullable=False)
    reason_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False)
