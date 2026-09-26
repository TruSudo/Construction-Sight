from datetime import UTC, datetime

import httpx
import pytest

import constructionsight.http_transport as http_transport_module
from constructionsight.parcel_source_acquisition import (
    build_arcgis_probe_plan,
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_acquisition_http import (
    ParcelArcGISProbeExecutionError,
    execute_arcgis_probe_plan,
)

_NOW = datetime(2026, 7, 14, 17, 0, tzinfo=UTC)


def test_arcgis_probe_preserves_redirect_failure_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_probe_plan(snapshot, generated_at=_NOW)
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302,
            headers={"Location": "https://example.test/elsewhere"},
        )

    def build_client() -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
            trust_env=False,
        )

    monkeypatch.setattr(http_transport_module, "_build_http_client", build_client)

    with pytest.raises(
        ParcelArcGISProbeExecutionError,
        match="ArcGIS HTTP redirects are forbidden",
    ):
        execute_arcgis_probe_plan(
            snapshot,
            plan,
            now=lambda: _NOW,
            sleep=lambda _delay: None,
        )

    assert calls == 1
