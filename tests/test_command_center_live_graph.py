"""Phase 6 graph reads must expose committed state without creating another graph store."""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.command_center_graph import graph_view
from constructionsight.entity_models import Entity
from constructionsight.intelligence.schemas import (
    RelationshipStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from constructionsight.provenance import Provenance
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore


def _record(title: str = "Synthetic live graph project") -> CeqaRecord:
    return CeqaRecord(
        ceqa_key="synthetic:live-graph:ceqa",
        title=title,
        county="Riverside",
        entities=[
            Entity(
                entity_key="synthetic:live-graph:developer",
                name="Synthetic graph developer",
                role="developer",
            )
        ],
        provenance=[
            Provenance(
                source_name="Synthetic graph fixture",
                captured_at=datetime(2026, 10, 16, tzinfo=UTC),
            )
        ],
    )


def _ingest(directory: Path, title: str = "Synthetic live graph project") -> None:
    runtime = InvestigationRuntime(directory)
    try:
        runtime.enqueue_bytes(_record(title).model_dump_json(round_trip=True).encode(), "ceqa")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()


def test_graph_absent_store_is_not_initialized(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    assert graph_view(directory)["available"] is False
    assert not (directory / "investigations.sqlite3").exists()
    external = tmp_path / "external"
    external.write_bytes(b"untrusted")
    (directory / "investigations.sqlite3").symlink_to(external)
    import pytest

    with pytest.raises(ValueError):
        graph_view(directory)
    assert external.read_bytes() == b"untrusted"


def test_graph_snapshot_and_event_anchor_recover_without_duplicate_nodes(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    _ingest(directory)
    before = hashlib.sha256((directory / "investigations.sqlite3").read_bytes()).hexdigest()
    initial = graph_view(directory)
    assert initial["available"] is True
    ids = {node["id"] for node in initial["nodes"]}
    assert len(ids) == len(initial["nodes"])
    assert all(edge["source"] in ids and edge["target"] in ids for edge in initial["edges"])
    assert any(node["label"] == "Synthetic graph developer" for node in initial["nodes"])
    assert all(node["identity_verified"] is False for node in initial["nodes"])
    assert initial["commercial_authority_granted"] is False
    assert graph_view(directory)["nodes"] == initial["nodes"]
    idle = graph_view(directory, mode="events", after=initial["cursor"], anchor=initial["anchor"])
    assert idle["events"] == []
    assert hashlib.sha256((directory / "investigations.sqlite3").read_bytes()).hexdigest() == before

    _ingest(directory, "Synthetic live graph revision")
    changes = graph_view(
        directory, mode="events", after=initial["cursor"], anchor=initial["anchor"]
    )
    assert changes["cursor"] > initial["cursor"]
    assert changes["reset_required"] is False
    assert changes["events"]
    assert all("payload" not in event for event in changes["events"])
    updated = graph_view(directory)
    assert {n["id"] for n in updated["nodes"] if n["kind"] == "investigation"} == {
        n["id"] for n in initial["nodes"] if n["kind"] == "investigation"
    }
    assert any(n["label"] == "Synthetic live graph revision" for n in updated["nodes"])
    assert (
        graph_view(directory, mode="events", after=changes["cursor"], anchor=changes["anchor"])[
            "events"
        ]
        == []
    )
    assert (
        graph_view(directory, mode="events", after=initial["cursor"], anchor="wrong-lineage")[
            "reset_required"
        ]
        is True
    )
    assert graph_view(directory, mode="events", after=updated["cursor"] + 1)["reset_required"]


def test_graph_event_pages_and_rejected_edges(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    _ingest(directory)
    initial = graph_view(directory)
    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            relation = next(
                r for r in store.list_relationships() if r.predicate == "source_claimed_developer"
            )
            store.upsert_relationship(
                relation.model_copy(update={"relationship_status": RelationshipStatus.REJECTED})
            )
            for index in range(270):
                store.add_runtime_event(
                    RuntimeEvent(
                        event_id=f"synthetic:graph-event:{index}",
                        event_type=RuntimeEventType.EXPORT_CREATED,
                        source_service="synthetic_graph_paging",
                        message="Synthetic retained event pagination fixture",
                    )
                )
            session.commit()
    finally:
        runtime.close()
    current = graph_view(directory)
    assert relation.relationship_id not in {e["id"] for e in current["edges"]}
    first = graph_view(directory, mode="events", after=initial["cursor"], anchor=initial["anchor"])
    assert len(first["events"]) == 250
    assert first["has_more"] is True
    second = graph_view(directory, mode="events", after=first["cursor"], anchor=first["anchor"])
    assert second["has_more"] is False
    assert len({e["event_id"] for e in first["events"] + second["events"]}) == (
        len(first["events"]) + len(second["events"])
    )


def test_native_graph_http_and_uncommitted_state(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    _ingest(directory)
    snapshot: dict[str, Any] = {
        "rows": [],
        "captured_at": "2026-10-16T12:00:00+00:00",
        "requests": 0,
        "totals": {"Riverside": 0},
        "baseline": True,
        "missing_count": 0,
    }
    server = make_server(snapshot, 0, directory=directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    runtime = InvestigationRuntime(directory)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            graph = client.get("/api/investigation-graph").json()
            root = graph["roots"][0]
            assert client.get("/api/investigation-graph?depth=0").status_code == 409
            assert client.get("/api/investigation-graph/events?after=-1").status_code == 409
            assert client.get("/api/investigation-graph?root=a&root=b").status_code == 409
            assert client.post("/api/investigation-graph").status_code == 501
            artifact_id = next(n["id"] for n in graph["nodes"] if n["kind"] == "evidence")
            artifact = client.get("/api/investigation-graph/evidence", params={"id": artifact_id})
            assert artifact.json()["evidence"]["evidence_id"] == artifact_id
            assert artifact.json()["evidence"]["content_hash"]
            with managed_session(runtime.queue.factory) as session:
                store = IntelligenceStore(session)
                original = store.get_project_cluster(root)
                assert original is not None
                store.upsert_project_cluster(
                    original.model_copy(update={"project_name": "UNCOMMITTED — MUST NEVER APPEAR"})
                )
                observed = client.get("/api/investigation-graph", params={"root": root}).json()
                assert all("UNCOMMITTED" not in node["label"] for node in observed["nodes"])
                session.rollback()
    finally:
        runtime.close()
        server.shutdown()
        server.server_close()
        thread.join()
