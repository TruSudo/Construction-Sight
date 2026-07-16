"""Transactional storage for portable bounded ArcGIS proof bundles."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.parcel_source_acquisition_bundle import (
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_bundle_models import (
    ParcelArcGISBoundedProofBundle,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelArcGISBoundedProofBundleRow,
)
from constructionsight.storage.parcel_source_acquisition_store import (
    load_arcgis_acquisition_assessments,
    load_arcgis_capability_snapshots,
    load_arcgis_probe_observations,
    load_arcgis_probe_plans,
    store_arcgis_proof_chain,
)
from constructionsight.storage.parcel_source_verification_store import (
    load_parcel_source_evidence,
    load_parcel_source_verification_profiles,
    store_parcel_source_evidence,
    store_parcel_source_verification_profile,
)


def store_arcgis_bounded_proof_bundle(
    session: Session,
    bundle: ParcelArcGISBoundedProofBundle,
) -> ParcelArcGISBoundedProofBundleRow:
    """Append an offline-verified bundle after validating persisted dependencies."""

    session.flush()
    verify_arcgis_bounded_proof_bundle(bundle)
    _require_persisted_chain(session, bundle)
    payload_json = _payload_json(bundle.to_dict())
    existing = session.execute(
        select(ParcelArcGISBoundedProofBundleRow).where(
            ParcelArcGISBoundedProofBundleRow.bundle_id == bundle.bundle_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if _semantic_payload(existing.payload_json) != _semantic_payload(payload_json):
            raise ValueError(f"ArcGIS bounded-proof identity collision: {bundle.bundle_id}")
        return existing
    row = ParcelArcGISBoundedProofBundleRow(
        bundle_id=bundle.bundle_id,
        profile_id=bundle.profile.profile_id,
        snapshot_id=bundle.snapshot.snapshot_id,
        plan_id=bundle.plan.plan_id,
        assessment_id=bundle.assessment.assessment_id,
        source_key=bundle.source_key,
        county=bundle.county,
        status=bundle.assessment.status.value,
        evidence_count=len(bundle.source_evidence),
        observation_count=len(bundle.observations),
        observed_created_at=bundle.created_at.isoformat(),
        payload_json=payload_json,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(f"ArcGIS bounded-proof bundle already exists: {bundle.bundle_id}") from exc
    return row


def store_arcgis_bounded_proof_bundle_chain(
    session: Session,
    bundle: ParcelArcGISBoundedProofBundle,
) -> ParcelArcGISBoundedProofBundleRow:
    """Persist every nested dependency and the bundle in one caller transaction."""

    verify_arcgis_bounded_proof_bundle(bundle)
    for evidence in bundle.source_evidence:
        store_parcel_source_evidence(session, evidence)
    store_parcel_source_verification_profile(session, bundle.profile)
    store_arcgis_proof_chain(
        session,
        snapshots=(bundle.snapshot,),
        plans=(bundle.plan,),
        observations=bundle.observations,
        assessments=(bundle.assessment,),
    )
    return store_arcgis_bounded_proof_bundle(session, bundle)


def load_arcgis_bounded_proof_bundles(
    session: Session,
    *,
    status: str | None = None,
    source_key: str | None = None,
    county: str | None = None,
) -> list[ParcelArcGISBoundedProofBundle]:
    """Load verified bundles and reject index, payload, or dependency drift."""

    statement = select(ParcelArcGISBoundedProofBundleRow)
    if status is not None:
        statement = statement.where(ParcelArcGISBoundedProofBundleRow.status == status)
    if source_key is not None:
        statement = statement.where(ParcelArcGISBoundedProofBundleRow.source_key == source_key)
    if county is not None:
        statement = statement.where(ParcelArcGISBoundedProofBundleRow.county == county)
    rows = session.execute(statement.order_by(ParcelArcGISBoundedProofBundleRow.id)).scalars()
    bundles = [_bundle_from_row(row) for row in rows]
    for bundle in bundles:
        _require_persisted_chain(session, bundle)
    return bundles


def _bundle_from_row(
    row: ParcelArcGISBoundedProofBundleRow,
) -> ParcelArcGISBoundedProofBundle:
    payload = _decode_object(row.payload_json, row.bundle_id)
    try:
        bundle = ParcelArcGISBoundedProofBundle.model_validate(payload)
    except ValueError as exc:
        raise ValueError(f"invalid ArcGIS bounded-proof payload: {row.bundle_id}") from exc
    indexed = (
        row.bundle_id,
        row.profile_id,
        row.snapshot_id,
        row.plan_id,
        row.assessment_id,
        row.source_key,
        row.county,
        row.status,
        row.evidence_count,
        row.observation_count,
        row.observed_created_at,
    )
    nested = (
        bundle.bundle_id,
        bundle.profile.profile_id,
        bundle.snapshot.snapshot_id,
        bundle.plan.plan_id,
        bundle.assessment.assessment_id,
        bundle.source_key,
        bundle.county,
        bundle.assessment.status.value,
        len(bundle.source_evidence),
        len(bundle.observations),
        bundle.created_at.isoformat(),
    )
    if indexed != nested:
        raise ValueError(
            f"ArcGIS bounded-proof indexed fields disagree with payload: {row.bundle_id}"
        )
    verify_arcgis_bounded_proof_bundle(bundle)
    return bundle


def _require_persisted_chain(
    session: Session,
    bundle: ParcelArcGISBoundedProofBundle,
) -> None:
    for evidence in bundle.source_evidence:
        if load_parcel_source_evidence(session, evidence.evidence_id) != evidence:
            raise ValueError("ArcGIS bounded proof requires its exact persisted evidence")
    profiles = load_parcel_source_verification_profiles(
        session,
        source_key=bundle.source_key,
        county=bundle.county,
    )
    if bundle.profile not in profiles:
        raise ValueError("ArcGIS bounded proof requires its exact persisted profile")
    snapshots = load_arcgis_capability_snapshots(
        session,
        source_key=bundle.source_key,
        county=bundle.county,
    )
    if bundle.snapshot not in snapshots:
        raise ValueError("ArcGIS bounded proof requires its exact persisted snapshot")
    plans = load_arcgis_probe_plans(
        session,
        source_key=bundle.source_key,
        county=bundle.county,
    )
    if bundle.plan not in plans:
        raise ValueError("ArcGIS bounded proof requires its exact persisted plan")
    observations = load_arcgis_probe_observations(
        session,
        source_key=bundle.source_key,
        county=bundle.county,
    )
    if not set(bundle.observations).issubset(set(observations)):
        raise ValueError("ArcGIS bounded proof requires its exact persisted observations")
    assessments = load_arcgis_acquisition_assessments(
        session,
        source_key=bundle.source_key,
        county=bundle.county,
    )
    if bundle.assessment not in assessments:
        raise ValueError("ArcGIS bounded proof requires its exact persisted assessment")


def _decode_object(payload_json: str, bundle_id: str) -> dict[str, Any]:
    try:
        payload: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed ArcGIS bounded-proof payload JSON: {bundle_id}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"ArcGIS bounded-proof payload must be a JSON object: {bundle_id}")
    return {str(key): value for key, value in payload.items()}


def _semantic_payload(payload_json: str) -> str:
    payload = _decode_object(payload_json, "semantic replay")
    payload.pop("created_at", None)
    return _payload_json(payload)


def _payload_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True)
