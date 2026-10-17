"""Phase 8 native parity: reuse the preserved operator source services read-only."""

from __future__ import annotations

import hashlib
import threading
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
        CeqaStore(session).upsert(_record("phase8:record", title="Synthetic retained review"))
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
            assert client.post("/api/source-registry", json={}).status_code == 501
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == original


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
    with pytest.raises(ValueError, match="demo/parity"):
        make_server(
            {**snapshot(), "demo": True}, 0, operator_database=target
        )
