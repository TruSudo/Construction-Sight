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
            assert hashlib.sha256(database.read_bytes()).hexdigest() == before
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
