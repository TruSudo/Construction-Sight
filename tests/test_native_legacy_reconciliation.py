"""Phase 8 original source replay converges only through the existing native worker."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from constructionsight.command_center_legacy_reconciliation import (
    enqueue_legacy_reconciliation,
    original_source_replay_audit,
    preview_legacy_reconciliation,
)
from constructionsight.intelligence.investigation_service import InvestigationService
from constructionsight.intelligence.investigation_sources import from_domain
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
)
from constructionsight.storage.intelligence_store import IntelligenceStore
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
        source = _record("phase8:replay", title="Retained original source")
        captured = datetime(2026, 10, 17, tzinfo=UTC)
        source = source.model_copy(update={
            "provenance": [
                item.model_copy(update={"captured_at": captured})
                for item in source.provenance
            ]
        })
        CeqaStore(session).upsert(source)
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
                "review_reason": (
                    "Review exact retained CEQA source, without a project identity claim."
                ),
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
            assert receipt["job_status"] == "queued"
            assert receipt["approval_audit_retained"] is True
            assert receipt["approval_audit_event_id"].startswith(
                "event:original-source-replay-approval:"
            )
            audited = client.get(
                "/api/source-reconciliation-audit",
                params={"job": receipt["job_id"]},
            )
            assert audited.status_code == 200, audited.text
            assert audited.json()["audit_event_id"] == receipt["approval_audit_event_id"]
            assert audited.json()["job_status"] == "queued"
            assert audited.json()["approval"]["review_reason"] == body["review_reason"]
            assert audited.json()["commercial_authority_granted"] is False
            assert client.get(
                "/api/source-reconciliation-audit?job=unknown"
            ).status_code == 409
            runtime = InvestigationRuntime(directory)
            try:
                processed = runtime.process(max_jobs=15)
            finally:
                runtime.close()
            assert processed["processed_jobs"] >= 1, processed
            accepted = client.get(
                "/api/source-reconciliation-audit",
                params={"job": receipt["job_id"]},
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["job_status"] == "completed"
            assert accepted.json()["approval"]["source_sha256"] == (
                body["expected_source_sha256"]
            )
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


def test_reviewed_source_replay_rejects_concurrent_existing_native_observation(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original}")
    initialize_database(engine)
    source = _record("phase8:stale", title="Reviewed original source")
    captured = datetime(2026, 10, 17, tzinfo=UTC)
    source = source.model_copy(update={
        "provenance": [
            item.model_copy(update={"captured_at": captured})
            for item in source.provenance
        ]
    })
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(source)
    engine.dispose()
    original_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    directory = tmp_path / "native"
    preview = preview_legacy_reconciliation(
        directory, original, kind="ceqa", record_id="phase8:stale"
    )
    body = {
        "kind": "ceqa",
        "record_id": "phase8:stale",
        "expected_source_sha256": preview["original_source"]["source_sha256"],
        "expected_native_evidence_id": None,
        "caller_confirmation": True,
        "review_reason": "Reviewed the retained source; queue observation only.",
    }
    queued = enqueue_legacy_reconciliation(directory, original, body)
    runtime = InvestigationRuntime(directory)
    try:
        # A separately ingested exact source arrives AFTER the approval but
        # BEFORE the worker claims the reviewed original job.
        with managed_session(runtime.queue.factory) as session:
            InvestigationService(IntelligenceStore(session)).ingest(from_domain(source))
        outcome = runtime.process(max_jobs=1)
        assert outcome["failed_jobs"] == 1
        receipt = original_source_replay_audit(
            directory, job_id=queued["job_id"]
        )
        assert receipt["job_status"] == "failed"
        assert receipt["job_error_code"] == "retained_input_or_state_validation_failed"
        assert receipt["approval"]["review_reason"] == body["review_reason"]
        assert receipt["commercial_authority_granted"] is False
    finally:
        runtime.close()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_sha
