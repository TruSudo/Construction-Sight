from datetime import UTC, datetime

import httpx
import pytest

from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_probe_plan,
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_acquisition_http import (
    ParcelArcGISHTTPPolicy,
    ParcelArcGISProbeExecutionError,
    execute_arcgis_probe_plan,
    fetch_arcgis_capability_snapshot,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionStatus,
)
from constructionsight.parcel_source_verification import (
    get_verified_parcel_source_profiles,
)

_NOW = datetime(2026, 7, 14, 17, 0, tzinfo=UTC)


def test_http_executor_fetches_metadata_then_runs_only_bounded_plan() -> None:
    baseline = get_official_arcgis_capability_snapshots()[0]
    profile = next(
        item
        for item in get_verified_parcel_source_profiles()
        if item.profile_id == baseline.profile_id
    )
    metadata = _metadata_for_snapshot(baseline)
    requested_parameters: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/query"):
            parameters = dict(request.url.params)
            requested_parameters.append(parameters)
            if parameters.get("returnCountOnly") == "true":
                return httpx.Response(200, json={"count": 6})
            offset = int(parameters["resultOffset"])
            object_ids = (1, 3) if offset == 0 else (5, 7)
            return httpx.Response(
                200,
                json={
                    "features": [
                        {"attributes": {"OBJECTID": object_id}} for object_id in object_ids
                    ],
                    "exceededTransferLimit": True,
                },
            )
        return httpx.Response(200, json=metadata)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = fetch_arcgis_capability_snapshot(
            profile,
            client,
            limitations=("bounded test metadata",),
            now=lambda: _NOW,
            sleep=lambda _delay: None,
        )
        plan = build_arcgis_probe_plan(snapshot, generated_at=_NOW)
        observations = execute_arcgis_probe_plan(
            snapshot,
            plan,
            client,
            now=lambda: _NOW,
            sleep=lambda _delay: None,
        )

    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        generated_at=_NOW,
    )
    assert len(observations) == 4
    assert len(requested_parameters) == 4
    assert all(parameters["returnGeometry"] == "false" for parameters in requested_parameters)
    assert assessment.status == ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED
    assert assessment.bulk_acquisition_verified is False


def test_http_executor_retries_only_bounded_transient_failures() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_NOW)
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary"})
        if dict(request.url.params).get("returnCountOnly") == "true":
            return httpx.Response(200, json={"count": 2})
        return httpx.Response(
            200,
            json={
                "features": [
                    {"attributes": {"OBJECTID": 1}},
                    {"attributes": {"OBJECTID": 3}},
                ]
                if dict(request.url.params)["resultOffset"] == "0"
                else [],
                "exceededTransferLimit": False,
            },
        )

    policy = ParcelArcGISHTTPPolicy(
        max_attempts=2,
        retry_delays_seconds=(0.0,),
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        observations = execute_arcgis_probe_plan(
            snapshot,
            plan,
            client,
            policy=policy,
            now=lambda: _NOW,
            sleep=delays.append,
        )

    assert len(observations) == 4
    assert calls == 5
    assert delays == [0.0]


def test_http_executor_fails_closed_on_nonretryable_status_and_oversize() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_NOW)
    calls = 0

    def not_found(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, json={"error": "missing"})

    with (
        httpx.Client(transport=httpx.MockTransport(not_found)) as client,
        pytest.raises(ParcelArcGISProbeExecutionError, match="HTTP 404"),
    ):
        execute_arcgis_probe_plan(
            snapshot,
            plan,
            client,
            now=lambda: _NOW,
            sleep=lambda _delay: None,
        )
    assert calls == 1

    def partial_content(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(206, json={"count": 2})

    with (
        httpx.Client(transport=httpx.MockTransport(partial_content)) as client,
        pytest.raises(ParcelArcGISProbeExecutionError, match="HTTP 206"),
    ):
        execute_arcgis_probe_plan(
            snapshot,
            plan,
            client,
            now=lambda: _NOW,
            sleep=lambda _delay: None,
        )

    def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 20)

    with (
        httpx.Client(transport=httpx.MockTransport(oversized)) as client,
        pytest.raises(ParcelArcGISProbeExecutionError, match="byte limit"),
    ):
        execute_arcgis_probe_plan(
            snapshot,
            plan,
            client,
            policy=ParcelArcGISHTTPPolicy(max_response_bytes=10),
            now=lambda: _NOW,
            sleep=lambda _delay: None,
        )


def _metadata_for_snapshot(snapshot) -> dict[str, object]:
    if snapshot.county == "Riverside":
        spatial_reference = {"wkid": 102646, "latestWkid": 2230}
    else:
        spatial_reference = {"wkid": 102100, "latestWkid": 3857}
    return {
        "currentVersion": snapshot.service_version,
        "geometryType": snapshot.geometry_type,
        "spatialReference": spatial_reference,
        "objectIdField": snapshot.object_id_field,
        "uniqueIdField": {
            "name": snapshot.object_id_field,
            "isSystemMaintained": True,
        },
        "maxRecordCount": snapshot.max_record_count,
        "capabilities": "Query",
        "supportsStatistics": True,
        "supportedQueryFormats": "JSON, geoJSON, PBF",
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
