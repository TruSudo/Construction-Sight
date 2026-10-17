"""Phase 8 native parity: reuse the preserved operator source services read-only."""

from __future__ import annotations

import hashlib
import threading
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from constructionsight.live_command_center import make_server
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_dashboard import _record


def _native(directory: Path, operator_database: Path | None = None):
    server = make_server(snapshot(), 0, directory, operator_database=operator_database)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    return server, worker


def test_unconfigured_legacy_source_does_not_create_or_fake_zero_results(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    server, worker = _native(directory)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            for endpoint in (
                "/api/source-registry",
                "/api/source-revision",
                "/api/source-review-queue",
                "/api/source-watchlist",
                "/api/workflow-summary",
                "/api/workflows",
                "/api/results",
                "/api/source-entity-index",
                "/api/source-entity-neighborhood?entity_key=fixture:party",
                "/api/source-timeline",
                "/api/source-footprint",
                "/api/source-capture-queue",
                "/api/source-ingestion-inbox",
            ):
                response = client.get(endpoint)
                assert response.status_code == 200
                payload = response.json()
                assert payload["available"] is False
                assert payload["configured"] is False
                assert payload["network_collection_enabled"] is False
                assert "total" not in payload
            assert client.get("/api/source-registry?extra=1").status_code == 409
            assert client.get("/api/source-review-queue?kind=wrong").status_code == 409
            assert client.get("/api/parcel-candidates?kind=all&record_id=x").status_code == 409
            assert not (directory / "constructionsight.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_existing_legacy_source_db_is_reused_by_native_without_mutation(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(_record(
                "phase8:record", title="Synthetic retained review",
                received_date=date(2026, 10, 10), posted_date=date(2026, 10, 11),
            ))
    engine.dispose()
    original = hashlib.sha256(database.read_bytes()).hexdigest()
    server, worker = _native(tmp_path / "private", operator_database=database)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            registry = client.get("/api/source-registry")
            assert registry.status_code == 200
            assert registry.json()["available"] is True
            assert registry.json()["read_only"] is True
            assert registry.json()["network_collection_enabled"] is False
            watch = client.get("/api/source-watchlist")
            assert watch.status_code == 200
            assert watch.json()["available"] is True
            assert watch.json()["total"] == 0
            summary = client.get("/api/workflow-summary")
            assert summary.status_code == 200
            assert summary.json()["total"] == 0
            workflows = client.get("/api/workflows?limit=25&offset=0")
            assert workflows.status_code == 200
            assert workflows.json()["leads"] == []
            results = client.get("/api/results?limit=25&offset=0")
            assert results.status_code == 200
            assert results.json()["results"] == []
            assert client.get("/api/workflow-summary?unexpected=1").status_code == 409
            assert client.get("/api/results?limit=100").status_code == 409
            revision = client.get("/api/source-revision")
            assert revision.status_code == 200
            assert revision.json()["source_families"]["ceqa"]["record_count"] == 1
            queue = client.get("/api/source-review-queue?kind=ceqa&limit=10")
            assert queue.status_code == 200, queue.text
            payload = queue.json()
            assert payload["available"] is True
            assert payload["total_source_records"] == 1
            item = payload["items"][0]
            assert item["record_id"] == "phase8:record"
            assert item["outreach_authorized"] is False
            selector = {"kind": "ceqa", "record_id": item["record_id"]}
            detail = client.get("/api/candidate-preview", params=selector)
            parcel = client.get("/api/parcel-candidates", params=selector)
            assert detail.status_code == 200, detail.text
            assert detail.json()["normalized_source_sha256"] == item[
                "normalized_source_sha256"
            ]
            assert parcel.status_code == 200, parcel.text
            assert parcel.json()["source_record_id"] == "phase8:record"
            assert client.get(
                "/api/candidate-preview?kind=ceqa&record_id=phase8:record&extra=1"
            ).status_code == 409
            assert client.get(
                "/api/source-review-queue?limit=100"
            ).status_code == 409
            assert client.get(
                "/api/source-review-queue?q=x&q=y"
            ).status_code == 409
            entities = client.get("/api/source-entity-index?kind=ceqa&county=San%20Bernardino")
            assert entities.status_code == 200, entities.text
            assert entities.json()["entries"][0]["entity_key"] == "fixture:party"
            assert entities.json()["entries"][0]["matching_records_in_scan"] == 1
            neighborhood = client.get(
                "/api/source-entity-neighborhood",
                params={"kind": "ceqa", "entity_key": "fixture:party"},
            )
            assert neighborhood.status_code == 200, neighborhood.text
            assert neighborhood.json()["records"][0]["record_id"] == "phase8:record"
            timeline = client.get("/api/source-timeline?kind=ceqa")
            assert timeline.status_code == 200, timeline.text
            assert {e["event_kind"] for e in timeline.json()["events"]} == {
                "ceqa_received", "ceqa_posted"
            }
            assert timeline.json()["events"][0]["recorded_date"] == "2026-10-11"
            footprint = client.get("/api/source-footprint?kind=ceqa")
            assert footprint.status_code == 200, footprint.text
            assert footprint.json()["mapped_in_scan"] == 1
            assert footprint.json()["points"][0]["record_id"] == "phase8:record"
            assert client.get("/api/source-entity-neighborhood").status_code == 409
            assert client.get("/api/source-entity-index?role=nope").status_code == 409
            assert client.get("/api/source-timeline?entity_key=%00bad").status_code == 409
            assert client.get("/api/source-footprint?unexpected=1").status_code == 409
            capture = client.get("/api/source-capture-queue")
            inbox = client.get("/api/source-ingestion-inbox")
            assert capture.status_code == 200
            assert inbox.status_code == 200
            assert capture.json()["configured"] is False
            assert inbox.json()["configured"] is False
            assert capture.json()["read_only"] is True
            assert inbox.json()["network_executed"] is False
            assert client.get("/api/source-capture-queue?other=1").status_code == 409
            assert client.get("/api/source-ingestion-inbox?kind=ceqa").status_code == 409
            assert client.post("/api/source-entity-index", json={}).status_code == 501
            assert client.post("/api/source-registry", json={}).status_code == 501
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == original



def test_original_ceqa_artifacts_are_inspected_without_ingesting_or_mutating(
    tmp_path: Path,
) -> None:
    from tests.test_operator_capture_queue import _payload
    from tests.test_operator_ingestion_inbox import _write_artifacts

    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    listing, review = _write_artifacts(tmp_path)
    capture = tmp_path / "capture.json"
    capture.write_text(__import__("json").dumps(_payload()), encoding="utf-8")
    paths = (database, listing, review, capture)
    original = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    server = make_server(
        snapshot(), 0, tmp_path / "native",
        operator_database=database,
        operator_capture_queue=capture,
        operator_ceqanet_listing=listing,
        operator_ceqanet_review_queue=review,
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            capture_response = client.get("/api/source-capture-queue")
            assert capture_response.status_code == 200, capture_response.text
            assert capture_response.json()["available"] is True
            assert capture_response.json()["candidate_count"] == 1
            assert capture_response.json()["candidates"][0]["sch_number"] == "2026012345"
            inbox = client.get("/api/source-ingestion-inbox")
            assert inbox.status_code == 200, inbox.text
            assert inbox.json()["available"] is True
            assert inbox.json()["pending_capture_count"] == 1
            assert inbox.json()["next_pending_sch"] == "2026030377"
            for result in (capture_response.json(), inbox.json()):
                assert result["read_only"] is True
                assert result["network_executed"] is False
                assert result["persistence_mutated"] is False
                assert result["commercial_leads_created"] is False
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == original



def test_native_refuses_symlinked_or_missing_operator_source_db(tmp_path: Path) -> None:
    target = tmp_path / "real.sqlite3"
    target.write_bytes(b"not a database")
    link = tmp_path / "linked.sqlite3"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="existing regular file"):
        make_server(snapshot(), 0, tmp_path / "private", operator_database=link)
    with pytest.raises(ValueError, match="existing regular file"):
        make_server(
            snapshot(), 0, tmp_path / "private", operator_database=tmp_path / "missing.sqlite3"
        )
    with pytest.raises(ValueError, match="must be paired"):
        make_server(
            snapshot(), 0, tmp_path / "private", operator_database=target,
            operator_ceqanet_listing=tmp_path / "listing.json",
        )
    with pytest.raises(ValueError, match="require an existing operator database"):
        make_server(
            snapshot(), 0, tmp_path / "private",
            operator_capture_queue=tmp_path / "capture.json",
        )
    with pytest.raises(ValueError, match="demo/parity"):
        make_server(
            {**snapshot(), "demo": True}, 0, operator_database=target
        )
