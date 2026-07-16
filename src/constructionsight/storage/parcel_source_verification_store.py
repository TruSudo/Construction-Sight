"""Immutable storage for parcel source evidence, profiles, and coverage reports."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.parcel_source_verification_models import (
    ParcelCountyCoverageReport,
    ParcelSourceEvidence,
    ParcelSourceVerificationProfile,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelCountyCoverageReportRow,
    ParcelSourceEvidenceRow,
    ParcelSourceVerificationProfileRow,
)

ModelT = TypeVar(
    "ModelT",
    ParcelSourceEvidence,
    ParcelSourceVerificationProfile,
    ParcelCountyCoverageReport,
)
RowT = TypeVar(
    "RowT",
    ParcelSourceEvidenceRow,
    ParcelSourceVerificationProfileRow,
    ParcelCountyCoverageReportRow,
)


def store_parcel_source_evidence(
    session: Session,
    evidence: ParcelSourceEvidence,
) -> ParcelSourceEvidenceRow:
    """Append immutable source evidence with exact idempotent replay."""

    session.flush()
    payload_json = _payload_json(evidence.to_dict())
    existing = session.execute(
        select(ParcelSourceEvidenceRow).where(
            ParcelSourceEvidenceRow.evidence_id == evidence.evidence_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        _require_exact_replay(
            existing.payload_json,
            payload_json,
            "parcel source evidence",
            evidence.evidence_id,
        )
        return existing
    row = ParcelSourceEvidenceRow(
        evidence_id=evidence.evidence_id,
        source_key=evidence.source_key,
        county=evidence.county,
        evidence_kind=evidence.evidence_kind.value,
        observed_at=evidence.observed_at.isoformat(),
        field_role_count=len(evidence.field_roles),
        payload_json=payload_json,
    )
    return _insert(session, row, "parcel source evidence", evidence.evidence_id)


def store_parcel_source_verification_profile(
    session: Session,
    profile: ParcelSourceVerificationProfile,
) -> ParcelSourceVerificationProfileRow:
    """Append an immutable verification profile with exact idempotent replay."""

    session.flush()
    _require_persisted_evidence(session, profile)
    payload_json = _payload_json(profile.to_dict())
    existing = session.execute(
        select(ParcelSourceVerificationProfileRow).where(
            ParcelSourceVerificationProfileRow.profile_id == profile.profile_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        _require_exact_replay(
            existing.payload_json,
            payload_json,
            "parcel source verification",
            profile.profile_id,
        )
        return existing
    row = ParcelSourceVerificationProfileRow(
        profile_id=profile.profile_id,
        source_key=profile.source_key,
        county=profile.county,
        status=profile.status.value,
        coverage_status=profile.coverage_status.value,
        observed_at=profile.observed_at.isoformat(),
        evidence_count=len(profile.evidence_ids),
        schema_field_count=len(profile.schema_fields),
        authoritative_field_count=len(profile.authoritative_fields),
        payload_json=payload_json,
    )
    return _insert(
        session,
        row,
        "parcel source verification",
        profile.profile_id,
    )


def store_parcel_county_coverage_report(
    session: Session,
    report: ParcelCountyCoverageReport,
) -> ParcelCountyCoverageReportRow:
    """Store an immutable coverage report with semantic idempotent replay."""

    session.flush()
    _require_persisted_profiles(session, report)
    payload_json = _payload_json(report.to_dict())
    existing = session.execute(
        select(ParcelCountyCoverageReportRow).where(
            ParcelCountyCoverageReportRow.report_id == report.report_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if _report_semantic_payload(existing.payload_json) != _report_semantic_payload(
            payload_json
        ):
            raise ValueError(f"parcel county coverage identity collision: {report.report_id}")
        return existing
    row = ParcelCountyCoverageReportRow(
        report_id=report.report_id,
        status=report.status.value,
        county_count=len(report.counties),
        profile_count=len(report.profile_ids),
        gap_count=len(report.gaps),
        observed_generated_at=report.generated_at.isoformat(),
        payload_json=payload_json,
    )
    return _insert(session, row, "parcel county coverage", report.report_id)


def load_parcel_source_evidence(
    session: Session,
    evidence_id: str,
) -> ParcelSourceEvidence | None:
    """Load one evidence record and reject indexed/payload drift."""

    row = session.execute(
        select(ParcelSourceEvidenceRow).where(ParcelSourceEvidenceRow.evidence_id == evidence_id)
    ).scalar_one_or_none()
    if row is None:
        return None
    evidence = _validated_model(
        row.payload_json,
        ParcelSourceEvidence,
        "parcel source evidence",
        evidence_id,
    )
    indexed = (
        row.evidence_id,
        row.source_key,
        row.county,
        row.evidence_kind,
        row.observed_at,
        row.field_role_count,
    )
    payload = (
        evidence.evidence_id,
        evidence.source_key,
        evidence.county,
        evidence.evidence_kind.value,
        evidence.observed_at.isoformat(),
        len(evidence.field_roles),
    )
    _require_index_match(indexed, payload, "parcel source evidence", evidence_id)
    return evidence


def load_parcel_source_verification_profiles(
    session: Session,
    *,
    source_key: str | None = None,
    county: str | None = None,
) -> list[ParcelSourceVerificationProfile]:
    """Load verification profiles and reject indexed/payload drift."""

    statement = select(ParcelSourceVerificationProfileRow)
    if source_key is not None:
        statement = statement.where(ParcelSourceVerificationProfileRow.source_key == source_key)
    if county is not None:
        statement = statement.where(ParcelSourceVerificationProfileRow.county == county)
    rows = session.execute(statement.order_by(ParcelSourceVerificationProfileRow.id)).scalars()
    return [_profile_from_row(row) for row in rows]


def load_parcel_county_coverage_report(
    session: Session,
    report_id: str,
) -> ParcelCountyCoverageReport | None:
    """Load one coverage report and reject indexed/payload drift."""

    row = session.execute(
        select(ParcelCountyCoverageReportRow).where(
            ParcelCountyCoverageReportRow.report_id == report_id
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    report = _validated_model(
        row.payload_json,
        ParcelCountyCoverageReport,
        "parcel county coverage",
        report_id,
    )
    indexed = (
        row.report_id,
        row.status,
        row.county_count,
        row.profile_count,
        row.gap_count,
        row.observed_generated_at,
    )
    payload = (
        report.report_id,
        report.status.value,
        len(report.counties),
        len(report.profile_ids),
        len(report.gaps),
        report.generated_at.isoformat(),
    )
    _require_index_match(indexed, payload, "parcel county coverage", report_id)
    return report


def _profile_from_row(
    row: ParcelSourceVerificationProfileRow,
) -> ParcelSourceVerificationProfile:
    profile = _validated_model(
        row.payload_json,
        ParcelSourceVerificationProfile,
        "parcel source verification",
        row.profile_id,
    )
    indexed = (
        row.profile_id,
        row.source_key,
        row.county,
        row.status,
        row.coverage_status,
        row.observed_at,
        row.evidence_count,
        row.schema_field_count,
        row.authoritative_field_count,
    )
    payload = (
        profile.profile_id,
        profile.source_key,
        profile.county,
        profile.status.value,
        profile.coverage_status.value,
        profile.observed_at.isoformat(),
        len(profile.evidence_ids),
        len(profile.schema_fields),
        len(profile.authoritative_fields),
    )
    _require_index_match(
        indexed,
        payload,
        "parcel source verification",
        row.profile_id,
    )
    return profile


def _require_persisted_evidence(
    session: Session,
    profile: ParcelSourceVerificationProfile,
) -> None:
    rows = list(
        session.execute(
            select(ParcelSourceEvidenceRow).where(
                ParcelSourceEvidenceRow.evidence_id.in_(profile.evidence_ids)
            )
        ).scalars()
    )
    evidence = [load_parcel_source_evidence(session, row.evidence_id) for row in rows]
    persisted_ids = {item.evidence_id for item in evidence if item is not None}
    if persisted_ids != set(profile.evidence_ids):
        raise ValueError(
            f"parcel source verification requires persisted evidence: {profile.profile_id}"
        )
    if any(
        item is not None
        and (item.source_key != profile.source_key or item.county != profile.county)
        for item in evidence
    ):
        raise ValueError(
            f"parcel source verification evidence scope mismatch: {profile.profile_id}"
        )


def _require_persisted_profiles(
    session: Session,
    report: ParcelCountyCoverageReport,
) -> None:
    rows = list(
        session.execute(
            select(ParcelSourceVerificationProfileRow).where(
                ParcelSourceVerificationProfileRow.profile_id.in_(report.profile_ids)
            )
        ).scalars()
    )
    profiles = [_profile_from_row(row) for row in rows]
    if {profile.profile_id for profile in profiles} != set(report.profile_ids):
        raise ValueError(f"parcel county coverage requires persisted profiles: {report.report_id}")


def _insert(
    session: Session,
    row: RowT,
    label: str,
    record_id: str,
) -> RowT:
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(f"{label} already exists: {record_id}") from exc
    return row


def _validated_model(
    payload_json: str,
    model_type: type[ModelT],
    label: str,
    record_id: str,
) -> ModelT:
    payload = _decode_object(payload_json, label, record_id)
    try:
        return model_type.model_validate(payload)
    except ValueError as exc:
        raise ValueError(f"invalid {label} payload: {record_id}") from exc


def _decode_object(payload_json: str, label: str, record_id: str) -> dict[str, Any]:
    try:
        payload: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed {label} payload JSON: {record_id}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} payload must be a JSON object: {record_id}")
    return {str(key): value for key, value in payload.items()}


def _require_exact_replay(
    existing_payload: str,
    replay_payload: str,
    label: str,
    record_id: str,
) -> None:
    if existing_payload != replay_payload:
        raise ValueError(f"{label} identity collision: {record_id}")


def _require_index_match(
    indexed: tuple[object, ...],
    payload: tuple[object, ...],
    label: str,
    record_id: str,
) -> None:
    if indexed != payload:
        raise ValueError(f"{label} indexed fields disagree with payload: {record_id}")


def _report_semantic_payload(payload_json: str) -> str:
    payload = _decode_object(payload_json, "parcel county coverage", "semantic replay")
    payload.pop("generated_at", None)
    return _payload_json(payload)


def _payload_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True)
