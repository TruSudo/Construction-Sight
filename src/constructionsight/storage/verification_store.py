"""Persistence helpers for source verification results."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.models import SourceVerificationResult
from constructionsight.storage.orm import SourceRecord, VerificationRecord


class VerificationStore:
    """Repository object for persisted source-verification results."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_result(self, result: SourceVerificationResult) -> VerificationRecord:
        """Persist a verification result and link it to a source when possible."""

        source = self.session.scalar(
            select(SourceRecord).where(
                SourceRecord.source_name == result.source_name,
                SourceRecord.public_url == str(result.public_url),
            )
        )

        record = VerificationRecord(
            source_id=source.id if source is not None else None,
            source_name=result.source_name,
            public_url=str(result.public_url),
            checked_at=result.checked_at,
            url_reachable=result.url_reachable,
            portal_type_detected=result.portal_type_detected.value,
            public_search_available=result.public_search_available,
            login_required=result.login_required,
            permit_details_visible=result.permit_details_visible,
            agenda_packets_visible=result.agenda_packets_visible,
            pdfs_downloadable=result.pdfs_downloadable,
            contractor_owner_applicant_fields_visible=result.contractor_owner_applicant_fields_visible,
            evidence_snapshot_text=result.evidence_snapshot_text,
            confidence_score=result.confidence_score,
            notes=result.notes,
            raw_observations_json=json.dumps(result.raw_observations, sort_keys=True, default=str),
        )
        self.session.add(record)

        if source is not None:
            source.confidence_score = result.confidence_score
            source.last_checked_date = result.checked_at.date()
            if result.url_reachable and result.confidence_score >= 60:
                source.verification_status = "verified"
            elif result.url_reachable:
                source.verification_status = "partial"
            else:
                source.verification_status = "failed"

        self.session.flush()
        return record

    def list_latest(self, limit: int = 20) -> list[VerificationRecord]:
        """Return latest verification records."""

        self.session.flush()
        return list(
            self.session.scalars(
                select(VerificationRecord)
                .order_by(VerificationRecord.checked_at.desc())
                .limit(limit)
            ).all()
        )
