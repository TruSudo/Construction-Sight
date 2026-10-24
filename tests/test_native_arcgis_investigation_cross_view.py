"""Source-backed ArcGIS parcel uses the original approved worker and one graph.

All GIS bytes are synthetic, retained locally; no external collection occurs.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.command_center_arcgis_investigation import (
    enqueue_arcgis_parcel_investigation,
    preview_arcgis_parcel_investigation,
)
from constructionsight.command_center_arcgis_parcel import (
    apply_reviewed_arcgis_parcel,
    preview_reviewed_arcgis_parcel,
)
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.storage.database import create_private_database_engine
from constructionsight.storage.parcel_site_orm import ParcelCoreRecordRow
from tests.test_native_arcgis_parcel_import import _local_retained_source
from tests.test_native_arcgis_proof_persistence import _serve


def _approved(tmp_path: Path):
    directory, proof, request, artifact = _local_retained_source(tmp_path)
    parcel = preview_reviewed_arcgis_parcel(directory, proof, request)
    applied = apply_reviewed_arcgis_parcel(directory, proof, {
        **request,
        "expected_parcel_sha256": parcel["parcel_sha256"],
        "expected_native_state": parcel["native_state"],
        "review_reason": "Review exact synthetic ArcGIS parcel observation independently",
        "caller_confirmation": True,
    })
    assert applied["native_worker_enqueued"] is False
    return directory, proof, {**request,
                              "expected_parcel_sha256": parcel["parcel_sha256"]}, artifact


def test_verified_arcgis_parcel_only_joins_shared_graph_after_worker_approval(
    tmp_path: Path,
) -> None:
    directory, proof, request, artifact = _approved(tmp_path)
    original_bytes = artifact.read_bytes()
    initial = preview_arcgis_parcel_investigation(directory, proof, request)
    assert initial["native_state"] == "not_in_native_store"
    assert initial["replay_eligible"] is True
    assert initial["native_evidence_id"] is None
    assert initial["parcel_to_project_identity_verified"] is False
    assert initial["commercial_authority_granted"] is False
    for invalid in (
        {**request, "expected_parcel_sha256": "0" * 64},
        {**request, "source_url": "https://forged.invalid"},
    ):
        with pytest.raises(ValueError):
            preview_arcgis_parcel_investigation(directory, proof, invalid)
    approved = {
        **request,
        "expected_native_evidence_id": None,
        "action": "retain_missing",
        "review_reason": "Approve one separately verified parcel source worker replay",
        "caller_confirmation": True,
    }
    for bad in (
        {**approved, "caller_confirmation": False},
        {**approved, "action": "retain_revision"},
        {**approved, "expected_native_evidence_id": "forged"},
        {**approved, "commercial_authority": True},
    ):
        with pytest.raises(ValueError):
            enqueue_arcgis_parcel_investigation(directory, proof, bad)
    server, thread = _serve(directory, proof)
    base = f"http://127.0.0.1:{server.server_port}"
    canonical_id = None
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            path = "/api/parcel-arcgis-investigation-preview"
            assert client.post(path, json=request).status_code == 403
            response = client.post(path, json=request, headers={"Origin": base})
            assert response.status_code == 200, response.text
            assert response.json()["replay_eligible"] is True
            assert client.post(
                path+"?override=1", json=request, headers={"Origin": base},
            ).status_code == 400
            queued = client.post(
                "/api/parcel-arcgis-investigation-queue", json=approved,
                headers={"Origin": base},
            )
            assert queued.status_code == 200, queued.text
            receipt = queued.json()
            assert receipt["native_worker_required"] is True
            assert receipt["approval_audit_retained"] is True
            assert receipt["project_identity_verified"] is False
            assert receipt["commercial_authority_granted"] is False
            assert receipt["job_id"]
            before = client.get("/api/investigations")
            assert before.status_code == 200
            assert before.json()["total"] == 0
            assert artifact.read_bytes() == original_bytes
            runtime = InvestigationRuntime(directory)
            try:
                first = runtime.process(max_jobs=100)
                second = runtime.process(max_jobs=100)
                assert first["failed_jobs"] == 0
                # The original queue may also hold background bookkeeping.
                # The exact canonical parcel identity below is authoritative.
                assert first["processed_jobs"] >= 1
                assert second["processed_jobs"] == 0
            finally:
                runtime.close()
            after = client.get("/api/investigations", params={
                "source":"parcel", "location":"unmapped",
            })
            assert after.status_code == 200, after.text
            listing = after.json()
            assert listing["total"] == 1
            assert listing["mapped_on_page"] == 0
            assert len(listing["rows"]) == 1
            row = listing["rows"][0]
            assert row["points"] == []
            assert row["assessment"]["identity_independently_verified"] is False
            assert row["assessment"]["commercial_authority_granted"] is False
            canonical_id = row["investigation_id"]
            dossier = client.get("/api/investigations/"+quote(canonical_id,safe=""))
            assert dossier.status_code == 200, dossier.text
            result = dossier.json()
            assert result["source_claimed_points"] == []
            assert len(result["source_observations"]) == 1
            evidence = result["source_observations"][0]["evidence"]
            assert evidence["source_family"] == "parcel"
            assert evidence["source_record_id"] == "3"
            assert evidence["raw_observations"]["parcel_record"]["normalized_apn"] == (
                "123456789"
            )
            assert result["assessment"]["commercial_authority_granted"] is False
            graph = client.get("/api/investigation-graph")
            assert graph.status_code == 200, graph.text
            nodes = graph.json()["nodes"]
            assert canonical_id in [node["id"] for node in nodes]
            assert graph.json()["commercial_authority_granted"] is False
            checked = client.post(path, json=request, headers={"Origin": base})
            assert checked.status_code == 200
            assert checked.json()["native_state"] == "exact_observation_already_retained"
            assert checked.json()["replay_eligible"] is False
            assert client.post(
                "/api/parcel-arcgis-investigation-queue", json=approved,
                headers={"Origin": base},
            ).status_code == 400
            assert artifact.read_bytes() == original_bytes
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert canonical_id


def test_arcgis_source_worker_refuses_missing_or_tampered_original_core(
    tmp_path: Path,
) -> None:
    directory, proof, request, artifact = _approved(tmp_path)
    before = artifact.read_bytes()
    engine = create_private_database_engine(
        directory / "investigations.sqlite3", create=False,
    )
    try:
        with Session(engine) as session, session.begin():
            row = session.scalar(select(ParcelCoreRecordRow))
            assert row is not None
            tampered = json.loads(row.payload_json)
            tampered["apn"] = "999999999"
            row.payload_json = json.dumps(tampered)
    finally:
        engine.dispose()
    with pytest.raises(ValueError, match="stored original parcel differs"):
        preview_arcgis_parcel_investigation(directory, proof, request)
    assert artifact.read_bytes() == before
