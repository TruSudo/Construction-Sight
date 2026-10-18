"""Native parcel/GIS source evidence is the original operator view, not a second registry."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from constructionsight.command_center_parcel_readiness import (
    parcel_source_readiness_snapshot,
)
from constructionsight.parcel_schema_preview import preview_schema_for_source_key
from constructionsight.parcel_source_registry import get_parcel_sources
from constructionsight.parcel_source_verification import get_parcel_source_evidence
from tests.test_native_source_inspection import _native


def test_native_parcel_registry_schema_and_verified_source_evidence_are_exact_and_offline(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "private"
    expected = parcel_source_readiness_snapshot()
    sources = get_parcel_sources()
    assert len(sources) == 3
    assert set(expected["schemas"]) == {source.source_key for source in sources}
    assert expected["network_executed"] is False
    assert expected["parcel_source_persisted"] is False
    assert expected["identity_independently_verified"] is False
    assert expected["commercial_authority_granted"] is False
    assert expected["evidence"] == [
        source.to_dict() for source in get_parcel_source_evidence()
    ]
    assert expected["schemas"][sources[0].source_key] == (
        preview_schema_for_source_key(sources[0].source_key).model_dump(mode="json")
    )
    server, worker = _native(directory)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            result = client.get("/api/parcel-source-readiness")
            assert result.status_code == 200, result.text
            assert result.json() == expected
            assert json.loads(result.content) == expected
            assert client.get("/api/parcel-source-readiness?source_key=not-allowed"
                              ).status_code == 409
            assert client.get("/api/parcel-source-readiness?source_key="
                              ).status_code == 409
            assert client.post("/api/parcel-source-readiness", json={}
                               ).status_code in {403, 404}
            assert not (directory / "investigations.sqlite3").exists()
            assert not (directory / "constructionsight.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
