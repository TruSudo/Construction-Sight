"""Native Command Center Phase 5 read-only shared investigation acceptance."""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


def snapshot() -> dict[str, Any]:
    return {
        "rows": [],
        "captured_at": "2026-10-16T12:00:00+00:00",
        "requests": 0,
        "totals": {"Riverside": 0, "San Bernardino": 0},
        "baseline": True,
        "missing_count": 0,
    }


def test_native_routes_share_worker_inventory_without_db_initialization(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    server = make_server(snapshot(), 0, directory=directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            empty = client.get("/api/investigations")
            assert empty.status_code == 200
            assert empty.json()["available"] is False
            assert empty.json()["rows"] == []
            assert client.get("/api/investigations?revision=1").json()["available"] is False
            assert not (directory / "investigations.sqlite3").exists()

            runtime = InvestigationRuntime(directory)
            try:
                record = CeqaRecord(
                    ceqa_key="test:phase5:ceqa:1",
                    title="Synthetic environmental application",
                    county="Riverside",
                    state_clearinghouse_number="2026101000",
                    site=Site(
                        site_key="test:phase5:site",
                        county="Riverside",
                        apn="123-456-789",
                    ),
                    provenance=[
                        Provenance(
                            source_name="Offline synthetic fixture",
                            captured_at=datetime(2026, 10, 16, tzinfo=UTC),
                        )
                    ],
                )
                original = record.model_dump_json(round_trip=True).encode()
                runtime.enqueue_bytes(original, "ceqa")
                assert runtime.process(max_jobs=100)["failed_jobs"] == 0
            finally:
                runtime.close()

            database = directory / "investigations.sqlite3"
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            inventory = client.get("/api/investigations")
            assert inventory.status_code == 200
            data = inventory.json()
            assert data["available"] is True
            assert data["total"] == 1
            assert len(data["rows"]) == 1
            assert data["mapped_on_page"] == 0
            identity = data["rows"][0]["investigation_id"]
            assert data["rows"][0]["source_records"][0]["source_family"] == "ceqa"
            assert data["rows"][0]["assessment"]["commercial_authority_granted"] is False
            dossier_response = client.get("/api/investigations/" + identity)
            assert dossier_response.status_code == 200
            dossier = dossier_response.json()
            assert dossier["investigation"]["project_cluster_id"] == identity
            assert dossier["source_membership"][0]["source_family"] == "ceqa"
            assert dossier["assessment"]["identity_independently_verified"] is False
            assert dossier["assessment"]["commercial_authority_granted"] is False
            assert dossier["source_claimed_points"] == []
            assert client.get("/api/investigations?after=not-a-valid-identity").status_code == 200
            assert client.post("/api/investigations").status_code == 501
            assert client.get("/api/investigations/" + identity + "/bad").status_code != 200
            revision = client.get("/api/investigations?revision=1").json()
            assert revision["available"] is True
            assert revision["event_cursor"] == data["event_cursor"]
            assert "rows" not in revision
            assert len(client.get("/api/investigations?q=environmental").json()["rows"]) == 1
            assert client.get("/api/investigations?q=absent-term").json()["rows"] == []
            assert len(client.get("/api/investigations?source=ceqa").json()["rows"]) == 1
            assert client.get("/api/investigations?source=permit").json()["rows"] == []
            assert len(client.get("/api/investigations?county=Riverside").json()["rows"]) == 1
            assert client.get("/api/investigations?county=Los+Angeles").json()["rows"] == []
            assert len(client.get("/api/investigations?location=unmapped").json()["rows"]) == 1
            assert client.get("/api/investigations?location=mapped").json()["rows"] == []
            assert client.get("/api/investigations?location=invalid").status_code == 409
            assert client.get("/api/investigations?q=a&q=b").status_code == 409
            assert client.get("/api/investigations?revision=1&q=a").status_code == 409
            assert client.get("/api/investigations?q=" + "a" * 256).status_code == 409
            assert hashlib.sha256(database.read_bytes()).hexdigest() == before

            runtime = InvestigationRuntime(directory)
            try:
                changed = record.model_copy(update={"title": "Revised retained application"})
                runtime.enqueue_bytes(changed.model_dump_json(round_trip=True).encode(), "ceqa")
                assert runtime.process(max_jobs=100)["failed_jobs"] == 0
            finally:
                runtime.close()
            updated = client.get("/api/investigations").json()
            assert updated["event_cursor"] > revision["event_cursor"]
            assert updated["total"] == 1
            assert updated["rows"][0]["investigation_id"] == identity
            assert updated["rows"][0]["title"] == "Revised retained application"
    finally:
        server.shutdown()
        server.server_close()
    thread.join()


def test_untrusted_investigation_db_is_not_followed(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    external = tmp_path / "outside.sqlite3"
    external.write_bytes(b"untrusted")
    (directory / "investigations.sqlite3").symlink_to(external)
    server = make_server(snapshot(), 0, directory=directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            assert client.get("/api/investigations").status_code == 409
            assert external.read_bytes() == b"untrusted"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_filtered_inventory_keeps_scan_continuation(tmp_path: Path) -> None:
    from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
    from constructionsight.intelligence.schemas import EvidenceRecord, ProjectCluster
    from constructionsight.storage.database import managed_session
    from constructionsight.storage.intelligence_store import IntelligenceStore

    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            store.upsert_evidence(EvidenceRecord(
                evidence_id="test:paging:evidence", source_name="Synthetic paging fixture",
                record_type="document", evidence_text="Synthetic retained pagination evidence"
            ))
            store.upsert_project_cluster(ProjectCluster(
                project_cluster_id="test:paging:001", project_name="First nonmatching record",
                evidence_record_ids=["test:paging:evidence"]
            ))
            store.upsert_project_cluster(ProjectCluster(
                project_cluster_id="test:paging:002", project_name="Needle beyond first scan",
                evidence_record_ids=["test:paging:evidence"]
            ))
            session.commit()
        with managed_session(runtime.queue.factory) as session:
            query = InvestigationQueryService(IntelligenceStore(session))
            first = query.inventory(limit=1, text="Needle")
            assert first["rows"] == []
            assert first["has_more"] is True
            assert first["scanned_on_page"] == 1
            second = query.inventory(limit=1, text="Needle", after=first["next_cursor"])
            assert second["has_more"] is False
            assert len(second["rows"]) == 1
            assert second["rows"][0]["investigation_id"] == "test:paging:002"
    finally:
        runtime.close()
