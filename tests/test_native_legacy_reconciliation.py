"""Phase 8 original source replay converges only through the existing native worker."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_dashboard import _record


def test_exact_original_source_replay_is_confirmed_idempotent_and_noncommercial(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record("phase8:replay", title="Retained original source"))
    engine.dispose()
    original_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    directory = tmp_path / "native"
    server = make_server(snapshot(), 0, directory, operator_database=original)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        selection = {"kind": "ceqa", "record_id": "phase8:replay"}
        with httpx.Client(base_url=base, trust_env=False) as client:
            first = client.get("/api/source-reconciliation", params=selection)
            assert first.status_code == 200, first.text
            preview = first.json()
            assert preview["native_state"] == "not_in_native_store"
            assert preview["replay_eligible"] is True
            assert preview["native_evidence_id"] is None
            assert preview["commercial_authority_granted"] is False
            assert client.get("/api/investigations").json()["available"] is False
            body = {
                **selection,
                "expected_source_sha256": preview["original_source"]["source_sha256"],
                "expected_native_evidence_id": None,
                "caller_confirmation": True,
                "review_reason": "Review exact retained CEQA source, without a project identity claim.",
            }
            assert client.post(
                "/api/source-reconciliation-queue", json=body
            ).status_code == 403
            assert client.post(
                "/api/source-reconciliation-queue", json=body,
                headers={"Origin": "https://attacker.example"},
            ).status_code == 403
            assert client.post(
                "/api/source-reconciliation-queue", json={**body, "caller_confirmation": False},
                headers={"Origin": base},
            ).status_code == 400
            assert client.post(
                "/api/source-reconciliation-queue", json={**body, "extra": "authorize"},
                headers={"Origin": base},
            ).status_code == 400
            assert client.post(
                "/api/source-reconciliation-queue",
                json={**body, "expected_source_sha256": "0" * 64},
                headers={"Origin": base},
            ).status_code == 400
            assert client.get(
                "/api/source-reconciliation?kind=ceqa&record_id=phase8:replay&other=1"
            ).status_code == 409
            assert client.get(
                "/api/source-reconciliation?kind=ceqa&kind=permit&record_id=phase8:replay"
            ).status_code == 409
            queued = client.post(
                "/api/source-reconciliation-queue", json=body, headers={"Origin": base}
            )
            assert queued.status_code == 200, queued.text
            receipt = queued.json()
            assert receipt["worker_required"] is True
            assert receipt["outreach_authorized"] is False
            assert receipt["bid_authorized"] is False
            assert receipt["job_status"] in ("pending", "queued")
            runtime = InvestigationRuntime(directory)
            try:
                processed = runtime.process(max_jobs=15)
            finally:
                runtime.close()
            assert processed["processed"] >= 1, processed
            after = client.get("/api/source-reconciliation", params=selection)
            assert after.status_code == 200, after.text
            state = after.json()
            assert state["native_state"] == "exact_observation_already_retained"
            assert state["replay_eligible"] is False
            assert state["native_evidence_id"] == state["expected_evidence_id"]
            assert state["canonical_investigation_id"] is not None
            dossier = client.get(
                "/api/investigations/" + state["canonical_investigation_id"]
            )
            assert dossier.status_code == 200, dossier.text
            assert "phase8:replay" in json.dumps(dossier.json())
            assert client.post(
                "/api/source-reconciliation-queue", json=body, headers={"Origin": base}
            ).status_code == 400
            assert client.get(
                "/api/source-reconciliation?kind=permit&record_id=phase8:replay"
            ).status_code == 409
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_sha
