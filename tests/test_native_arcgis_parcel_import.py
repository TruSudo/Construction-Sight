"""Exact source-response to reviewed native parcel-core persistence.

Synthetic official bytes only; no external GIS acquisition is performed.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.command_center_arcgis_parcel import (
    apply_reviewed_arcgis_parcel,
    preview_reviewed_arcgis_parcel,
)
from constructionsight.command_center_arcgis_record import (
    _verify_exact_arcgis_feature,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.storage.database import create_private_database_engine
from constructionsight.storage.parcel_site_orm import (
    ParcelCoreRecordRow,
    ParcelRecordObservationRow,
)
from constructionsight.storage.runtime_artifacts import write_runtime_text
from tests.test_native_arcgis_proof_persistence import _serve
from tests.test_native_arcgis_single_record_acquisition import _body, _fixture


def _local_retained_source(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, object], Path]:
    proof, ids, plan = _fixture(tmp_path)
    directory = tmp_path / "native"
    raw = _body()
    sha = hashlib.sha256(raw).hexdigest()
    from constructionsight.parcel_source_acquisition_http import _exact_request_url

    retained = {
        "schema_version": "constructionsight.arcgis-single-record-body/v1",
        "plan_id": plan["plan_id"],
        "source_key": plan["source_key"],
        "bundle_id": plan["bundle_id"],
        "bundle_sha256": plan["bundle_sha256"],
        "snapshot_id": plan["snapshot_id"],
        "object_id": plan["object_id"],
        "request_url": _exact_request_url(plan["query_url"], plan["parameters"]),
        "response_sha256": sha,
        "response_body_base64": base64.b64encode(raw).decode("ascii"),
        "observed_at": datetime(2026, 10, 22, tzinfo=UTC).isoformat(),
        "report": _verify_exact_arcgis_feature(proof, plan, raw),
        "network_executed": True,
        "parcel_persisted": False,
        "site_identity_verified": False,
        "commercial_authority_granted": False,
    }
    evidence_file = plan["plan_id"].replace(":", "-") + ".json"
    path = directory / "arcgis-record-evidence" / evidence_file
    write_runtime_text(path, json.dumps(retained), max_bytes=2_000_000)
    request = {
        **ids,
        "expected_plan_id": plan["plan_id"],
        "expected_response_sha256": sha,
    }
    return directory, proof, request, path


def test_exact_retained_arcgis_parcel_requires_separate_review_and_retains_once(
    tmp_path: Path,
) -> None:
    directory, proof, request, artifact = _local_retained_source(tmp_path)
    original = artifact.read_bytes()
    baseline = preview_reviewed_arcgis_parcel(directory, proof, request)
    assert baseline["may_request_persistence"] is True
    assert baseline["native_state"] == "absent"
    assert baseline["parcel_persisted"] is False
    assert baseline["site_identity_verified"] is False
    assert baseline["geometry_verified"] is False
    assert baseline["commercial_authority_granted"] is False
    assert baseline["parcel"]["normalized_apn"] == "123456789"
    assert baseline["parcel"]["geometry"] is None
    assert baseline["parcel"]["source_record_id"] == "3"
    assert not (directory / "investigations.sqlite3").exists()
    payload = {
        **request,
        "expected_parcel_sha256": baseline["parcel_sha256"],
        "expected_native_state": baseline["native_state"],
        "review_reason": "Retain one verified original parcel source observation",
        "caller_confirmation": True,
    }
    for changed in (
        {**payload, "caller_confirmation": False},
        {**payload, "extra": "authorize-commerce"},
        {**payload, "expected_parcel_sha256": "0" * 64},
        {**payload, "expected_native_state": "exact_replay"},
    ):
        with pytest.raises(ValueError):
            apply_reviewed_arcgis_parcel(directory, proof, changed)
    assert not (directory / "investigations.sqlite3").exists()
    receipt = apply_reviewed_arcgis_parcel(directory, proof, payload)
    assert receipt["parcel_persisted"] is True
    assert receipt["observation_retained"] is True
    assert receipt["native_worker_enqueued"] is False
    assert receipt["commercial_authority_granted"] is False
    assert receipt["geometry_verified"] is False
    assert artifact.read_bytes() == original
    engine = create_private_database_engine(
        directory / "investigations.sqlite3", create=False,
    )
    try:
        with Session(engine) as session:
            records = session.scalars(select(ParcelCoreRecordRow)).all()
            observations = session.scalars(select(ParcelRecordObservationRow)).all()
            assert len(records) == len(observations) == 1
            record = ParcelCoreRecord.model_validate(json.loads(records[0].payload_json))
            assert record.parcel_record_id == receipt["parcel_record_id"]
            assert record.geometry is None
            assert record.source_record_id == "3"
    finally:
        engine.dispose()
    repeated = preview_reviewed_arcgis_parcel(directory, proof, request)
    assert repeated["native_state"] == "exact_replay"
    exact = apply_reviewed_arcgis_parcel(
        directory, proof, {**payload, "expected_native_state": "exact_replay"},
    )
    assert exact["parcel_record_id"] == receipt["parcel_record_id"]
    with pytest.raises(ValueError, match="stale"):
        apply_reviewed_arcgis_parcel(directory, proof, payload)
    assert artifact.read_bytes() == original


def test_retained_arcgis_parcel_rejects_tampering_and_source_substitutions(
    tmp_path: Path,
) -> None:
    directory, proof, request, artifact = _local_retained_source(tmp_path)
    for changed in (
        {**request, "expected_plan_id": "other"},
        {**request, "object_id": 2},
        {**request, "expected_response_sha256": "0" * 64},
        {**request, "source_url": "https://attacker.invalid/"},
    ):
        with pytest.raises(ValueError):
            preview_reviewed_arcgis_parcel(directory, proof, changed)
    original = json.loads(artifact.read_text())
    for mutation in (
        {"response_sha256": "0" * 64},
        {"object_id": 7},
        {"commercial_authority_granted": True},
        {"response_body_base64": base64.b64encode(_body(4)).decode("ascii")},
    ):
        artifact.write_text(json.dumps({**original, **mutation}))
        with pytest.raises(ValueError):
            preview_reviewed_arcgis_parcel(directory, proof, request)
    artifact.write_text(json.dumps(original))
    assert preview_reviewed_arcgis_parcel(
        directory, proof, request,
    )["may_request_persistence"] is True


def test_retained_arcgis_record_persistence_same_origin_and_no_implicit_import(
    tmp_path: Path,
) -> None:
    directory, proof, request, artifact = _local_retained_source(tmp_path)
    before = artifact.read_bytes()
    server, worker = _serve(directory, proof)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            preview_url = "/api/parcel-arcgis-parcel-preview"
            assert client.post(preview_url, json=request).status_code == 403
            view = client.post(
                preview_url, json=request, headers={"Origin": base},
            )
            assert view.status_code == 200, view.text
            assert view.json()["parcel_persisted"] is False
            assert client.post(
                preview_url + "?override=1", json=request,
                headers={"Origin": base},
            ).status_code == 400
            route = "/api/parcel-arcgis-parcel-apply"
            assert client.post(
                route, json={**request, "expected_parcel_sha256": "0" * 64,
                             "expected_native_state": "absent",
                             "caller_confirmation": True,
                             "review_reason": "Unauthorized replacement"},
                headers={"Origin": base},
            ).status_code == 400
            assert client.post(
                route, json={**request, "expected_parcel_sha256":
                             view.json()["parcel_sha256"],
                             "expected_native_state": "absent",
                             "caller_confirmation": False,
                             "review_reason": "Unauthorized replacement"},
                headers={"Origin": base},
            ).status_code == 400
            assert artifact.read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
