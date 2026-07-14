from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_bulk_rehearsal import (
    JSONFileParcelArcGISCheckpointStore,
    ParcelArcGISBulkTransientError,
    execute_arcgis_complete_rehearsal,
)
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    JSONFileParcelArcGISBulkArtifactStore,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    HTTPParcelArcGISBulkRehearsalSource,
    ParcelArcGISBulkHTTPError,
    build_arcgis_bulk_rehearsal_plan,
)

_NOW = datetime(2026, 7, 14, 21, 0, tzinfo=UTC)


@dataclass
class _Clock:
    value: datetime = _NOW

    def __call__(self) -> datetime:
        current = self.value
        self.value = self.value + timedelta(seconds=1)
        return current


def _snapshot(index: int = 0):
    return get_official_arcgis_capability_snapshots()[index]


def _plan(**overrides):
    values = {
        "generated_at": _NOW,
        "page_size": 2,
        "checkpoint_after_pages": 1,
        "injected_retry_page_index": 1,
        "max_attempts": 3,
        "retry_delays_seconds": (0.0, 0.0),
    }
    values.update(overrides)
    return build_arcgis_bulk_rehearsal_plan(_snapshot(), **values)


def test_rehearsal_plan_is_deterministic_digest_bound_and_non_authorizing() -> None:
    first = _plan()
    second = _plan()

    assert first == second
    assert first.plan_id.startswith("parcel-arcgis-bulk-rehearsal-plan:")
    assert first.query_url == _snapshot().layer_url.rstrip("/") + "/query"
    assert first.rehearsal_policy.page_size == 2
    assert first.rehearsal_policy.injected_retry_page_index == 1
    assert first.http_policy.max_response_bytes == 2_000_000
    assert first.bulk_run_authorized is False
    assert first.to_dict()["plan_id"] == first.plan_id


def test_http_source_preserves_exact_noncanonical_count_and_page_bytes() -> None:
    count_body = b'{  "count" : 6 }\n'
    page_body = b'{ "objectIds" : [1, 2] }\n'
    requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        parameters = dict(request.url.params)
        requests.append(parameters)
        body = count_body if parameters.get("returnCountOnly") == "true" else page_body
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = HTTPParcelArcGISBulkRehearsalSource(_snapshot(), _plan(), client)
        count = source.fetch_count()
        page = source.fetch_object_id_page(
            offset=0,
            record_count=2,
            attempt_number=1,
        )

    assert count.count == 6
    assert count.response_body == count_body
    assert page.response_body == page_body
    assert requests == [
        {
            "f": "json",
            "returnCountOnly": "true",
            "returnGeometry": "false",
            "where": "1=1",
        },
        {
            "f": "json",
            "orderByFields": f"{_snapshot().object_id_field} ASC",
            "outFields": _snapshot().object_id_field,
            "resultOffset": "0",
            "resultRecordCount": "2",
            "returnGeometry": "false",
            "where": "1=1",
        },
    ]


def test_http_source_runs_complete_executor_without_hidden_transport_retries(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, int | None]] = []
    count_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count_calls
        parameters = dict(request.url.params)
        if parameters.get("returnCountOnly") == "true":
            count_calls += 1
            calls.append(("count", None))
            return httpx.Response(200, json={"count": 6})
        offset = int(parameters["resultOffset"])
        calls.append(("page", offset))
        pages = {
            0: (1, 2),
            2: (3, 4),
            4: (5, 6),
        }
        return httpx.Response(200, json={"objectIds": list(pages[offset])})

    plan = _plan()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = execute_arcgis_complete_rehearsal(
            _snapshot(),
            HTTPParcelArcGISBulkRehearsalSource(_snapshot(), plan, client),
            JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
            JSONFileParcelArcGISBulkArtifactStore(tmp_path / "responses"),
            policy=plan.rehearsal_policy,
            now=_Clock(),
            sleep=lambda _delay: None,
        )

    assert calls == [
        ("count", None),
        ("page", 0),
        ("page", 2),
        ("page", 4),
        ("count", None),
    ]
    assert count_calls == 2
    assert result.manifest.retrieved_count == 6
    assert result.manifest.page_count == 3
    assert result.manifest.checkpoint_resume_verified is True
    assert result.manifest.retry_recovery_verified is True
    assert result.manifest.rehearsal_evidence.retry_events[0].fault_injected is True
    assert result.bulk_run_authorized is False


def test_http_source_classifies_one_transient_status_per_source_call() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json={"objectIds": [1, 2]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = HTTPParcelArcGISBulkRehearsalSource(_snapshot(), _plan(), client)
        with pytest.raises(ParcelArcGISBulkTransientError, match="http_503"):
            source.fetch_object_id_page(
                offset=0,
                record_count=2,
                attempt_number=1,
            )
        response = source.fetch_object_id_page(
            offset=0,
            record_count=2,
            attempt_number=2,
        )

    assert calls == 2
    assert response.payload()["objectIds"] == [1, 2]


def test_http_source_classifies_arcgis_service_errors() -> None:
    responses = iter(
        (
            httpx.Response(200, json={"error": {"code": 503, "message": "temporary"}}),
            httpx.Response(200, json={"error": {"code": 400, "message": "bad query"}}),
        )
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return next(responses)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = HTTPParcelArcGISBulkRehearsalSource(_snapshot(), _plan(), client)
        with pytest.raises(ParcelArcGISBulkTransientError, match="arcgis_503"):
            source.fetch_count()
        with pytest.raises(ParcelArcGISBulkHTTPError, match="terminal error 400"):
            source.fetch_count()


def test_http_source_rejects_redirects_even_when_client_follows_them() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/query"):
            return httpx.Response(
                302,
                headers={"Location": "https://example.test/elsewhere"},
            )
        return httpx.Response(200, json={"count": 6})

    with (
        httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        ) as client,
        pytest.raises(ParcelArcGISBulkHTTPError, match="redirects are forbidden"),
    ):
        HTTPParcelArcGISBulkRehearsalSource(_snapshot(), _plan(), client).fetch_count()


def test_http_source_rejects_terminal_status_media_type_and_oversize() -> None:
    def not_found(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "missing"})

    with (
        httpx.Client(transport=httpx.MockTransport(not_found)) as client,
        pytest.raises(ParcelArcGISBulkHTTPError, match="HTTP 404"),
    ):
        HTTPParcelArcGISBulkRehearsalSource(_snapshot(), _plan(), client).fetch_count()

    def html(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html></html>",
            headers={"Content-Type": "text/html"},
        )

    with (
        httpx.Client(transport=httpx.MockTransport(html)) as client,
        pytest.raises(ParcelArcGISBulkHTTPError, match="media type"),
    ):
        HTTPParcelArcGISBulkRehearsalSource(_snapshot(), _plan(), client).fetch_count()

    def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"objectIds":[1,2]}')

    with (
        httpx.Client(transport=httpx.MockTransport(oversized)) as client,
        pytest.raises(ParcelArcGISBulkHTTPError, match="byte limit"),
    ):
        HTTPParcelArcGISBulkRehearsalSource(
            _snapshot(),
            _plan(max_response_bytes=5),
            client,
        ).fetch_object_id_page(
            offset=0,
            record_count=2,
            attempt_number=1,
        )


def test_http_source_rejects_invalid_page_scope_and_plan_mismatch() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(500))
    ) as client:
        source = HTTPParcelArcGISBulkRehearsalSource(_snapshot(), _plan(), client)
        with pytest.raises(ValueError, match="page size does not match"):
            source.fetch_object_id_page(
                offset=0,
                record_count=3,
                attempt_number=1,
            )
        with pytest.raises(ValueError, match="offset must align"):
            source.fetch_object_id_page(
                offset=1,
                record_count=2,
                attempt_number=1,
            )
        with pytest.raises(ValueError, match="attempt number"):
            source.fetch_object_id_page(
                offset=0,
                record_count=2,
                attempt_number=4,
            )
        with pytest.raises(ValueError, match="does not match the snapshot"):
            HTTPParcelArcGISBulkRehearsalSource(_snapshot(1), _plan(), client)


def test_plan_rejects_unsupported_snapshot_and_oversized_page() -> None:
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="page size exceeds"):
        build_arcgis_bulk_rehearsal_plan(
            snapshot,
            generated_at=_NOW,
            page_size=snapshot.max_record_count + 1,
        )
