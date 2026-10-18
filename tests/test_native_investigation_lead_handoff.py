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
