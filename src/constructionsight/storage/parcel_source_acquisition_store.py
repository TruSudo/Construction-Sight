"""Immutable storage for ArcGIS capability, probe, and acquisition proof."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionAssessment,
    ParcelArcGISBulkManifest,
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbeKind,
    ParcelArcGISProbeObservation,
    ParcelArcGISProbePlan,
)
from constructionsight.parcel_source_verification_models import (
    ParcelSourceVerificationProfile,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelArcGISAcquisitionAssessmentRow,
    ParcelArcGISBulkManifestRow,
    ParcelArcGISCapabilitySnapshotRow,
    ParcelArcGISProbeObservationRow,
    ParcelArcGISProbePlanRow,
    ParcelSourceVerificationProfileRow,
)

ModelT = TypeVar(
    "ModelT",
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbePlan,
    ParcelArcGISProbeObservation,
    ParcelArcGISBulkManifest,
    ParcelArcGISAcquisitionAssessment,
    ParcelSourceVerificationProfile,
)
RowT = TypeVar(
    "RowT",
    ParcelArcGISCapabilitySnapshotRow,
    ParcelArcGISProbePlanRow,
    ParcelArcGISProbeObservationRow,
    ParcelArcGISBulkManifestRow,
    ParcelArcGISAcquisitionAssessmentRow,
)


def store_arcgis_capability_snapshot(
    session: Session,
    snapshot: ParcelArcGISCapabilitySnapshot,
) -> ParcelArcGISCapabilitySnapshotRow:
    """Append a capability snapshot after validating its verification profile."""

    session.flush()
    _require_profile(session, snapshot)
    payload_json = _payload_json(snapshot.to_dict())
    existing = session.execute(
        select(ParcelArcGISCapabilitySnapshotRow).where(
            ParcelArcGISCapabilitySnapshotRow.snapshot_id == snapshot.snapshot_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        _require_exact_replay(
            existing.payload_json,
            payload_json,
            "capability",
            snapshot.snapshot_id,
        )
        return existing
    row = ParcelArcGISCapabilitySnapshotRow(
        snapshot_id=snapshot.snapshot_id,
        profile_id=snapshot.profile_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        observed_at=snapshot.observed_at.isoformat(),
        schema_fingerprint=snapshot.schema_fingerprint,
        advertised_ready=snapshot.advertised_ready_for_probe,
        field_count=len(snapshot.fields),
        max_record_count=snapshot.max_record_count,
        payload_json=payload_json,
    )
    return _insert(session, row, "ArcGIS capability", snapshot.snapshot_id)


def store_arcgis_probe_plan(
    session: Session,
    plan: ParcelArcGISProbePlan,
) -> ParcelArcGISProbePlanRow:
    """Append a bounded plan after validating its capability dependency."""

    session.flush()
    snapshot = _require_snapshot(session, plan.snapshot_id)
    _require_scope(snapshot, plan, "ArcGIS probe plan")
    payload_json = _payload_json(plan.to_dict())
    existing = session.execute(
        select(ParcelArcGISProbePlanRow).where(ParcelArcGISProbePlanRow.plan_id == plan.plan_id)
    ).scalar_one_or_none()
    if existing is not None:
        _require_semantic_replay(
            existing.payload_json,
            payload_json,
            "generated_at",
            "ArcGIS probe plan",
            plan.plan_id,
        )
        return existing
    row = ParcelArcGISProbePlanRow(
        plan_id=plan.plan_id,
        snapshot_id=plan.snapshot_id,
        profile_id=plan.profile_id,
        source_key=plan.source_key,
        county=plan.county,
        request_count=len(plan.requests),
        observed_generated_at=plan.generated_at.isoformat(),
        payload_json=payload_json,
    )
    return _insert(session, row, "ArcGIS probe plan", plan.plan_id)


def store_arcgis_probe_observation(
    session: Session,
    observation: ParcelArcGISProbeObservation,
) -> ParcelArcGISProbeObservationRow:
    """Append one response only when its exact request exists in a persisted plan."""

    session.flush()
    plan = _require_plan_for_request(session, observation.request_id)
    snapshot = _require_snapshot(session, observation.snapshot_id)
    _require_scope(snapshot, observation, "ArcGIS probe observation")
    request = next(
        request for request in plan.requests if request.request_id == observation.request_id
    )
    if request.kind != observation.kind:
        raise ValueError("ArcGIS probe observation kind does not match request")
    payload_json = _payload_json(observation.to_dict())
    existing = session.execute(
        select(ParcelArcGISProbeObservationRow).where(
            ParcelArcGISProbeObservationRow.observation_id == observation.observation_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        _require_exact_replay(
            existing.payload_json,
            payload_json,
            "ArcGIS probe observation",
            observation.observation_id,
        )
        return existing
    request_existing = session.execute(
        select(ParcelArcGISProbeObservationRow).where(
            ParcelArcGISProbeObservationRow.request_id == observation.request_id
        )
    ).scalar_one_or_none()
    if request_existing is not None:
        raise ValueError(
            f"ArcGIS probe request already has an observation: {observation.request_id}"
        )
    observed_count = (
        observation.total_count
        if observation.kind == ParcelArcGISProbeKind.COUNT
        else len(observation.object_ids)
    )
    assert observed_count is not None
    row = ParcelArcGISProbeObservationRow(
        observation_id=observation.observation_id,
        request_id=observation.request_id,
        snapshot_id=observation.snapshot_id,
        profile_id=observation.profile_id,
        source_key=observation.source_key,
        county=observation.county,
        probe_kind=observation.kind.value,
        observed_at=observation.observed_at.isoformat(),
        observed_record_count=observed_count,
        payload_json=payload_json,
    )
    return _insert(
        session,
        row,
        "ArcGIS probe observation",
        observation.observation_id,
    )


def store_arcgis_bulk_manifest(
    session: Session,
    manifest: ParcelArcGISBulkManifest,
) -> ParcelArcGISBulkManifestRow:
    """Append a complete-run manifest after count-observation reconciliation."""

    session.flush()
    snapshot = _require_snapshot(session, manifest.snapshot_id)
    _require_scope(snapshot, manifest, "ArcGIS bulk manifest")
    count_rows = list(
        session.execute(
            select(ParcelArcGISProbeObservationRow).where(
                ParcelArcGISProbeObservationRow.snapshot_id == manifest.snapshot_id,
                ParcelArcGISProbeObservationRow.probe_kind
                == ParcelArcGISProbeKind.COUNT.value,
            )
        ).scalars()
    )
    counts = {
        observation.total_count
        for observation in (_observation_from_row(row) for row in count_rows)
    }
    if manifest.starting_count not in counts:
        raise ValueError("ArcGIS bulk manifest requires a matching persisted count probe")
    payload_json = _payload_json(manifest.to_dict())
    existing = session.execute(
        select(ParcelArcGISBulkManifestRow).where(
            ParcelArcGISBulkManifestRow.manifest_id == manifest.manifest_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        _require_exact_replay(
            existing.payload_json,
            payload_json,
            "ArcGIS bulk manifest",
            manifest.manifest_id,
        )
        return existing
    row = ParcelArcGISBulkManifestRow(
        manifest_id=manifest.manifest_id,
        snapshot_id=manifest.snapshot_id,
        profile_id=manifest.profile_id,
        source_key=manifest.source_key,
        county=manifest.county,
        expected_record_count=manifest.starting_count,
        retrieved_record_count=manifest.retrieved_count,
        page_count=manifest.page_count,
        observed_completed_at=manifest.completed_at.isoformat(),
        payload_json=payload_json,
    )
    return _insert(session, row, "ArcGIS bulk manifest", manifest.manifest_id)


def store_arcgis_acquisition_assessment(
    session: Session,
    assessment: ParcelArcGISAcquisitionAssessment,
) -> ParcelArcGISAcquisitionAssessmentRow:
    """Append an assessment after validating every referenced proof dependency."""

    session.flush()
    snapshot = _require_snapshot(session, assessment.snapshot_id)
    _require_scope(snapshot, assessment, "ArcGIS acquisition assessment")
    plan = _require_plan(session, assessment.plan_id)
    if plan.snapshot_id != assessment.snapshot_id:
        raise ValueError("ArcGIS assessment plan does not match capability snapshot")
    persisted_observation_ids = {
        row.observation_id
        for row in session.execute(
            select(ParcelArcGISProbeObservationRow).where(
                ParcelArcGISProbeObservationRow.observation_id.in_(
                    assessment.probe_observation_ids
                )
            )
        ).scalars()
    }
    if persisted_observation_ids != set(assessment.probe_observation_ids):
        raise ValueError("ArcGIS assessment requires every persisted probe observation")
    if assessment.bulk_manifest_id is not None:
        manifest_row = session.execute(
            select(ParcelArcGISBulkManifestRow).where(
                ParcelArcGISBulkManifestRow.manifest_id == assessment.bulk_manifest_id
            )
        ).scalar_one_or_none()
        if manifest_row is None:
            raise ValueError("ArcGIS assessment requires its persisted bulk manifest")
        manifest = _manifest_from_row(manifest_row)
        if manifest.snapshot_id != assessment.snapshot_id:
            raise ValueError("ArcGIS assessment manifest scope mismatch")
    payload_json = _payload_json(assessment.to_dict())
    existing = session.execute(
        select(ParcelArcGISAcquisitionAssessmentRow).where(
            ParcelArcGISAcquisitionAssessmentRow.assessment_id
            == assessment.assessment_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        _require_semantic_replay(
            existing.payload_json,
            payload_json,
            "generated_at",
            "ArcGIS acquisition assessment",
            assessment.assessment_id,
        )
        return existing
    row = ParcelArcGISAcquisitionAssessmentRow(
        assessment_id=assessment.assessment_id,
        snapshot_id=assessment.snapshot_id,
        plan_id=assessment.plan_id,
        profile_id=assessment.profile_id,
        source_key=assessment.source_key,
        county=assessment.county,
        status=assessment.status.value,
        bulk_acquisition_verified=assessment.bulk_acquisition_verified,
        observation_count=len(assessment.probe_observation_ids),
        gap_count=len(assessment.gaps),
        observed_generated_at=assessment.generated_at.isoformat(),
        payload_json=payload_json,
    )
    return _insert(
        session,
        row,
        "ArcGIS acquisition assessment",
        assessment.assessment_id,
    )


def load_arcgis_capability_snapshots(
    session: Session,
    *,
    source_key: str | None = None,
    county: str | None = None,
) -> list[ParcelArcGISCapabilitySnapshot]:
    statement = select(ParcelArcGISCapabilitySnapshotRow)
    if source_key is not None:
        statement = statement.where(ParcelArcGISCapabilitySnapshotRow.source_key == source_key)
    if county is not None:
        statement = statement.where(ParcelArcGISCapabilitySnapshotRow.county == county)
    rows = session.execute(
        statement.order_by(ParcelArcGISCapabilitySnapshotRow.id)
    ).scalars()
    return [_snapshot_from_row(row) for row in rows]


def load_arcgis_probe_plans(
    session: Session,
    *,
    source_key: str | None = None,
    county: str | None = None,
) -> list[ParcelArcGISProbePlan]:
    statement = select(ParcelArcGISProbePlanRow)
    if source_key is not None:
        statement = statement.where(ParcelArcGISProbePlanRow.source_key == source_key)
    if county is not None:
        statement = statement.where(ParcelArcGISProbePlanRow.county == county)
    rows = session.execute(statement.order_by(ParcelArcGISProbePlanRow.id)).scalars()
    return [_plan_from_row(row) for row in rows]


def load_arcgis_probe_observations(
    session: Session,
    *,
    source_key: str | None = None,
    county: str | None = None,
) -> list[ParcelArcGISProbeObservation]:
    statement = select(ParcelArcGISProbeObservationRow)
    if source_key is not None:
        statement = statement.where(ParcelArcGISProbeObservationRow.source_key == source_key)
    if county is not None:
        statement = statement.where(ParcelArcGISProbeObservationRow.county == county)
    rows = session.execute(
        statement.order_by(ParcelArcGISProbeObservationRow.id)
    ).scalars()
    return [_observation_from_row(row) for row in rows]


def load_arcgis_bulk_manifests(
    session: Session,
    *,
    source_key: str | None = None,
    county: str | None = None,
) -> list[ParcelArcGISBulkManifest]:
    statement = select(ParcelArcGISBulkManifestRow)
    if source_key is not None:
        statement = statement.where(ParcelArcGISBulkManifestRow.source_key == source_key)
    if county is not None:
        statement = statement.where(ParcelArcGISBulkManifestRow.county == county)
    rows = session.execute(statement.order_by(ParcelArcGISBulkManifestRow.id)).scalars()
    return [_manifest_from_row(row) for row in rows]


def load_arcgis_acquisition_assessments(
    session: Session,
    *,
    status: str | None = None,
    source_key: str | None = None,
    county: str | None = None,
) -> list[ParcelArcGISAcquisitionAssessment]:
    statement = select(ParcelArcGISAcquisitionAssessmentRow)
    if status is not None:
        statement = statement.where(ParcelArcGISAcquisitionAssessmentRow.status == status)
    if source_key is not None:
        statement = statement.where(
            ParcelArcGISAcquisitionAssessmentRow.source_key == source_key
        )
    if county is not None:
        statement = statement.where(ParcelArcGISAcquisitionAssessmentRow.county == county)
    rows = session.execute(
        statement.order_by(ParcelArcGISAcquisitionAssessmentRow.id)
    ).scalars()
    return [_assessment_from_row(row) for row in rows]


def _require_profile(
    session: Session,
    snapshot: ParcelArcGISCapabilitySnapshot,
) -> None:
    row = session.execute(
        select(ParcelSourceVerificationProfileRow).where(
            ParcelSourceVerificationProfileRow.profile_id == snapshot.profile_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("ArcGIS capability requires a persisted verification profile")
    profile = _validated_model(
        row.payload_json,
        ParcelSourceVerificationProfile,
        "parcel source verification",
        row.profile_id,
    )
    if profile.source_key != snapshot.source_key or profile.county != snapshot.county:
        raise ValueError("ArcGIS capability verification profile scope mismatch")


def _require_snapshot(
    session: Session,
    snapshot_id: str,
) -> ParcelArcGISCapabilitySnapshot:
    row = session.execute(
        select(ParcelArcGISCapabilitySnapshotRow).where(
            ParcelArcGISCapabilitySnapshotRow.snapshot_id == snapshot_id
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(f"ArcGIS capability snapshot is not persisted: {snapshot_id}")
    return _snapshot_from_row(row)


def _require_plan(session: Session, plan_id: str) -> ParcelArcGISProbePlan:
    row = session.execute(
        select(ParcelArcGISProbePlanRow).where(ParcelArcGISProbePlanRow.plan_id == plan_id)
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(f"ArcGIS probe plan is not persisted: {plan_id}")
    return _plan_from_row(row)


def _require_plan_for_request(session: Session, request_id: str) -> ParcelArcGISProbePlan:
    rows = list(session.execute(select(ParcelArcGISProbePlanRow)).scalars())
    plans = [_plan_from_row(row) for row in rows]
    matches = [
        plan
        for plan in plans
        if request_id in {request.request_id for request in plan.requests}
    ]
    if len(matches) != 1:
        raise ValueError("ArcGIS probe observation requires exactly one persisted request")
    return matches[0]


def _require_scope(
    snapshot: ParcelArcGISCapabilitySnapshot,
    record: ParcelArcGISProbePlan
    | ParcelArcGISProbeObservation
    | ParcelArcGISBulkManifest
    | ParcelArcGISAcquisitionAssessment,
    label: str,
) -> None:
    if (
        record.snapshot_id != snapshot.snapshot_id
        or record.profile_id != snapshot.profile_id
        or record.source_key != snapshot.source_key
        or record.county != snapshot.county
    ):
        raise ValueError(f"{label} scope mismatch")


def _snapshot_from_row(
    row: ParcelArcGISCapabilitySnapshotRow,
) -> ParcelArcGISCapabilitySnapshot:
    model = _validated_model(
        row.payload_json,
        ParcelArcGISCapabilitySnapshot,
        "ArcGIS capability",
        row.snapshot_id,
    )
    _require_index_match(
        (
            row.snapshot_id,
            row.profile_id,
            row.source_key,
            row.county,
            row.observed_at,
            row.schema_fingerprint,
            row.advertised_ready,
            row.field_count,
            row.max_record_count,
        ),
        (
            model.snapshot_id,
            model.profile_id,
            model.source_key,
            model.county,
            model.observed_at.isoformat(),
            model.schema_fingerprint,
            model.advertised_ready_for_probe,
            len(model.fields),
            model.max_record_count,
        ),
        "ArcGIS capability",
        row.snapshot_id,
    )
    return model


def _plan_from_row(row: ParcelArcGISProbePlanRow) -> ParcelArcGISProbePlan:
    model = _validated_model(
        row.payload_json,
        ParcelArcGISProbePlan,
        "ArcGIS probe plan",
        row.plan_id,
    )
    _require_index_match(
        (
            row.plan_id,
            row.snapshot_id,
            row.profile_id,
            row.source_key,
            row.county,
            row.request_count,
            row.observed_generated_at,
        ),
        (
            model.plan_id,
            model.snapshot_id,
            model.profile_id,
            model.source_key,
            model.county,
            len(model.requests),
            model.generated_at.isoformat(),
        ),
        "ArcGIS probe plan",
        row.plan_id,
    )
    return model


def _observation_from_row(
    row: ParcelArcGISProbeObservationRow,
) -> ParcelArcGISProbeObservation:
    model = _validated_model(
        row.payload_json,
        ParcelArcGISProbeObservation,
        "ArcGIS probe observation",
        row.observation_id,
    )
    observed_count = (
        model.total_count
        if model.kind == ParcelArcGISProbeKind.COUNT
        else len(model.object_ids)
    )
    _require_index_match(
        (
            row.observation_id,
            row.request_id,
            row.snapshot_id,
            row.profile_id,
            row.source_key,
            row.county,
            row.probe_kind,
            row.observed_at,
            row.observed_record_count,
        ),
        (
            model.observation_id,
            model.request_id,
            model.snapshot_id,
            model.profile_id,
            model.source_key,
            model.county,
            model.kind.value,
            model.observed_at.isoformat(),
            observed_count,
        ),
        "ArcGIS probe observation",
        row.observation_id,
    )
    return model


def _manifest_from_row(row: ParcelArcGISBulkManifestRow) -> ParcelArcGISBulkManifest:
    model = _validated_model(
        row.payload_json,
        ParcelArcGISBulkManifest,
        "ArcGIS bulk manifest",
        row.manifest_id,
    )
    _require_index_match(
        (
            row.manifest_id,
            row.snapshot_id,
            row.profile_id,
            row.source_key,
            row.county,
            row.expected_record_count,
            row.retrieved_record_count,
            row.page_count,
            row.observed_completed_at,
        ),
        (
            model.manifest_id,
            model.snapshot_id,
            model.profile_id,
            model.source_key,
            model.county,
            model.starting_count,
            model.retrieved_count,
            model.page_count,
            model.completed_at.isoformat(),
        ),
        "ArcGIS bulk manifest",
        row.manifest_id,
    )
    return model


def _assessment_from_row(
    row: ParcelArcGISAcquisitionAssessmentRow,
) -> ParcelArcGISAcquisitionAssessment:
    model = _validated_model(
        row.payload_json,
        ParcelArcGISAcquisitionAssessment,
        "ArcGIS acquisition assessment",
        row.assessment_id,
    )
    _require_index_match(
        (
            row.assessment_id,
            row.snapshot_id,
            row.plan_id,
            row.profile_id,
            row.source_key,
            row.county,
            row.status,
            row.bulk_acquisition_verified,
            row.observation_count,
            row.gap_count,
            row.observed_generated_at,
        ),
        (
            model.assessment_id,
            model.snapshot_id,
            model.plan_id,
            model.profile_id,
            model.source_key,
            model.county,
            model.status.value,
            model.bulk_acquisition_verified,
            len(model.probe_observation_ids),
            len(model.gaps),
            model.generated_at.isoformat(),
        ),
        "ArcGIS acquisition assessment",
        row.assessment_id,
    )
    return model


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


def _insert(session: Session, row: RowT, label: str, record_id: str) -> RowT:
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(f"{label} already exists: {record_id}") from exc
    return row


def _require_exact_replay(
    existing_payload: str,
    replay_payload: str,
    label: str,
    record_id: str,
) -> None:
    if existing_payload != replay_payload:
        raise ValueError(f"{label} identity collision: {record_id}")


def _require_semantic_replay(
    existing_payload: str,
    replay_payload: str,
    excluded_key: str,
    label: str,
    record_id: str,
) -> None:
    if _semantic_payload(existing_payload, excluded_key) != _semantic_payload(
        replay_payload, excluded_key
    ):
        raise ValueError(f"{label} identity collision: {record_id}")


def _semantic_payload(payload_json: str, excluded_key: str) -> str:
    payload = _decode_object(payload_json, "semantic replay", excluded_key)
    payload.pop(excluded_key, None)
    return _payload_json(payload)


def _require_index_match(
    indexed: tuple[object, ...],
    payload: tuple[object, ...],
    label: str,
    record_id: str,
) -> None:
    if indexed != payload:
        raise ValueError(f"{label} indexed fields disagree with payload: {record_id}")


def _decode_object(payload_json: str, label: str, record_id: str) -> dict[str, Any]:
    try:
        payload: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed {label} payload JSON: {record_id}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} payload must be a JSON object: {record_id}")
    return {str(key): value for key, value in payload.items()}


def _payload_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True)


def store_arcgis_proof_chain(
    session: Session,
    *,
    snapshots: Iterable[ParcelArcGISCapabilitySnapshot] = (),
    plans: Iterable[ParcelArcGISProbePlan] = (),
    observations: Iterable[ParcelArcGISProbeObservation] = (),
    manifests: Iterable[ParcelArcGISBulkManifest] = (),
    assessments: Iterable[ParcelArcGISAcquisitionAssessment] = (),
) -> None:
    """Persist a caller-supplied proof chain in dependency order."""

    for snapshot in snapshots:
        store_arcgis_capability_snapshot(session, snapshot)
    for plan in plans:
        store_arcgis_probe_plan(session, plan)
    for observation in observations:
        store_arcgis_probe_observation(session, observation)
    for manifest in manifests:
        store_arcgis_bulk_manifest(session, manifest)
    for assessment in assessments:
        store_arcgis_acquisition_assessment(session, assessment)
