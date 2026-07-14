from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect

from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_probe_plan,
    get_official_arcgis_capability_snapshots,
    parse_arcgis_probe_observation,
)
from constructionsight.parcel_source_acquisition_bundle import (
    build_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_models import ParcelArcGISProbeKind
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
from constructionsight.storage.parcel_source_acquisition_bundle_store import (
    load_arcgis_bounded_proof_bundles,
    store_arcgis_bounded_proof_bundle,
    store_arcgis_bounded_proof_bundle_chain,
)
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    get_upstream_operator_record,
    list_upstream_operator_records,
)

_OBSERVED_AT = datetime(2026, 7, 14, 18, 30, tzinfo=UTC)


def _factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def _bounded_bundle(*, created_at: datetime = _OBSERVED_AT):
    snapshot = get_official_arcgis_capability_snapshots()[0]
    profile = next(
        item
        for item in get_verified_parcel_source_profiles()
        if item.profile_id == snapshot.profile_id
    )
    evidence_by_id = {
        item.evidence_id: item for item in get_parcel_source_evidence()
    }
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    response_by_kind = {
        ParcelArcGISProbeKind.COUNT: {"count": 6},
        ParcelArcGISProbeKind.INITIAL_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 1}},
                {"attributes": {"OBJECTID": 3}},
            ],
            "exceededTransferLimit": True,
        },
        ParcelArcGISProbeKind.NEXT_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 5}},
                {"attributes": {"OBJECTID": 7}},
            ],
            "exceededTransferLimit": True,
        },
        ParcelArcGISProbeKind.REPLAY_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 1}},
                {"attributes": {"OBJECTID": 3}},
            ],
            "exceededTransferLimit": True,
        },
    }
    observations = tuple(
        parse_arcgis_probe_observation(
            request,
            response_by_kind[request.kind],
            observed_at=_OBSERVED_AT,
        )
        for request in plan.requests
    )
    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        generated_at=_OBSERVED_AT,
    )
    return build_arcgis_bounded_proof_bundle(
        profile,
        (evidence_by_id[evidence_id] for evidence_id in profile.evidence_ids),
        snapshot,
        plan,
        observations,
        assessment,
        created_at=created_at,
    )


def test_database_initializes_bounded_proof_bundle_table() -> None:
    engine, _ = _factory()

    assert "parcel_arcgis_bounded_proof_bundles" in inspect(engine).get_table_names()


def test_bundle_storage_requires_every_persisted_dependency() -> None:
    _, factory = _factory()
    bundle = _bounded_bundle()

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="exact persisted evidence"),
    ):
        store_arcgis_bounded_proof_bundle(session, bundle)


def test_bundle_chain_persists_replays_loads_and_serves_operator_records() -> None:
    _, factory = _factory()
    bundle = _bounded_bundle()
    semantic_replay = _bounded_bundle(
        created_at=_OBSERVED_AT + timedelta(minutes=10)
    )
    assert semantic_replay.bundle_id == bundle.bundle_id

    with managed_session(factory) as session:
        row = store_arcgis_bounded_proof_bundle_chain(session, bundle)
        assert row is store_arcgis_bounded_proof_bundle_chain(session, semantic_replay)

    with managed_session(factory) as session:
        loaded = load_arcgis_bounded_proof_bundles(
            session,
            status="bounded_query_verified",
            source_key=bundle.source_key,
            county=bundle.county,
        )
        listed = list_upstream_operator_records(
            session,
            UpstreamOperatorRecordKind.PARCEL_ARCGIS_PROOF_BUNDLE,
            status="bounded_query_verified",
            source_key=bundle.source_key,
            county=bundle.county,
        )
        detail = get_upstream_operator_record(
            session,
            UpstreamOperatorRecordKind.PARCEL_ARCGIS_PROOF_BUNDLE,
            bundle.bundle_id,
        )

    assert loaded == [bundle]
    assert len(listed) == 1
    assert listed[0].record_id == bundle.bundle_id
    assert listed[0].payload["bulk_run_authorized"] is False
    assert detail is not None
    assert detail.payload["assessment"]["status"] == "bounded_query_verified"


def test_bundle_loader_rejects_index_and_payload_drift() -> None:
    _, factory = _factory()
    bundle = _bounded_bundle()

    with managed_session(factory) as session:
        row = store_arcgis_bounded_proof_bundle_chain(session, bundle)
        row.county = "Wrong County"

    with (
        managed_session(factory) as session,
        pytest.raises(ValueError, match="indexed fields disagree"),
    ):
        load_arcgis_bounded_proof_bundles(session)

    _, second_factory = _factory()
    with managed_session(second_factory) as session:
        row = store_arcgis_bounded_proof_bundle_chain(session, bundle)
        row.payload_json = row.payload_json.replace(
            '"network_request_count": 5',
            '"network_request_count": 6',
        )

    with (
        managed_session(second_factory) as session,
        pytest.raises(ValueError, match="invalid ArcGIS bounded-proof payload"),
    ):
        load_arcgis_bounded_proof_bundles(session)
