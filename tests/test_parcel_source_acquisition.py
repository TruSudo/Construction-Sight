from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_bulk_manifest,
    build_arcgis_probe_plan,
    get_official_arcgis_acquisition_assessments,
    get_official_arcgis_capability_snapshots,
    parse_arcgis_capability_snapshot,
    parse_arcgis_probe_observation,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionGapCode,
    ParcelArcGISAcquisitionStatus,
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbeKind,
    ParcelArcGISProbeRequest,
    digest_json_payload,
)
from constructionsight.parcel_source_bulk_rehearsal_models import (
    assemble_arcgis_bulk_rehearsal_evidence,
)
from constructionsight.parcel_source_verification import (
    get_verified_parcel_source_profiles,
)

_OBSERVED_AT = datetime(2026, 7, 14, 16, 0, tzinfo=UTC)


def test_official_capabilities_bind_exact_live_field_projections() -> None:
    snapshots = get_official_arcgis_capability_snapshots()
    profiles = {profile.source_key: profile for profile in get_verified_parcel_source_profiles()}

    assert len(snapshots) == 2
    assert all(snapshot.advertised_ready_for_probe for snapshot in snapshots)
    for snapshot in snapshots:
        assert {field.name for field in snapshot.fields} | {"geometry"} == set(
            profiles[snapshot.source_key].schema_fields
        )
        assert snapshot.object_id_field == "OBJECTID"
        assert snapshot.object_id_is_unique is True
        assert snapshot.supported_query_formats == ("geojson", "json", "pbf")

    san_bernardino = next(item for item in snapshots if item.county == "San Bernardino")
    riverside = next(item for item in snapshots if item.county == "Riverside")
    assert "Shape" not in {field.name for field in san_bernardino.fields}
    assert {"LAND", "STRUCTURES"} <= {field.name for field in riverside.fields}


def test_capability_snapshot_rejects_digest_tampering() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    payload = snapshot.to_dict()
    payload["max_record_count"] += 1

    with pytest.raises(ValidationError, match="projection digest|ID does not match"):
        ParcelArcGISCapabilitySnapshot.model_validate(payload)


def test_probe_observation_retains_verifiable_canonical_response() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    observation = _bounded_observations(plan)[0]

    assert observation.response_payload_json == '{"count":6}'
    payload = observation.to_dict()
    payload["response_payload_json"] = '{"count":7}'
    with pytest.raises(ValidationError, match="response digest"):
        type(observation).model_validate(payload)


def test_metadata_parser_rejects_profile_schema_drift() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    profile = next(
        item
        for item in get_verified_parcel_source_profiles()
        if item.profile_id == snapshot.profile_id
    )
    drifted_profile = profile.model_copy(
        update={"schema_fields": (*profile.schema_fields, "NOT_LIVE")}
    )
    metadata = {
        "currentVersion": snapshot.service_version,
        "geometryType": snapshot.geometry_type,
        "spatialReference": {"wkid": 102646, "latestWkid": 2230},
        "objectIdField": snapshot.object_id_field,
        "uniqueIdField": {
            "name": snapshot.object_id_field,
            "isSystemMaintained": True,
        },
        "maxRecordCount": snapshot.max_record_count,
        "capabilities": "Query",
        "supportsStatistics": True,
        "supportedQueryFormats": "JSON",
        "advancedQueryCapabilities": {
            "supportsStatistics": True,
            "supportsOrderBy": True,
            "supportsPagination": True,
        },
        "fields": [
            {
                "name": field.name,
                "type": field.field_type,
                "nullable": field.nullable,
                **({} if field.length is None else {"length": field.length}),
            }
            for field in snapshot.fields
        ],
    }

    with pytest.raises(ValueError, match="metadata disagrees"):
        parse_arcgis_capability_snapshot(
            drifted_profile,
            metadata,
            observed_at=_OBSERVED_AT,
            limitations=("test limitation",),
        )

    parsed = parse_arcgis_capability_snapshot(
        profile,
        metadata,
        observed_at=_OBSERVED_AT,
        limitations=("test limitation",),
    )
    noisy = parse_arcgis_capability_snapshot(
        profile,
        {**metadata, "drawingInfo": {"renderer": "mutable presentation"}},
        observed_at=_OBSERVED_AT,
        limitations=("test limitation",),
    )
    assert noisy.metadata_projection_digest == parsed.metadata_projection_digest
    assert noisy.snapshot_id == parsed.snapshot_id

    missing_version = dict(metadata)
    missing_version.pop("currentVersion")
    with pytest.raises(ValueError, match="currentVersion"):
        parse_arcgis_capability_snapshot(
            profile,
            missing_version,
            observed_at=_OBSERVED_AT,
            limitations=("test limitation",),
        )


def test_probe_plan_is_bounded_ordered_and_never_authorizes_bulk() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(
        snapshot,
        sample_size=2,
        generated_at=_OBSERVED_AT,
    )

    assert plan.bulk_run_authorized is False
    assert [request.kind for request in plan.requests] == list(ParcelArcGISProbeKind)
    assert plan.requests[0].query_parameters["returnCountOnly"] is True
    assert plan.requests[1].query_parameters["resultOffset"] == 0
    assert plan.requests[2].query_parameters["resultOffset"] == 2
    assert plan.requests[3].query_parameters == plan.requests[1].query_parameters
    assert all(request.return_geometry is False for request in plan.requests)

    unsafe = plan.requests[1].to_dict()
    unsafe["return_geometry"] = True
    with pytest.raises(ValidationError, match="cannot request geometry"):
        ParcelArcGISProbeRequest.model_validate(unsafe)


def test_default_assessment_preserves_unexecuted_probe_boundary() -> None:
    assessments = get_official_arcgis_acquisition_assessments(generated_at=_OBSERVED_AT)

    assert len(assessments) == 2
    assert all(
        assessment.status == ParcelArcGISAcquisitionStatus.METADATA_ONLY
        for assessment in assessments
    )
    assert all(assessment.bulk_acquisition_verified is False for assessment in assessments)
    assert all(
        {gap.code for gap in assessment.gaps}
        == {
            ParcelArcGISAcquisitionGapCode.COUNT_PROBE_MISSING,
            ParcelArcGISAcquisitionGapCode.PAGE_PROBE_MISSING,
            ParcelArcGISAcquisitionGapCode.PAGE_REPLAY_MISSING,
            ParcelArcGISAcquisitionGapCode.BULK_REHEARSAL_MISSING,
        }
        for assessment in assessments
    )


def test_count_adjacent_pages_and_replay_advance_only_to_bounded_query() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    observations = _bounded_observations(plan)

    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        generated_at=_OBSERVED_AT,
    )

    assert assessment.status == ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED
    assert assessment.expected_record_count == 6
    assert assessment.observed_unique_sample_count == 4
    assert assessment.bulk_acquisition_verified is False
    assert [gap.code for gap in assessment.gaps] == [
        ParcelArcGISAcquisitionGapCode.BULK_REHEARSAL_MISSING
    ]


def test_page_replay_mismatch_blocks_acquisition() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    observations = _bounded_observations(plan, replay_ids=(1, 4))

    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        generated_at=_OBSERVED_AT,
    )

    assert assessment.status == ParcelArcGISAcquisitionStatus.BLOCKED
    assert ParcelArcGISAcquisitionGapCode.PAGE_SEQUENCE_INVALID in {
        gap.code for gap in assessment.gaps
    }


def test_page_replay_requires_exact_canonical_response_payload() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    observations = _bounded_observations(
        plan,
        replay_extra={"sourceTimestamp": 123},
    )

    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        generated_at=_OBSERVED_AT,
    )

    assert assessment.status == ParcelArcGISAcquisitionStatus.BLOCKED
    assert ParcelArcGISAcquisitionGapCode.PAGE_SEQUENCE_INVALID in {
        gap.code for gap in assessment.gaps
    }


def test_complete_manifest_requires_count_unique_ids_terminal_resume_and_retry() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    observations = _bounded_observations(plan)
    rehearsal_evidence = _bulk_rehearsal_evidence(snapshot)
    manifest = build_arcgis_bulk_manifest(
        snapshot,
        started_at=_OBSERVED_AT,
        completed_at=_OBSERVED_AT + timedelta(minutes=3),
        starting_count=6,
        ending_count=6,
        rehearsal_evidence=rehearsal_evidence,
    )

    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        bulk_manifest=manifest,
        generated_at=_OBSERVED_AT,
    )

    assert assessment.status == ParcelArcGISAcquisitionStatus.BULK_REHEARSAL_VERIFIED
    assert assessment.bulk_acquisition_verified is True
    assert assessment.gaps == ()

    with pytest.raises(ValidationError, match="stable start and end count"):
        build_arcgis_bulk_manifest(
            snapshot,
            started_at=_OBSERVED_AT,
            completed_at=_OBSERVED_AT + timedelta(minutes=3),
            starting_count=6,
            ending_count=7,
            rehearsal_evidence=rehearsal_evidence,
        )


def _bulk_rehearsal_evidence(snapshot):
    return assemble_arcgis_bulk_rehearsal_evidence(
        snapshot,
        page_size=2,
        page_object_ids=((1, 3), (5, 7), (9, 11)),
        page_response_digests=tuple(digest_json_payload({"page": value}) for value in range(3)),
        page_attempt_counts=(1, 2, 1),
        page_observed_at=(
            _OBSERVED_AT,
            _OBSERVED_AT + timedelta(seconds=30),
            _OBSERVED_AT + timedelta(minutes=2),
        ),
        checkpoint_completed_page_count=1,
        checkpoint_created_at=_OBSERVED_AT + timedelta(seconds=10),
        resumed_at=_OBSERVED_AT + timedelta(seconds=20),
        retry_page_index=1,
        retry_failure_kind="injected_pre_request_transient",
        retry_failed_attempt_count=1,
        retry_fault_injected=True,
        retry_recorded_at=_OBSERVED_AT + timedelta(seconds=25),
        created_at=_OBSERVED_AT + timedelta(minutes=3),
    )


def _bounded_observations(
    plan,
    *,
    replay_ids: tuple[int, ...] = (1, 3),
    replay_extra: dict[str, object] | None = None,
):
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
            "features": [{"attributes": {"OBJECTID": object_id}} for object_id in replay_ids],
            "exceededTransferLimit": True,
            **(replay_extra or {}),
        },
    }
    return [
        parse_arcgis_probe_observation(
            request,
            response_by_kind[request.kind],
            observed_at=_OBSERVED_AT,
        )
        for request in plan.requests
    ]
