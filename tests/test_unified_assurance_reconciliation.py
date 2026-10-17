"""Phase 7: historical safeguards exercised through the new unified runtime and UI.

No source polling, operator authorization, or commercial effects are performed here.
Retained synthetic evidence must stay uncertain, traceable and separate across views.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from constructionsight.command_center_graph import graph_view
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore
from tests.test_investigation_multisource_acceptance import retained_inputs


def _empty_commercial_snapshot() -> dict[str, Any]:
    return {
        "rows": [],
        "captured_at": "2026-10-16T12:00:00+00:00",
        "requests": 0,
        "totals": {"Riverside": 0, "San Bernardino": 0},
        "baseline": True,
        "missing_count": 0,
    }


def test_retained_multisource_investigation_keeps_historical_guards_across_native_views(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    inputs = [
        (kind, record.model_dump_json(round_trip=True).encode())
        for kind, record in retained_inputs()[:3]
    ]
    runtime = InvestigationRuntime(directory)
    try:
        # Exercise the actual shared worker's primary DB connection, not a
        # separate test engine that could conceal missing SQLite FK protection.
        with managed_session(runtime.queue.factory) as session:
            assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        for kind, original in inputs:
            runtime.enqueue_bytes(original, kind)
        assert runtime.process(max_jobs=150)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            inventory = InvestigationQueryService(store).inventory(limit=20)
            assert inventory["total"] == 3
            ids = {item["investigation_id"] for item in inventory["rows"]}
            assert len(ids) == 3
            assert {row["source_records"][0]["source_family"] for row in inventory["rows"]} == {
                "ceqa", "planning", "permit"
            }
            assert all(
                len(row["source_records"]) == 1
                and row["assessment"]["commercial_authority_granted"] is False
                and row["assessment"]["identity_independently_verified"] is False
                for row in inventory["rows"]
            )
            event_cursor = store.runtime_event_cursor()
    finally:
        runtime.close()

    for _kind, original in inputs:
        digest = hashlib.sha256(original).hexdigest()
        assert (directory / "investigation-inputs" / digest).read_bytes() == original

    initial = graph_view(directory)
    assert set(initial["roots"]) == ids
    assert initial["commercial_authority_granted"] is False
    assert all(node["identity_verified"] is False for node in initial["nodes"])
    assert all(edge["identity_verified"] is False for edge in initial["edges"])
    assert initial["cursor"] == event_cursor

    server = make_server(_empty_commercial_snapshot(), 0, directory=directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            database = directory / "investigations.sqlite3"
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            native = client.get("/api/investigations")
            assert native.status_code == 200
            assert {row["investigation_id"] for row in native.json()["rows"]} == ids
            visible_graph = client.get("/api/investigation-graph")
            assert visible_graph.status_code == 200
            assert set(visible_graph.json()["roots"]) == ids
            assert client.get("/api/leads").json()["rows"] == []
            for identity in ids:
                response = client.get("/api/investigations/" + identity)
                assert response.status_code == 200
                dossier = response.json()
                assert dossier["investigation"]["project_cluster_id"] == identity
                assert len(dossier["source_observations"]) == 1
                assert dossier["assessment"]["commercial_authority_granted"] is False
                assert dossier["assessment"]["identity_independently_verified"] is False
                evidence_id = dossier["source_observations"][0]["evidence"]["evidence_id"]
                inspected = client.get(
                    "/api/investigation-graph/evidence", params={"id": evidence_id}
                )
                assert inspected.status_code == 200
                assert inspected.json()["evidence"]["evidence_id"] == evidence_id
            assert hashlib.sha256(database.read_bytes()).hexdigest() == before

            # A new worker lifetime must not manufacture new evidence on replay.
            runtime = InvestigationRuntime(directory)
            try:
                for kind, original in inputs:
                    runtime.enqueue_bytes(original, kind)
                idle = runtime.process(max_jobs=150)
                assert idle["processed_jobs"] == idle["failed_jobs"] == 0
                with managed_session(runtime.queue.factory) as session:
                    store = IntelligenceStore(session)
                    assert store.runtime_event_cursor() == event_cursor
                    assert InvestigationQueryService(store).inventory()["total"] == 3
            finally:
                runtime.close()
            after = client.get("/api/investigation-graph").json()
            assert set(after["roots"]) == ids
            assert after["cursor"] == event_cursor
            assert client.get("/api/leads").json()["rows"] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
