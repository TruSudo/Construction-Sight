"""Exact canonical source enters the existing product lead pipeline without commercial effects."""
from __future__ import annotations

import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.command_center_canonical_leads import canonical_lead_preview
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_command_center_live_graph import _record


def test_original_lead_pipeline_preview_is_read_only_and_current(tmp_path: Path) -> None:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    runtime = InvestigationRuntime(folder)
    try:
        runtime.enqueue_bytes(_record().model_dump_json(round_trip=True).encode(), "ceqa")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()
    server = make_server(snapshot(), 0, directory=folder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            identity = client.get("/api/investigations").json()["rows"][0]["investigation_id"]
            dossier = client.get("/api/investigations/" + identity).json()
            before = (folder / "investigations.sqlite3").read_bytes()
            request = {"investigation_id": identity}
            response = client.get("/api/investigation-lead-preview", params=request)
            assert response.status_code == 200, response.text
            preview = response.json()
            assert preview["canonical_investigation_id"] == identity
            assert preview["current_evidence_id"] == (
                dossier["source_membership"][0]["current_evidence_id"]
            )
            assert preview["lead_review_status"] in {"hold", "monitor", "review_required"}
            assert preview["provisional_workflow_status"] in {"hold", "monitor", "review"}
            assert preview["persisted"] is False
            assert preview["outreach_authorized"] is False
            assert preview["commercial_authority_granted"] is False
            product = preview["original_product_integration"]
            assert product["candidate"]["intake_id"].startswith("canonical-intake:")
            assert product["workflow"]["base_candidate_id"] == product["candidate"][
                "candidate_id"
            ]
            assert client.get(
                "/api/investigation-lead-preview", params=request
            ).json()["current_evidence_sha256"] == preview["current_evidence_sha256"]
            assert (folder / "investigations.sqlite3").read_bytes() == before
            assert client.get(
                "/api/investigation-lead-preview", params={**request, "bad": "1"}
            ).status_code == 409
            assert client.get(
                "/api/investigation-lead-preview", params={"investigation_id": "absent"}
            ).status_code == 409
            assert client.post("/api/investigation-lead-preview").status_code == 501
            runtime = InvestigationRuntime(folder)
            try:
                runtime.enqueue_bytes(
                    _record("New exact source revision").model_dump_json(
                        round_trip=True
                    ).encode(), "ceqa"
                )
                assert runtime.process(max_jobs=100)["failed_jobs"] == 0
            finally:
                runtime.close()
            revised = client.get("/api/investigation-lead-preview", params=request)
            assert revised.status_code == 200, revised.text
            assert revised.json()["current_evidence_id"] != preview["current_evidence_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_uninitialized_investigation_cannot_create_lead(tmp_path: Path) -> None:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    with pytest.raises(ValueError):
        canonical_lead_preview(folder, "not-a-retained-investigation")
    assert not (folder / "investigations.sqlite3").exists()


def test_explicit_canonical_lead_handoff_persists_existing_original_workflow(
    tmp_path: Path,
) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from constructionsight.storage.lead_workflow_orm import (
        LeadFingerprintRecord,
        LeadWorkflowRecordRow,
    )
    from constructionsight.storage.operator_read_store import create_operator_read_engine

    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    runtime = InvestigationRuntime(folder)
    try:
        runtime.enqueue_bytes(_record().model_dump_json(round_trip=True).encode(), "ceqa")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()
    server = make_server(snapshot(), 0, directory=folder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as client:
            identity = client.get("/api/investigations").json()["rows"][0]["investigation_id"]
            original = client.get("/api/investigations/" + identity).json()
            preview = client.get(
                "/api/investigation-lead-preview", params={"investigation_id": identity}
            ).json()
            body = {
                "investigation_id": identity,
                "expected_evidence_id": preview["current_evidence_id"],
                "expected_evidence_sha256": preview["current_evidence_sha256"],
                "expected_event_anchor": preview["event_anchor"],
                "reason": "Retain source-claimed project for independent operator review.",
                "caller_confirmation": True,
            }
            assert client.post(
                "/api/investigation-lead-handoff", json=body
            ).status_code == 403
            assert client.post(
                "/api/investigation-lead-handoff", json=body,
                headers={"Origin": "https://untrusted.example"},
            ).status_code == 403
            assert client.post(
                "/api/investigation-lead-handoff",
                json={**body, "caller_confirmation": False},
                headers={"Origin": base},
            ).status_code == 400
            assert client.post(
                "/api/investigation-lead-handoff",
                json={**body, "expected_evidence_sha256": "0" * 64},
                headers={"Origin": base},
            ).status_code == 400
            saved = client.post(
                "/api/investigation-lead-handoff", json=body,
                headers={"Origin": base},
            )
            assert saved.status_code == 200, saved.text
            receipt = saved.json()
            assert receipt["workflow_status"] in {"hold", "monitor", "review"}
            assert receipt["source_evidence_id"] == preview["current_evidence_id"]
            assert receipt["outreach_authorized"] is False
            assert receipt["human_review_required"] is True
            assert client.post(
                "/api/investigation-lead-handoff", json=body,
                headers={"Origin": base},
            ).status_code == 400
            latest = client.get(
                "/api/investigation-lead-preview", params={"investigation_id": identity}
            ).json()
            assert latest["existing_native_handoff"]["workflow_id"] == receipt["workflow_id"]
            assert client.get("/api/investigations/" + identity).json() == original
            engine = create_operator_read_engine(folder / "investigations.sqlite3")
            try:
                with Session(engine) as session:
                    assert session.scalar(
                        select(func.count()).select_from(LeadFingerprintRecord)
                    ) == 1
                    assert session.scalar(
                        select(func.count()).select_from(LeadWorkflowRecordRow)
                    ) == 1
            finally:
                engine.dispose()
            runtime = InvestigationRuntime(folder)
            try:
                runtime.enqueue_bytes(
                    _record("New revision after retained lead").model_dump_json(
                        round_trip=True
                    ).encode(), "ceqa"
                )
                assert runtime.process(max_jobs=100)["failed_jobs"] == 0
            finally:
                runtime.close()
            updated = client.get(
                "/api/investigation-lead-preview", params={"investigation_id": identity}
            ).json()
            assert updated["existing_native_handoff"]["workflow_id"] == receipt["workflow_id"]
            assert client.post(
                "/api/investigation-lead-handoff", json={
                    **body,
                    "expected_evidence_id": updated["current_evidence_id"],
                    "expected_evidence_sha256": updated["current_evidence_sha256"],
                    "expected_event_anchor": updated["event_anchor"],
                }, headers={"Origin": base},
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_lead_console_reads_original_workflow_history_and_source_drift(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    runtime = InvestigationRuntime(folder)
    try:
        runtime.enqueue_bytes(_record().model_dump_json(round_trip=True).encode(), "ceqa")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()
    server = make_server(snapshot(), 0, directory=folder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as client:
            empty = client.get("/api/investigation-lead-workflows")
            assert empty.status_code == 200
            assert empty.json()["total"] == 0
            assert empty.json()["available"] is True
            identity = client.get("/api/investigations").json()["rows"][0]["investigation_id"]
            preview = client.get(
                "/api/investigation-lead-preview", params={"investigation_id": identity}
            ).json()
            payload = {
                "investigation_id": identity,
                "expected_evidence_id": preview["current_evidence_id"],
                "expected_evidence_sha256": preview["current_evidence_sha256"],
                "expected_event_anchor": preview["event_anchor"],
                "reason": "Keep this candidate for manual verification.",
                "caller_confirmation": True,
            }
            saved = client.post(
                "/api/investigation-lead-handoff", json=payload,
                headers={"Origin": base},
            )
            assert saved.status_code == 200, saved.text
            original = (folder / "investigations.sqlite3").read_bytes()
            listing = client.get("/api/investigation-lead-workflows")
            assert listing.status_code == 200, listing.text
            listing_value = listing.json()
            assert listing_value["total"] == 1
            assert listing_value["has_more"] is False
            row = listing_value["rows"][0]
            assert row["canonical_investigation_id"] == identity
            assert row["workflow_id"] == saved.json()["workflow_id"]
            assert row["source_evidence_state"] == "current_source_observation"
            assert row["original_source_evidence_id"] == preview["current_evidence_id"]
            assert row["workflow_status"] in {"hold", "monitor", "review"}
            assert row["transition_count"] == len(row["recent_transitions"])
            assert row["history_integrity_validated"] is True
            assert row["recent_transitions"][0]["historical_only"] is True
            assert row["recent_transitions"][0]["commercial_authority_granted"] is False
            assert row["outreach_authorized"] is False
            assert row["commercial_authority_granted"] is False
            assert client.get(
                "/api/investigation-lead-workflows", params={"offset": 1}
            ).json()["rows"] == []
            for parameters in (
                {"limit": "0"}, {"limit": "51"}, {"offset": "-1"},
                {"limit": "1", "extra": "yes"},
            ):
                assert client.get(
                    "/api/investigation-lead-workflows", params=parameters
                ).status_code == 409
            assert (folder / "investigations.sqlite3").read_bytes() == original
            runtime = InvestigationRuntime(folder)
            try:
                runtime.enqueue_bytes(
                    _record("New source claim after lead retention")
                    .model_dump_json(round_trip=True).encode(), "ceqa"
                )
                assert runtime.process(max_jobs=100)["failed_jobs"] == 0
            finally:
                runtime.close()
            after = client.get("/api/investigation-lead-workflows").json()
            assert after["total"] == 1
            assert after["rows"][0]["workflow_id"] == saved.json()["workflow_id"]
            assert after["rows"][0]["source_evidence_state"] == (
                "source_revision_requires_review"
            )
            assert after["rows"][0]["outreach_authorized"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_lead_workflow_listing_rejects_substituted_database(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    runtime = InvestigationRuntime(folder)
    try:
        runtime.enqueue_bytes(_record().model_dump_json(round_trip=True).encode(), "ceqa")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()
    original = folder / "investigations.sqlite3"
    outside = tmp_path / "outside.sqlite3"
    original.replace(outside)
    original.symlink_to(outside)
    server = make_server(snapshot(), 0, directory=folder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            before = outside.read_bytes()
            assert client.get("/api/investigation-lead-workflows").status_code == 409
            assert outside.read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_console_uninitialized_store_reports_unavailable_without_creating(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    server = make_server(snapshot(), 0, directory=folder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    workflow_file = folder / "workflow.sqlite3"
    workflow_before = workflow_file.read_bytes() if workflow_file.exists() else None
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            response = client.get("/api/investigation-lead-workflows")
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["available"] is False
            assert result["rows"] == []
            assert result["total"] is None
            assert not (folder / "investigations.sqlite3").exists()
            assert (
                workflow_file.read_bytes() if workflow_file.exists() else None
            ) == workflow_before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
