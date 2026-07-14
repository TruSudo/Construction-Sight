from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect

from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_bulk_manifest,
    build_arcgis_probe_plan,
    get_official_arcgis_capability_snapshots,
    parse_arcgis_probe_observation,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISProbeKind,
    digest_json_payload,
)
from constructionsight.parcel_source_verification import (
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelArcGISCapabilitySnapshotRow,
)
from constructionsight.storage.parcel_source_acquisition_store import (
    load_arcgis_acquisition_assessments,
    load_arcgis_bulk_manifests,
    load_arcgis_capability_snapshots,
    load_arcgis_probe_observations,
    load_arcgis_probe_plans,
    store_arcgis_acquisition_assessment,
    store_arcgis_bulk_manifest,
    store_arcgis_capability_snapshot,
    store_arcgis_probe_observation,
    store_arcgis_probe_plan,
)
from constructionsight.storage.parcel_source_verification_store import (
    store_parcel_source_evidence,
    store_parcel_source_verification_profile,
)
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    get_upstream_operator_record,
    list_upstream_operator_records,
)

_OBSERVED_AT = datetime(2026, 7, 14, 16, 30, tzinfo=UTC)


def _factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def _persist_profiles(session) -> None:
    for evidence in get_parcel_source_evidence():
        store_parcel_source_evidence(session, evidence)
    for profile in get_verified_parcel_source_profiles():
        store_parcel_source_verification_profile(session, profile)


def test_database_initializes_arcgis_acquisition_proof_tables() -> None:
    engine, _ = _factory()

    assert {
        "parcel_arcgis_capability_snapshots",
        "parcel_arcgis_probe_plans",
        "parcel_arcgis_probe_observations",
        "parcel_arcgis_bulk_manifests",
        "parcel_arcgis_acquisition_assessments",
    } <= set(inspect(engine).get_table_names())


def test_capability_storage_requires_persisted_verification_profile() -> None:
    _, factory = _factory()
    snapshot = get_official_arcgis_capability_snapshots()[0]

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="persisted verification profile"),
    ):
        store_arcgis_capability_snapshot(session, snapshot)


def test_metadata_only_chain_replays_and_loads_with_dependency_validation() -> None:
    _, factory = _factory()
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    replay_plan = build_arcgis_probe_plan(
        snapshot,
        generated_at=datetime(2026, 7, 14, 17, 0, tzinfo=UTC),
    )
    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        generated_at=_OBSERVED_AT,
    )

    with managed_session(factory) as session:
        _persist_profiles(session)
        snapshot_row = store_arcgis_capability_snapshot(session, snapshot)
        assert snapshot_row is store_arcgis_capability_snapshot(session, snapshot)
        plan_row = store_arcgis_probe_plan(session, plan)
        assert plan_row is store_arcgis_probe_plan(session, replay_plan)
        assessment_row = store_arcgis_acquisition_assessment(session, assessment)
        assert assessment_row is store_arcgis_acquisition_assessment(session, assessment)

    with managed_session(factory) as session:
        snapshots = load_arcgis_capability_snapshots(
            session,
            county=snapshot.county,
        )
        plans = load_arcgis_probe_plans(session, source_key=snapshot.source_key)
        assessments = load_arcgis_acquisition_assessments(
            session,
            status="metadata_only",
        )

    assert snapshots == [snapshot]
    assert plans == [plan]
    assert assessments == [assessment]


def test_observation_storage_requires_persisted_plan_and_unique_request() -> None:
    _, factory = _factory()
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    count_request = plan.requests[0]
    observation = parse_arcgis_probe_observation(
        count_request,
        {"count": 6},
        observed_at=_OBSERVED_AT,
    )

    with managed_session(factory) as session:
        _persist_profiles(session)
        store_arcgis_capability_snapshot(session, snapshot)
        with pytest.raises(ValueError, match="persisted request"):
            store_arcgis_probe_observation(session, observation)
        store_arcgis_probe_plan(session, plan)
        first = store_arcgis_probe_observation(session, observation)
        assert first is store_arcgis_probe_observation(session, observation)

    with managed_session(factory) as session:
        loaded = load_arcgis_probe_observations(
            session,
            county=snapshot.county,
        )

    assert loaded == [observation]
    assert loaded[0].kind == ParcelArcGISProbeKind.COUNT


def test_capability_loader_rejects_indexed_payload_drift() -> None:
    _, factory = _factory()
    snapshot = get_official_arcgis_capability_snapshots()[0]

    with managed_session(factory) as session:
        _persist_profiles(session)
        row = store_arcgis_capability_snapshot(session, snapshot)
        row.county = "Wrong County"

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="indexed fields disagree"),
    ):
        load_arcgis_capability_snapshots(session)


def test_capability_loader_rejects_payload_digest_drift() -> None:
    _, factory = _factory()
    snapshot = get_official_arcgis_capability_snapshots()[0]

    with managed_session(factory) as session:
        _persist_profiles(session)
        row = store_arcgis_capability_snapshot(session, snapshot)
        assert isinstance(row, ParcelArcGISCapabilitySnapshotRow)
        row.payload_json = row.payload_json.replace(
            '"max_record_count": 2000',
            '"max_record_count": 1999',
        )

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="invalid ArcGIS capability payload"),
    ):
        load_arcgis_capability_snapshots(session)


def test_complete_chain_persists_manifest_and_verified_assessment() -> None:
    _, factory = _factory()
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    responses = (
        {"count": 6},
        {
            "features": [
                {"attributes": {"OBJECTID": 1}},
                {"attributes": {"OBJECTID": 3}},
            ],
            "exceededTransferLimit": True,
        },
        {
            "features": [
                {"attributes": {"OBJECTID": 5}},
                {"attributes": {"OBJECTID": 7}},
            ],
            "exceededTransferLimit": True,
        },
        {
            "features": [
                {"attributes": {"OBJECTID": 1}},
                {"attributes": {"OBJECTID": 3}},
            ],
            "exceededTransferLimit": True,
        },
    )
    observations = [
        parse_arcgis_probe_observation(
            request,
            response,
            observed_at=_OBSERVED_AT,
        )
        for request, response in zip(plan.requests, responses, strict=True)
    ]
    manifest = build_arcgis_bulk_manifest(
        snapshot,
        started_at=_OBSERVED_AT,
        completed_at=_OBSERVED_AT + timedelta(minutes=3),
        starting_count=6,
        ending_count=6,
        page_size=2,
        page_count=3,
        retrieved_count=6,
        unique_object_id_count=6,
        duplicate_object_id_count=0,
        failed_page_count=0,
        terminal_page_observed=True,
        checkpoint_resume_verified=True,
        retry_recovery_verified=True,
        page_response_digests=tuple(
            digest_json_payload({"page": page}) for page in range(3)
        ),
        object_id_set_digest=digest_json_payload([1, 3, 5, 7, 9, 11]),
    )
    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        bulk_manifest=manifest,
        generated_at=_OBSERVED_AT,
    )

    with managed_session(factory) as session:
        _persist_profiles(session)
        store_arcgis_capability_snapshot(session, snapshot)
        store_arcgis_probe_plan(session, plan)
        with pytest.raises(ValueError, match="matching persisted count probe"):
            store_arcgis_bulk_manifest(session, manifest)
        for observation in observations:
            store_arcgis_probe_observation(session, observation)
        row = store_arcgis_bulk_manifest(session, manifest)
        assert row is store_arcgis_bulk_manifest(session, manifest)
        store_arcgis_acquisition_assessment(session, assessment)

    with managed_session(factory) as session:
        manifests = load_arcgis_bulk_manifests(
            session,
            source_key=snapshot.source_key,
        )
        assessments = load_arcgis_acquisition_assessments(
            session,
            status="bulk_rehearsal_verified",
        )
        manifest_record = get_upstream_operator_record(
            session,
            UpstreamOperatorRecordKind.PARCEL_ARCGIS_BULK_MANIFEST,
            manifest.manifest_id,
        )

    assert manifests == [manifest]
    assert assessments == [assessment]
    assert assessment.bulk_acquisition_verified is True
    assert manifest_record is not None
    assert manifest_record.status == "reconciled"


def test_operator_exposes_capability_plan_and_assessment_read_only() -> None:
    _, factory = _factory()
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        generated_at=_OBSERVED_AT,
    )

    with managed_session(factory) as session:
        _persist_profiles(session)
        store_arcgis_capability_snapshot(session, snapshot)
        store_arcgis_probe_plan(session, plan)
        store_arcgis_acquisition_assessment(session, assessment)

    with managed_session(factory) as session:
        capability_records = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL_ARCGIS_CAPABILITY,
            county=snapshot.county,
        )
        plan_record = get_upstream_operator_record(
            session,
            UpstreamOperatorRecordKind.PARCEL_ARCGIS_PROBE_PLAN,
            plan.plan_id,
        )
        assessment_records = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL_ARCGIS_ACQUISITION,
            status="metadata_only",
            source_key=snapshot.source_key,
        )

    assert len(capability_records) == 1
    assert capability_records[0].status == "advertised_ready"
    assert plan_record is not None
    assert plan_record.payload["bulk_run_authorized"] is False
    assert len(assessment_records) == 1
    assert assessment_records[0].payload["bulk_acquisition_verified"] is False
