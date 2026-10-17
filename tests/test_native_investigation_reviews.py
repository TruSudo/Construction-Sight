"""Phase 8: explicit native reviews reuse the existing worker graph and authority service."""

from __future__ import annotations

import hashlib
import threading

import httpx
import pytest

from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_investigation_multisource_acceptance import retained_inputs


def _ingest(directory, update=False):
    runtime = InvestigationRuntime(directory)
    try:
        for kind, record in retained_inputs()[:2]:
            if update and kind == "ceqa":
                record = record.model_copy(update={"title": "Revised synthetic CEQA evidence"})
            runtime.enqueue_bytes(record.model_dump_json(round_trip=True).encode(), kind)
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()


@pytest.fixture
def native(tmp_path):
    directory = tmp_path / "private"
    _ingest(directory)
    server = make_server(snapshot(), 0, directory)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, headers={"Origin": base}, trust_env=False) as client:
            inventory = client.get("/api/investigations").json()
            identity = inventory["rows"][0]["investigation_id"]
            dossier = client.get("/api/investigations/" + identity).json()
            relationship = dossier["candidate_source_links"][0]["relationship_id"]
            yield directory, client, identity, relationship
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def _preview(client, relationship):
    response = client.get("/api/investigation-review", params={"relationship": relationship})
    assert response.status_code == 200, response.text
    return response.json()


def _request(preview, decision="associate", **changes):
    return {
        "relationship_id": preview["relationship"]["relationship_id"],
        "expected_identity": preview["expected_identity"],
        "decision": decision,
        "target_id": preview["target_choices"][0] if decision == "associate" else None,
        "reason": "Synthetic operator reviewed the retained source context.",
        "caller_confirmation": True,
        "operator_id": "operator:phase8-test",
        **changes,
    }


def test_native_preview_is_read_only_and_associate_then_reject_preserves_source_identity(native):
    directory, client, identity, relationship = native
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    preview = _preview(client, relationship)
    assert preview["review_applied"] is False
    assert len(preview["investigations"]) == 2
    assert all(len(d["source_membership"]) == 1 for d in preview["investigations"].values())
    assert {
        p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    } == before
    retained = {p.name: p.read_bytes() for p in (directory / "investigation-inputs").iterdir()}
    applied = client.post("/api/investigation-review", json=_request(preview))
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["review_applied"] is True
    assert result["identity_independently_verified"] is False
    assert result["commercial_authority_granted"] is False
    inventory = client.get("/api/investigations").json()
    assert inventory["total"] == 1
    dossier = client.get("/api/investigations/" + result["target_id"]).json()
    assert len(dossier["source_membership"]) == 2
    assert dossier["assessment"]["identity_independently_verified"] is False
    assert client.get("/api/leads").json()["rows"] == []
    assert len(client.get("/api/investigation-graph").json()["roots"]) == 1
    repeated = client.post("/api/investigation-review", json=_request(preview))
    assert repeated.status_code == 400
    current = _preview(client, relationship)
    rejected = client.post("/api/investigation-review", json=_request(current, "reject"))
    assert rejected.status_code == 200, rejected.text
    assert client.get("/api/investigations").json()["total"] == 2
    assert len(client.get("/api/investigation-graph").json()["roots"]) == 2
    assert {
        p.name: p.read_bytes() for p in (directory / "investigation-inputs").iterdir()
    } == retained
    for digest, original in retained.items():
        assert hashlib.sha256(original).hexdigest() == digest


@pytest.mark.parametrize(
    "changes",
    [
        {"caller_confirmation": False},
        {"caller_confirmation": "true"},
        {"reason": " "},
        {"target_id": "investigation:unrelated"},
        {"identity_independently_verified": True},
        {"operator_id": 123},
    ],
)
def test_native_review_rejects_invalid_or_overbroad_effect_without_mutation(native, changes):
    directory, client, _, relationship = native
    preview = _preview(client, relationship)
    before = (directory / "investigations.sqlite3").read_bytes()
    response = client.post("/api/investigation-review", json=_request(preview, **changes))
    assert response.status_code == 400
    assert (directory / "investigations.sqlite3").read_bytes() == before


def test_source_revision_invalidates_native_review_preview(native):
    directory, client, _, relationship = native
    preview = _preview(client, relationship)
    _ingest(directory, update=True)
    before = (directory / "investigations.sqlite3").read_bytes()
    response = client.post("/api/investigation-review", json=_request(preview))
    assert response.status_code == 400 and "changed" in response.text
    assert (directory / "investigations.sqlite3").read_bytes() == before
    assert client.get("/api/investigations").json()["total"] == 2


def test_native_review_rejects_cross_origin_and_missing_preview_store(native, tmp_path):
    directory, client, _, relationship = native
    preview = _preview(client, relationship)
    before = (directory / "investigations.sqlite3").read_bytes()
    response = client.post(
        "/api/investigation-review",
        json=_request(preview),
        headers={"Origin": "https://unrelated.test"},
    )
    assert response.status_code == 403
    assert (directory / "investigations.sqlite3").read_bytes() == before
    other = tmp_path / "empty"
    server = make_server(snapshot(), 0, other)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, headers={"Origin": base}, trust_env=False) as client:
            assert (
                client.get(
                    "/api/investigation-review", params={"relationship": relationship}
                ).status_code
                == 409
            )
            assert (
                client.post("/api/investigation-review", json=_request(preview)).status_code == 400
            )
        assert not (other / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
