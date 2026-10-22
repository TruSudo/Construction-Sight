"""Offline ArcGIS proof handoff reuses original authority and the native store."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from constructionsight.command_center_arcgis_proofs import (
    native_arcgis_proof_inventory,
    retained_arcgis_proof_preview,
)
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import (
    create_private_database_engine,
    initialize_database,
)
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_parcel_source_acquisition_bundle_storage import _bounded_bundle


def _serve(directory: Path, proof: Path | None):
    server = make_server(snapshot(), 0, directory, operator_arcgis_proof_bundle=proof)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    return server, worker


def _native_database(directory: Path) -> Path:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = directory / "investigations.sqlite3"
    engine = create_private_database_engine(database)
    try:
        initialize_database(engine)
    finally:
        engine.dispose()
    return database


def test_unconfigured_proof_does_not_initialize_or_invent_native_evidence(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "private"
    server, worker = _serve(directory, None)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
        ) as client:
            response = client.get("/api/parcel-arcgis-proof")
            assert response.status_code == 200
            assert response.json()["configured"] is False
            assert client.get("/api/native-parcel-proofs").json()["available"] is False
            assert client.get("/api/parcel-arcgis-proof?unexpected=1").status_code == 409
            assert client.get("/api/native-parcel-proofs?unexpected=1").status_code == 409
            assert not (directory / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_verified_offline_proof_persists_with_exact_origin_and_digest(
    tmp_path: Path,
) -> None:
    bundle = _bounded_bundle()
    proof = tmp_path / "retained-proof.json"
    proof.write_text(json.dumps(bundle.to_dict()))
    original_bytes = proof.read_bytes()
    directory = tmp_path / "private"
    database = _native_database(directory)
    server, worker = _serve(directory, proof)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            response = client.get("/api/parcel-arcgis-proof")
            assert response.status_code == 200, response.text
            review = response.json()
            assert review["bundle_id"] == bundle.bundle_id
            assert review["bundle_sha256"] == hashlib.sha256(original_bytes).hexdigest()
            assert review["verification"]["valid"] is True
            assert (
                review["observed_schema"]["snapshot_id"]
                == bundle.snapshot.snapshot_id
            )
            assert review["observed_schema"]["parcel_imported"] is False
            assert review["observed_schema"]["project_identity_established"] is False
            assert review["network_executed"] is False
            assert review["parcel_imported"] is False
            payload = {
                "expected_bundle_id": bundle.bundle_id,
                "expected_bundle_sha256": review["bundle_sha256"],
                "review_reason": "Preserve this exact offline proof chain for audit.",
                "caller_confirmation": True,
            }
            endpoint = "/api/parcel-arcgis-proof-persist"
            assert client.post(endpoint, json=payload).status_code == 403
            assert client.post(
                endpoint, json=payload,
                headers={"Origin": base, "Sec-Fetch-Site": "cross-site"},
            ).status_code == 400
            for invalid in (
                {**payload, "expected_bundle_sha256": "0" * 64},
                {**payload, "expected_bundle_id": "wrong"},
                {**payload, "caller_confirmation": 1},
                {**payload, "review_reason": "short"},
                {**payload, "unexpected": "write"},
            ):
                assert client.post(
                    endpoint, json=invalid, headers={"Origin": base},
                ).status_code == 400
            assert client.post(
                endpoint + "?extra=1", json=payload, headers={"Origin": base},
            ).status_code == 400
            assert native_arcgis_proof_inventory(directory)["total"] == 0
            accepted = client.post(endpoint, json=payload, headers={"Origin": base})
            assert accepted.status_code == 200, accepted.text
            receipt = accepted.json()
            assert receipt["persisted_in_shared_database"] is True
            assert receipt["receipt"]["bundle_id"] == bundle.bundle_id
            assert receipt["commercial_authority_granted"] is False
            assert receipt["network_executed"] is False
            inventory = client.get("/api/native-parcel-proofs")
            assert inventory.status_code == 200, inventory.text
            assert inventory.json()["total"] == 1
            assert inventory.json()["bundles"] == [bundle.to_dict()]
            assert database.is_file()
            assert proof.read_bytes() == original_bytes
            replay = client.post(endpoint, json=payload, headers={"Origin": base})
            assert replay.status_code == 200, replay.text
            assert client.get("/api/native-parcel-proofs").json()["total"] == 1
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_verified_observed_arcgis_schema_reuses_original_preview_without_import(
    tmp_path: Path,
) -> None:
    bundle = _bounded_bundle()
    proof = tmp_path / "exact-arcgis-proof.json"
    proof.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
    original = proof.read_bytes()

    review = retained_arcgis_proof_preview(proof)
    schema = review["observed_schema"]
    assert review["bundle_sha256"] == hashlib.sha256(original).hexdigest()
    assert schema["bundle_id"] == bundle.bundle_id
    assert schema["snapshot_id"] == bundle.snapshot.snapshot_id
    assert schema["schema_fingerprint"] == bundle.snapshot.schema_fingerprint
    assert schema["metadata_projection_digest"] == (
        bundle.snapshot.metadata_projection_digest
    )
    assert schema["observed_at"] == bundle.snapshot.observed_at.isoformat()
    assert [item["name"] for item in schema["observed_fields"]] == [
        item.name for item in bundle.snapshot.fields
    ]
    assert schema["original_schema_preview_service_reused"] is True
    assert schema["original_schema_preview"]["observed_field_count"] == len(
        bundle.snapshot.fields
    )
    assert schema["original_schema_preview"]["source_key"] == bundle.source_key
    assert schema["original_schema_preview"]["sample_record_count"] is None
    assert schema["network_executed"] is False
    assert schema["parcel_rows_observed"] is False
    assert schema["parcel_imported"] is False
    assert schema["project_identity_established"] is False
    assert schema["commercial_authority_granted"] is False
    assert proof.read_bytes() == original

    # An old valid proof must not be relabeled against a changed or missing
    # original source registry just because its JSON is structurally valid.
    with patch(
        "constructionsight.command_center_arcgis_proofs.get_parcel_sources",
        return_value=[],
    ), pytest.raises(ValueError, match="current registered parcel source"):
        retained_arcgis_proof_preview(proof)
    assert proof.read_bytes() == original


def test_changed_or_corrupt_proof_cannot_be_persisted(tmp_path: Path) -> None:
    bundle = _bounded_bundle()
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps(bundle.to_dict()))
    review = retained_arcgis_proof_preview(proof)
    directory = tmp_path / "private"
    _native_database(directory)
    payload = {
        "expected_bundle_id": bundle.bundle_id,
        "expected_bundle_sha256": review["bundle_sha256"],
        "review_reason": "Preserve this exact independently verified offline proof.",
        "caller_confirmation": True,
    }
    proof.write_text(json.dumps(bundle.to_dict(), indent=2))
    server, worker = _serve(directory, proof)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.post(
                "/api/parcel-arcgis-proof-persist", json=payload,
                headers={"Origin": base},
            ).status_code == 400
            assert client.get("/api/native-parcel-proofs").json()["total"] == 0
            damaged = bundle.to_dict()
            damaged["county"] = "Other County"
            proof.write_text(json.dumps(damaged))
            assert client.get("/api/parcel-arcgis-proof").status_code == 409
            assert client.post(
                "/api/parcel-arcgis-proof-persist", json=payload,
                headers={"Origin": base},
            ).status_code == 400
            assert client.get("/api/native-parcel-proofs").json()["total"] == 0
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_symlinked_proof_is_rejected_before_read(tmp_path: Path) -> None:
    target = tmp_path / "proof.json"
    target.write_text(json.dumps(_bounded_bundle().to_dict()))
    link = tmp_path / "proof-link.json"
    link.symlink_to(target)
    with pytest.raises((ValueError, OSError)):
        retained_arcgis_proof_preview(link)
