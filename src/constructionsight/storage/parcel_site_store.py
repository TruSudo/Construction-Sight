"""Store helpers for parcel core, longitudinal evidence, assurance, and resolution."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.parcel_assurance_models import (
    ParcelAssuranceReport,
    ParcelAssuranceStatus,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_observation_models import (
    ParcelCurrentSelectionReport,
    ParcelRecordObservation,
    ParcelSourceSelectionStatus,
)
from constructionsight.site_resolution_models import SiteResolutionResult
from constructionsight.storage.parcel_site_orm import (
    ParcelAssuranceReportRow,
    ParcelCoreRecordRow,
    ParcelCurrentSelectionReportRow,
    ParcelRecordObservationRow,
    SiteResolutionResultRow,
)


def store_parcel_record_observation(
    session: Session,
    observation: ParcelRecordObservation,
) -> ParcelRecordObservationRow:
    """Append one immutable parcel observation with exact idempotent replay."""

    session.flush()
    payload_json = _payload_json(observation.to_dict())
    existing = session.execute(
        select(ParcelRecordObservationRow).where(
            ParcelRecordObservationRow.observation_id == observation.observation_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.payload_json != payload_json:
            raise ValueError(
                f"parcel observation identity collision: {observation.observation_id}"
            )
        return existing
    record = observation.record
    row = ParcelRecordObservationRow(
        observation_id=observation.observation_id,
        parcel_record_id=record.parcel_record_id,
        source_key=record.source_key,
        source_record_id=record.source_record_id,
        normalized_apn=record.normalized_apn,
        county=record.county,
        source_effective_at=(
            record.source_updated_at.isoformat()
            if record.source_updated_at is not None
            else None
        ),
        observed_at=record.created_at.isoformat(),
        record_digest=observation.record_digest,
        content_digest=observation.content_digest,
        payload_json=payload_json,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(
            f"parcel observation already exists: {observation.observation_id}"
        ) from exc
    return row


def store_parcel_current_selection_report(
    session: Session,
    report: ParcelCurrentSelectionReport,
) -> ParcelCurrentSelectionReportRow:
    """Store one immutable derived selection report with semantic idempotency."""

    session.flush()
    payload_json = _payload_json(report.to_dict())
    existing = session.execute(
        select(ParcelCurrentSelectionReportRow).where(
            ParcelCurrentSelectionReportRow.selection_report_id
            == report.selection_report_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if _selection_semantic_payload(existing.payload_json) != (
            _selection_semantic_payload(payload_json)
        ):
            raise ValueError(
                "parcel current-selection identity collision: "
                f"{report.selection_report_id}"
            )
        return existing
    ambiguous_source_count = sum(
        item.status is ParcelSourceSelectionStatus.AMBIGUOUS
        for item in report.source_selections
    )
    row = ParcelCurrentSelectionReportRow(
        selection_report_id=report.selection_report_id,
        normalized_apn=report.normalized_apn,
        county=report.county,
        status=report.status.value,
        requires_human_review=report.requires_human_review,
        source_count=report.source_count,
        current_observation_count=len(report.current_observation_ids),
        ambiguous_source_count=ambiguous_source_count,
        observed_generated_at=report.generated_at.isoformat(),
        payload_json=payload_json,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(
            "parcel current-selection report already exists: "
            f"{report.selection_report_id}"
        ) from exc
    return row


def load_parcel_record_observations(
    session: Session,
    *,
    normalized_apn: str,
    county: str,
    source_key: str | None = None,
) -> list[ParcelRecordObservation]:
    """Load immutable observations and reject indexed/payload integrity drift."""

    statement = select(ParcelRecordObservationRow).where(
        ParcelRecordObservationRow.normalized_apn == normalized_apn,
        ParcelRecordObservationRow.county == county,
    )
    if source_key is not None:
        statement = statement.where(ParcelRecordObservationRow.source_key == source_key)
    rows = session.execute(
        statement.order_by(ParcelRecordObservationRow.id)
    ).scalars()
    return [_parcel_observation_from_row(row) for row in rows]


def load_parcel_current_selection_report(
    session: Session,
    selection_report_id: str,
) -> ParcelCurrentSelectionReport | None:
    """Load one current-selection report and reject indexed/payload drift."""

    row = session.execute(
        select(ParcelCurrentSelectionReportRow).where(
            ParcelCurrentSelectionReportRow.selection_report_id
            == selection_report_id
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    payload = _decode_object(
        row.payload_json,
        record_label="parcel current-selection",
        record_id=selection_report_id,
    )
    try:
        report = ParcelCurrentSelectionReport.model_validate(payload)
    except ValueError as exc:
        raise ValueError(
            f"invalid parcel current-selection payload: {selection_report_id}"
        ) from exc
    indexed = (
        row.selection_report_id,
        row.normalized_apn,
        row.county,
        row.status,
        row.requires_human_review,
        row.source_count,
        row.current_observation_count,
        row.ambiguous_source_count,
        row.observed_generated_at,
    )
    payload_values = (
        report.selection_report_id,
        report.normalized_apn,
        report.county,
        report.status.value,
        report.requires_human_review,
        report.source_count,
        len(report.current_observation_ids),
        sum(
            item.status is ParcelSourceSelectionStatus.AMBIGUOUS
            for item in report.source_selections
        ),
        report.generated_at.isoformat(),
    )
    if indexed != payload_values:
        raise ValueError(
            "parcel current-selection indexed fields disagree with payload: "
            f"{selection_report_id}"
        )
    return report


def store_parcel_assurance_report(
    session: Session,
    report: ParcelAssuranceReport,
) -> ParcelAssuranceReportRow:
    """Insert one immutable semantic assurance report or accept exact replay."""

    session.flush()
    if report.report_id != report.computed_report_id():
        raise ValueError("parcel assurance report identity does not match semantic content")
    payload_json = _payload_json(report.to_dict())
    existing = session.execute(
        select(ParcelAssuranceReportRow).where(
            ParcelAssuranceReportRow.report_id == report.report_id
        )
    ).scalar_one_or_none()
    conflict_count = sum(
        assurance.status == ParcelAssuranceStatus.CONFLICT
        for assurance in report.field_assurances
    )
    missing_count = sum(
        assurance.status == ParcelAssuranceStatus.MISSING
        for assurance in report.field_assurances
    )
    requires_human_review = any(
        assurance.requires_human_review for assurance in report.field_assurances
    )
    if existing is None:
        existing = ParcelAssuranceReportRow(
            report_id=report.report_id,
            normalized_apn=report.normalized_apn,
            county=report.county,
            review_status=report.review_status.value,
            requires_human_review=requires_human_review,
            source_count=report.source_count,
            independent_lineage_count=report.independent_lineage_count,
            claim_count=len(report.claims),
            conflict_count=conflict_count,
            missing_count=missing_count,
            observed_created_at=report.generated_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    if _semantic_replay_payload(existing.payload_json, "generated_at") != (
        _semantic_replay_payload(payload_json, "generated_at")
    ):
        raise ValueError("persisted parcel assurance reports are immutable")
    return existing


def store_parcel_core_record(
    session: Session,
    parcel: ParcelCoreRecord,
) -> ParcelCoreRecordRow:
    """Insert or update a parcel core record."""

    session.flush()
    payload_json = _payload_json(parcel.to_dict())
    existing = session.execute(
        select(ParcelCoreRecordRow).where(
            ParcelCoreRecordRow.parcel_record_id == parcel.parcel_record_id
        )
    ).scalar_one_or_none()
    geometry = parcel.geometry
    if existing is None:
        existing = ParcelCoreRecordRow(
            parcel_record_id=parcel.parcel_record_id,
            source_key=parcel.source_key,
            source_record_id=parcel.source_record_id,
            apn=parcel.apn,
            normalized_apn=parcel.normalized_apn,
            county=parcel.county,
            state=parcel.state,
            address=parcel.address,
            normalized_address=parcel.normalized_address,
            jurisdiction=parcel.jurisdiction,
            zoning=parcel.zoning,
            land_use=parcel.land_use,
            acreage=parcel.acreage,
            geometry_kind=geometry.geometry_kind.value if geometry else None,
            geometry_hash=geometry.geometry_hash if geometry else None,
            centroid_latitude=geometry.centroid_latitude if geometry else None,
            centroid_longitude=geometry.centroid_longitude if geometry else None,
            envelope_min_latitude=geometry.envelope_min_latitude if geometry else None,
            envelope_min_longitude=geometry.envelope_min_longitude if geometry else None,
            envelope_max_latitude=geometry.envelope_max_latitude if geometry else None,
            envelope_max_longitude=geometry.envelope_max_longitude if geometry else None,
            spatial_reference=geometry.spatial_reference if geometry else None,
            source_updated_at=(
                parcel.source_updated_at.isoformat() if parcel.source_updated_at else None
            ),
            observed_created_at=parcel.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.source_key = parcel.source_key
    existing.source_record_id = parcel.source_record_id
    existing.apn = parcel.apn
    existing.normalized_apn = parcel.normalized_apn
    existing.county = parcel.county
    existing.state = parcel.state
    existing.address = parcel.address
    existing.normalized_address = parcel.normalized_address
    existing.jurisdiction = parcel.jurisdiction
    existing.zoning = parcel.zoning
    existing.land_use = parcel.land_use
    existing.acreage = parcel.acreage
    existing.geometry_kind = geometry.geometry_kind.value if geometry else None
    existing.geometry_hash = geometry.geometry_hash if geometry else None
    existing.centroid_latitude = geometry.centroid_latitude if geometry else None
    existing.centroid_longitude = geometry.centroid_longitude if geometry else None
    existing.envelope_min_latitude = geometry.envelope_min_latitude if geometry else None
    existing.envelope_min_longitude = geometry.envelope_min_longitude if geometry else None
    existing.envelope_max_latitude = geometry.envelope_max_latitude if geometry else None
    existing.envelope_max_longitude = geometry.envelope_max_longitude if geometry else None
    existing.spatial_reference = geometry.spatial_reference if geometry else None
    existing.source_updated_at = (
        parcel.source_updated_at.isoformat() if parcel.source_updated_at else None
    )
    existing.observed_created_at = parcel.created_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_site_resolution_result(
    session: Session,
    result: SiteResolutionResult,
) -> SiteResolutionResultRow:
    """Insert one immutable semantic site-resolution result or accept exact replay."""

    session.flush()
    if result.resolution_id != result.computed_resolution_id():
        raise ValueError("site-resolution identity does not match semantic content")
    payload_json = _payload_json(result.to_dict())
    existing = session.execute(
        select(SiteResolutionResultRow).where(
            SiteResolutionResultRow.resolution_id == result.resolution_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = SiteResolutionResultRow(
            resolution_id=result.resolution_id,
            source_name=result.source_name,
            evidence_id=result.evidence_id,
            status=result.status.value,
            primary_site_key=result.primary_site_key,
            candidate_count=len(result.candidates),
            conflict_count=len(result.conflicts),
            limitation_count=len(result.limitations),
            observed_created_at=result.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    if _semantic_replay_payload(existing.payload_json, "created_at") != (
        _semantic_replay_payload(payload_json, "created_at")
    ):
        raise ValueError("persisted site-resolution results are immutable")
    return existing


def _payload_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON payload."""

    return json.dumps(payload, sort_keys=True)


def _semantic_replay_payload(payload_json: str, timestamp_field: str) -> str:
    """Return immutable derived-result semantics without receipt timestamp."""

    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        raise ValueError("derived result payload must be a JSON object")
    payload.pop(timestamp_field, None)
    return _payload_json({str(key): value for key, value in payload.items()})


def _parcel_observation_from_row(
    row: ParcelRecordObservationRow,
) -> ParcelRecordObservation:
    payload = _decode_object(
        row.payload_json,
        record_label="parcel observation",
        record_id=row.observation_id,
    )
    try:
        observation = ParcelRecordObservation.model_validate(payload)
    except ValueError as exc:
        raise ValueError(
            f"invalid parcel observation payload: {row.observation_id}"
        ) from exc
    record = observation.record
    indexed = (
        row.observation_id,
        row.parcel_record_id,
        row.source_key,
        row.source_record_id,
        row.normalized_apn,
        row.county,
        row.source_effective_at,
        row.observed_at,
        row.record_digest,
        row.content_digest,
    )
    payload_values = (
        observation.observation_id,
        record.parcel_record_id,
        record.source_key,
        record.source_record_id,
        record.normalized_apn,
        record.county,
        record.source_updated_at.isoformat()
        if record.source_updated_at is not None
        else None,
        record.created_at.isoformat(),
        observation.record_digest,
        observation.content_digest,
    )
    if indexed != payload_values:
        raise ValueError(
            "parcel observation indexed fields disagree with payload: "
            f"{row.observation_id}"
        )
    return observation


def _decode_object(
    payload_json: str,
    *,
    record_label: str,
    record_id: str,
) -> dict[str, Any]:
    try:
        payload: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"malformed {record_label} payload JSON: {record_id}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{record_label} payload must be a JSON object: {record_id}")
    return {str(key): value for key, value in payload.items()}


def _selection_semantic_payload(payload_json: str) -> str:
    """Return selection content excluding its derivation timestamp."""

    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        raise ValueError("parcel current-selection payload must be a JSON object")
    payload.pop("generated_at", None)
    return _payload_json({str(key): value for key, value in payload.items()})
