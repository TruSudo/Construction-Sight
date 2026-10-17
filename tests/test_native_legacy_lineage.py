"""Exact source-candidate commercial lineage never silently links projects or money."""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.live_command_center import make_server
from constructionsight.operator_source_candidate import build_source_candidate_preview
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_record,
)
from tests.test_bid_proposal_service import _package
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_dashboard import _record


def test_exact_original_candidate_lineage_requires_evidence_not_auto_merges(
    tmp_path: Path,
) -> None:
    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    source = _record("phase8:lineage", title="Synthetic candidate lineage")
    source = source.model_copy(update={
        "provenance": [
            item.model_copy(update={
                "captured_at": datetime(2026, 10, 17, tzinfo=UTC)
            })
            for item in source.provenance
        ]
    })
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(source)
    with Session(engine) as session:
        candidate = build_source_candidate_preview(
            session, kind="ceqa", record_id="phase8:lineage"
        )
    matching = _package().model_copy(update={
        "package_id": "lead-review:phase8:exact-candidate",
        "base_candidate_id": candidate.candidate_key,
    })
    unrelated = _package().model_copy(update={
        "package_id": "lead-review:phase8:unrelated",
        "base_candidate_id": "unrelated:never-join",
    })
    matched_workflow = create_lead_workflow(package=matching)
    with Session(engine) as session, session.begin():
        for package in (matching, unrelated):
            store_lead_review_package(session, package)
            store_lead_workflow_record(session, create_lead_workflow(package=package))
    engine.dispose()
    original_digest = hashlib.sha256(database.read_bytes()).hexdigest()
    directory = tmp_path / "native"
    server = make_server(snapshot(), 0, directory, operator_database=database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        selection = {"kind": "ceqa", "record_id": "phase8:lineage"}
        with httpx.Client(base_url=base, trust_env=False) as client:
            response = client.get("/api/source-commercial-lineage", params=selection)
            assert response.status_code == 200, response.text
            before = response.json()
            assert before["matching_workflow_total"] == 1
            assert before["native_state"] == "not_in_native_store"
            assert before["commercial_authority_granted"] is False
            assert before["identity_association_verified"] is False
            assert before["result_share_or_payment_verified"] is False
            record = before["matching_workflows"][0]
            assert record["workflow_id"] == matched_workflow.workflow_id
            assert record["canonical_investigation_id"] is None
            assert record["original_candidate_key"] == candidate.candidate_key
            assert record["review_package_status"] == "ready"
            assert record["identity_association_verified"] is False
            assert "unrelated:never-join" not in response.text
            preview = client.get("/api/source-reconciliation", params=selection).json()
            queued = client.post(
                "/api/source-reconciliation-queue",
                json={
                    **selection,
                    "expected_source_sha256": preview["original_source"]["source_sha256"],
                    "expected_native_evidence_id": None,
                    "caller_confirmation": True,
                    "review_reason": "Reviewed source candidate; no same-project or bid approval.",
                },
                headers={"Origin": base},
            )
            assert queued.status_code == 200, queued.text
            runtime = InvestigationRuntime(directory)
            try:
                result = runtime.process(max_jobs=20)
                assert result["failed_jobs"] == 0
            finally:
                runtime.close()
            aligned = client.get("/api/source-commercial-lineage", params=selection)
            assert aligned.status_code == 200, aligned.text
            after = aligned.json()
            assert after["native_state"] == "exact_observation_already_retained"
            assert after["canonical_investigation_id"] is not None
            assert after["matching_workflow_total"] == 1
            assert after["matching_workflows"][0]["canonical_investigation_id"] == (
                after["canonical_investigation_id"]
            )
            assert after["identity_association_verified"] is False
            assert after["commercial_authority_granted"] is False
            for query in (
                "kind=all&record_id=phase8:lineage",
                "kind=ceqa&record_id=phase8:lineage&extra=1",
                "kind=ceqa&record_id=phase8:lineage&limit=21",
                "kind=ceqa&record_id=phase8:lineage&offset=-1",
                "kind=ceqa&kind=permit&record_id=phase8:lineage",
            ):
                assert client.get("/api/source-commercial-lineage?" + query).status_code == 409
            assert client.get(
                "/api/source-commercial-lineage?kind=ceqa&record_id=phase8:lineage"
                "&offset=1"
            ).json()["matching_workflows"] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == original_digest
