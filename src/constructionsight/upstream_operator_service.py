"""Read-safe operator service for persisted upstream intelligence records."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.storage.movement_identity_orm import (
    ContractorIdentityRecord,
    DecisionRecordRow,
    PermitSnapshotRecord,
    PermitTransitionRecord,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelAssuranceReportRow,
    ParcelCoreRecordRow,
    SiteResolutionResultRow,
)
from constructionsight.upstream_operator_models import (
    UpstreamOperatorRecord,
    UpstreamOperatorRecordKind,
)


class UpstreamOperatorError(ValueError):
    """Raised when upstream operator data is absent, malformed, or unsupported."""


_FILTER_SUPPORT: dict[UpstreamOperatorRecordKind, frozenset[str]] = {
    UpstreamOperatorRecordKind.PERMIT_SNAPSHOT: frozenset(
        {"status", "source_key", "source_record_id", "site_key"}
    ),
    UpstreamOperatorRecordKind.PERMIT_TRANSITION: frozenset(
        {"source_key", "source_record_id"}
    ),
    UpstreamOperatorRecordKind.CONTRACTOR: frozenset({"status"}),
    UpstreamOperatorRecordKind.DECISION: frozenset(
        {"source_key", "source_record_id", "site_key", "apn"}
    ),
    UpstreamOperatorRecordKind.PARCEL: frozenset(
        {"source_key", "source_record_id", "apn", "county"}
    ),
    UpstreamOperatorRecordKind.PARCEL_ASSURANCE: frozenset(
        {"status", "apn", "county"}
    ),
    UpstreamOperatorRecordKind.SITE_RESOLUTION: frozenset({"status", "site_key"}),
}


def list_upstream_operator_records(
    session: Session,
    record_kind: UpstreamOperatorRecordKind,
    *,
    limit: int = 100,
    status: str | None = None,
    source_key: str | None = None,
    source_record_id: str | None = None,
    site_key: str | None = None,
    apn: str | None = None,
    county: str | None = None,
) -> list[UpstreamOperatorRecord]:
    """Return newest upstream records using only kind-supported filters."""

    if limit < 1 or limit > 1000:
        raise UpstreamOperatorError("limit must be between 1 and 1000")
    _validate_filters(
        record_kind,
        status=status,
        source_key=source_key,
        source_record_id=source_record_id,
        site_key=site_key,
        apn=apn,
        county=county,
    )

    if record_kind == UpstreamOperatorRecordKind.PERMIT_SNAPSHOT:
        snapshot_statement = select(PermitSnapshotRecord)
        if status is not None:
            snapshot_statement = snapshot_statement.where(
                PermitSnapshotRecord.status == status
            )
        if source_key is not None:
            snapshot_statement = snapshot_statement.where(
                PermitSnapshotRecord.source_key == source_key
            )
        if source_record_id is not None:
            snapshot_statement = snapshot_statement.where(
                PermitSnapshotRecord.source_record_id == source_record_id
            )
        if site_key is not None:
            snapshot_statement = snapshot_statement.where(
                PermitSnapshotRecord.site_key == site_key
            )
        snapshot_rows = session.execute(
            snapshot_statement.order_by(PermitSnapshotRecord.id.desc()).limit(limit)
        ).scalars()
        return [
            _permit_snapshot_record(snapshot_row) for snapshot_row in snapshot_rows
        ]

    if record_kind == UpstreamOperatorRecordKind.PERMIT_TRANSITION:
        transition_statement = select(PermitTransitionRecord)
        if source_key is not None:
            transition_statement = transition_statement.where(
                PermitTransitionRecord.source_key == source_key
            )
        if source_record_id is not None:
            transition_statement = transition_statement.where(
                PermitTransitionRecord.source_record_id == source_record_id
            )
        transition_rows = session.execute(
            transition_statement.order_by(PermitTransitionRecord.id.desc()).limit(
                limit
            )
        ).scalars()
        return [
            _permit_transition_record(transition_row)
            for transition_row in transition_rows
        ]

    if record_kind == UpstreamOperatorRecordKind.CONTRACTOR:
        contractor_statement = select(ContractorIdentityRecord)
        if status is not None:
            contractor_statement = contractor_statement.where(
                ContractorIdentityRecord.status == status
            )
        contractor_rows = session.execute(
            contractor_statement.order_by(ContractorIdentityRecord.id.desc()).limit(
                limit
            )
        ).scalars()
        return [
            _contractor_record(contractor_row) for contractor_row in contractor_rows
        ]

    if record_kind == UpstreamOperatorRecordKind.DECISION:
        decision_statement = select(DecisionRecordRow)
        if source_key is not None:
            decision_statement = decision_statement.where(
                DecisionRecordRow.source_key == source_key
            )
        if source_record_id is not None:
            decision_statement = decision_statement.where(
                DecisionRecordRow.source_record_id == source_record_id
            )
        if site_key is not None:
            decision_statement = decision_statement.where(
                DecisionRecordRow.site_key == site_key
            )
        if apn is not None:
            decision_statement = decision_statement.where(
                DecisionRecordRow.apn == apn
            )
        decision_rows = session.execute(
            decision_statement.order_by(DecisionRecordRow.id.desc()).limit(limit)
        ).scalars()
        return [_decision_record(decision_row) for decision_row in decision_rows]

    if record_kind == UpstreamOperatorRecordKind.PARCEL:
        parcel_statement = select(ParcelCoreRecordRow)
        if source_key is not None:
            parcel_statement = parcel_statement.where(
                ParcelCoreRecordRow.source_key == source_key
            )
        if source_record_id is not None:
            parcel_statement = parcel_statement.where(
                ParcelCoreRecordRow.source_record_id == source_record_id
            )
        if apn is not None:
            parcel_statement = parcel_statement.where(ParcelCoreRecordRow.apn == apn)
        if county is not None:
            parcel_statement = parcel_statement.where(
                ParcelCoreRecordRow.county == county
            )
        parcel_rows = session.execute(
            parcel_statement.order_by(ParcelCoreRecordRow.id.desc()).limit(limit)
        ).scalars()
        return [_parcel_record(parcel_row) for parcel_row in parcel_rows]

    if record_kind == UpstreamOperatorRecordKind.PARCEL_ASSURANCE:
        assurance_statement = select(ParcelAssuranceReportRow)
        if status is not None:
            assurance_statement = assurance_statement.where(
                ParcelAssuranceReportRow.review_status == status
            )
        if apn is not None:
            assurance_statement = assurance_statement.where(
                ParcelAssuranceReportRow.normalized_apn == apn
            )
        if county is not None:
            assurance_statement = assurance_statement.where(
                ParcelAssuranceReportRow.county == county
            )
        assurance_rows = session.execute(
            assurance_statement.order_by(ParcelAssuranceReportRow.id.desc()).limit(
                limit
            )
        ).scalars()
        return [
            _parcel_assurance_record(assurance_row)
            for assurance_row in assurance_rows
        ]

    resolution_statement = select(SiteResolutionResultRow)
    if status is not None:
        resolution_statement = resolution_statement.where(
            SiteResolutionResultRow.status == status
        )
    if site_key is not None:
        resolution_statement = resolution_statement.where(
            SiteResolutionResultRow.primary_site_key == site_key
        )
    resolution_rows = session.execute(
        resolution_statement.order_by(SiteResolutionResultRow.id.desc()).limit(limit)
    ).scalars()
    return [
        _site_resolution_record(resolution_row)
        for resolution_row in resolution_rows
    ]


def get_upstream_operator_record(
    session: Session,
    record_kind: UpstreamOperatorRecordKind,
    record_id: str,
) -> UpstreamOperatorRecord | None:
    """Return one persisted upstream record by canonical identifier."""

    if record_kind == UpstreamOperatorRecordKind.PERMIT_SNAPSHOT:
        snapshot_row = session.execute(
            select(PermitSnapshotRecord).where(
                PermitSnapshotRecord.snapshot_id == record_id
            )
        ).scalar_one_or_none()
        return (
            None
            if snapshot_row is None
            else _permit_snapshot_record(snapshot_row)
        )
    if record_kind == UpstreamOperatorRecordKind.PERMIT_TRANSITION:
        transition_row = session.execute(
            select(PermitTransitionRecord).where(
                PermitTransitionRecord.transition_id == record_id
            )
        ).scalar_one_or_none()
        return (
            None
            if transition_row is None
            else _permit_transition_record(transition_row)
        )
    if record_kind == UpstreamOperatorRecordKind.CONTRACTOR:
        contractor_row = session.execute(
            select(ContractorIdentityRecord).where(
                ContractorIdentityRecord.contractor_key == record_id
            )
        ).scalar_one_or_none()
        return (
            None if contractor_row is None else _contractor_record(contractor_row)
        )
    if record_kind == UpstreamOperatorRecordKind.DECISION:
        decision_row = session.execute(
            select(DecisionRecordRow).where(
                DecisionRecordRow.decision_key == record_id
            )
        ).scalar_one_or_none()
        return None if decision_row is None else _decision_record(decision_row)
    if record_kind == UpstreamOperatorRecordKind.PARCEL:
        parcel_row = session.execute(
            select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.parcel_record_id == record_id
            )
        ).scalar_one_or_none()
        return None if parcel_row is None else _parcel_record(parcel_row)
    if record_kind == UpstreamOperatorRecordKind.PARCEL_ASSURANCE:
        assurance_row = session.execute(
            select(ParcelAssuranceReportRow).where(
                ParcelAssuranceReportRow.report_id == record_id
            )
        ).scalar_one_or_none()
        return (
            None
            if assurance_row is None
            else _parcel_assurance_record(assurance_row)
        )
    resolution_row = session.execute(
        select(SiteResolutionResultRow).where(
            SiteResolutionResultRow.resolution_id == record_id
        )
    ).scalar_one_or_none()
    return (
        None
        if resolution_row is None
        else _site_resolution_record(resolution_row)
    )


def _validate_filters(
    record_kind: UpstreamOperatorRecordKind,
    **filters: str | None,
) -> None:
    supported = _FILTER_SUPPORT[record_kind]
    unsupported = [
        name
        for name, value in filters.items()
        if value is not None and name not in supported
    ]
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise UpstreamOperatorError(
            f"unsupported filter(s) for {record_kind.value} records: {names}"
        )


def _payload(
    payload_json: str,
    kind: UpstreamOperatorRecordKind,
    record_id: str,
) -> dict[str, Any]:
    try:
        data: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise UpstreamOperatorError(
            f"malformed {kind.value} payload JSON for record: {record_id}"
        ) from exc
    if not isinstance(data, dict):
        raise UpstreamOperatorError(
            f"{kind.value} payload must be a JSON object for record: {record_id}"
        )
    return {str(key): value for key, value in data.items()}


def _permit_snapshot_record(row: PermitSnapshotRecord) -> UpstreamOperatorRecord:
    return UpstreamOperatorRecord(
        record_kind=UpstreamOperatorRecordKind.PERMIT_SNAPSHOT,
        record_id=row.snapshot_id,
        status=row.status,
        source_key=row.source_key,
        source_record_id=row.source_record_id,
        site_key=row.site_key,
        observed_at=row.observed_at,
        payload=_payload(
            row.payload_json,
            UpstreamOperatorRecordKind.PERMIT_SNAPSHOT,
            row.snapshot_id,
        ),
    )


def _permit_transition_record(
    row: PermitTransitionRecord,
) -> UpstreamOperatorRecord:
    return UpstreamOperatorRecord(
        record_kind=UpstreamOperatorRecordKind.PERMIT_TRANSITION,
        record_id=row.transition_id,
        status=row.transition_kind,
        source_key=row.source_key,
        source_record_id=row.source_record_id,
        observed_at=row.detected_at,
        payload=_payload(
            row.payload_json,
            UpstreamOperatorRecordKind.PERMIT_TRANSITION,
            row.transition_id,
        ),
    )


def _contractor_record(row: ContractorIdentityRecord) -> UpstreamOperatorRecord:
    return UpstreamOperatorRecord(
        record_kind=UpstreamOperatorRecordKind.CONTRACTOR,
        record_id=row.contractor_key,
        status=row.status,
        confidence_score=row.confidence_score,
        payload=_payload(
            row.payload_json,
            UpstreamOperatorRecordKind.CONTRACTOR,
            row.contractor_key,
        ),
    )


def _decision_record(row: DecisionRecordRow) -> UpstreamOperatorRecord:
    return UpstreamOperatorRecord(
        record_kind=UpstreamOperatorRecordKind.DECISION,
        record_id=row.decision_key,
        status=row.decision_kind,
        source_key=row.source_key,
        source_record_id=row.source_record_id,
        site_key=row.site_key,
        apn=row.apn,
        confidence_score=row.confidence_score,
        payload=_payload(
            row.payload_json,
            UpstreamOperatorRecordKind.DECISION,
            row.decision_key,
        ),
    )


def _parcel_record(row: ParcelCoreRecordRow) -> UpstreamOperatorRecord:
    return UpstreamOperatorRecord(
        record_kind=UpstreamOperatorRecordKind.PARCEL,
        record_id=row.parcel_record_id,
        source_key=row.source_key,
        source_record_id=row.source_record_id,
        apn=row.apn,
        county=row.county,
        observed_at=row.observed_created_at,
        payload=_payload(
            row.payload_json,
            UpstreamOperatorRecordKind.PARCEL,
            row.parcel_record_id,
        ),
    )


def _parcel_assurance_record(
    row: ParcelAssuranceReportRow,
) -> UpstreamOperatorRecord:
    return UpstreamOperatorRecord(
        record_kind=UpstreamOperatorRecordKind.PARCEL_ASSURANCE,
        record_id=row.report_id,
        status=row.review_status,
        apn=row.normalized_apn,
        county=row.county,
        observed_at=row.observed_created_at,
        payload=_payload(
            row.payload_json,
            UpstreamOperatorRecordKind.PARCEL_ASSURANCE,
            row.report_id,
        ),
    )


def _site_resolution_record(
    row: SiteResolutionResultRow,
) -> UpstreamOperatorRecord:
    return UpstreamOperatorRecord(
        record_kind=UpstreamOperatorRecordKind.SITE_RESOLUTION,
        record_id=row.resolution_id,
        status=row.status,
        site_key=row.primary_site_key,
        observed_at=row.observed_created_at,
        payload=_payload(
            row.payload_json,
            UpstreamOperatorRecordKind.SITE_RESOLUTION,
            row.resolution_id,
        ),
    )
