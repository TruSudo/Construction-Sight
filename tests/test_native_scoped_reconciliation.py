"""Reviewed original-source pages converge through the existing durable worker."""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from constructionsight import command_center_legacy_reconciliation as replay
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.command_center_investigations import investigation_view
from constructionsight.intelligence.investigation_service import InvestigationService
from constructionsight.intelligence.investigation_sources import from_domain
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from constructionsight.permit_models import PermitRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
)
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.intelligence_store import IntelligenceStore
from tests.test_command_center_investigation_bridge import snapshot


def _sources(tmp_path: Path) -> tuple[Path, Path, list[CeqaRecord | PermitRecord]]:
    database = tmp_path / "original.sqlite3"
    directory = tmp_path / "native"
    provenance = [Provenance(
        source_name="Synthetic scoped-replay fixture", evidence_text="Not a real project",
        captured_at=datetime(2026, 10, 17, tzinfo=UTC),
    )]
    site = Site(site_key="synthetic:shared-parcel", county="Riverside", apn="000-111-222")
    records: list[CeqaRecord | PermitRecord] = [
        CeqaRecord(ceqa_key=f"scoped:ceqa:{i}", title=f"Scoped source {i}",
                   county="Riverside", site=site, provenance=provenance)
        for i in range(4)
    ] + [
        PermitRecord(permit_key=f"scoped:permit:{i}", permit_number=f"Scoped permit {i}",
                     jurisdiction="Synthetic local agency", county="Riverside",
                     site=site, provenance=provenance)
        for i in range(3)
    ]
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        for record in records:
            if isinstance(record, CeqaRecord):
                CeqaStore(session).upsert(record)
            else:
                PermitStore(session).upsert(record)
        CeqaStore(session).upsert(CeqaRecord(
            ceqa_key="outside:county", title="Scoped outside county",
            county="San Bernardino", provenance=provenance,
        ))
    engine.dispose()
    return database, directory, records


def _body(plan: dict[str, Any]) -> dict[str, Any]:
    return {"scope": plan["scope"], "expected_plan_sha256": plan["plan_sha256"],
            "caller_confirmation": True,
            "review_reason": "Reviewed this exact retained source page for worker replay only."}


def test_complete_filtered_scope_replays_in_bounded_pages_across_worker_restarts(
    tmp_path: Path,
) -> None:
    original, directory, records = _sources(tmp_path)
    before = original.read_bytes()
    scope = {"county": "Riverside", "query": "Scoped", "limit": 3}
    all_jobs = []
    offset = 0
    while True:
        plan = replay.preview_legacy_reconciliation_batch(
            directory, original, {**scope, "offset": offset}
        )
        assert plan["total_source_records"] == 7
        assert 0 < plan["returned"] <= 3
        assert plan["eligible_count"] == plan["returned"]
        assert plan["commercial_authority_granted"] is False
        if offset == 0:
            assert not (directory / "investigations.sqlite3").exists()
        queued = replay.enqueue_legacy_reconciliation_batch(directory, original, _body(plan))
        repeated = replay.enqueue_legacy_reconciliation_batch(directory, original, _body(plan))
        assert queued == repeated
        assert queued["batch_approval_audit_event_id"]
        all_jobs.extend(queued["jobs"])
        runtime = InvestigationRuntime(directory)
        try:
            assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        finally:
            runtime.close()
        checked = replay.preview_legacy_reconciliation_batch(
            directory, original, {**scope, "offset": offset}
        )
        assert checked["eligible_count"] == 0
        assert checked["already_retained_count"] == checked["returned"]
        if not queued["has_more"]:
            break
        assert queued["next_offset"] > offset
        offset = queued["next_offset"]
    assert len(all_jobs) == len(records) == 7
    assert len({item["job_id"] for item in all_jobs}) == 7
    inventory = investigation_view(directory)
    assert inventory["total"] == 7  # Common APN is not project identity.
    assert all(not row["assessment"]["commercial_authority_granted"] for row in inventory["rows"])
    for job in all_jobs:
        audit = replay.original_source_replay_audit(directory, job_id=job["job_id"])
        assert audit["job_status"] == "completed"
        assert audit["approval"]["source_sha256"] == job["original_source"]["source_sha256"]
    runtime = InvestigationRuntime(directory)
    try:
        assert runtime.process(max_jobs=100)["processed_jobs"] == 0
    finally:
        runtime.close()
    assert original.read_bytes() == before


def test_scoped_replay_holds_conflicts_and_skips_exact_current_observations(tmp_path: Path) -> None:
    original, directory, records = _sources(tmp_path)
    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            service = InvestigationService(IntelligenceStore(session))
            service.ingest(from_domain(records[0]))
            service.ingest(from_domain(records[1].model_copy(
                update={"title": "Different evidence"}
            )))
    finally:
        runtime.close()
    plan = replay.preview_legacy_reconciliation_batch(directory, original, {"county": "Riverside"})
    assert plan["already_retained_count"] == plan["requires_review_count"] == 1
    assert plan["eligible_count"] == 5
    receipt = replay.enqueue_legacy_reconciliation_batch(directory, original, _body(plan))
    assert receipt["queued_count"] == 5
    assert all(job["original_source"]["record_id"] not in {"scoped:ceqa:0", "scoped:ceqa:1"}
               for job in receipt["jobs"])
    runtime = InvestigationRuntime(directory)
    try:
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()
    assert replay.preview_legacy_reconciliation_batch(
        directory, original, {"county": "Riverside"}
    )["requires_review_count"] == 1


def test_scoped_replay_rejects_stale_original_or_native_state_and_invalid_confirmation(
    tmp_path: Path,
) -> None:
    original, directory, records = _sources(tmp_path)
    plan = replay.preview_legacy_reconciliation_batch(directory, original, {})
    for confirmation in (False, 1, "true", None):
        with pytest.raises(ValueError):
            replay.enqueue_legacy_reconciliation_batch(
                directory, original, {**_body(plan), "caller_confirmation": confirmation}
            )
    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            InvestigationService(IntelligenceStore(session)).ingest(from_domain(records[0]))
    finally:
        runtime.close()
    with pytest.raises(ValueError, match="changed"):
        replay.enqueue_legacy_reconciliation_batch(directory, original, _body(plan))
    plan = replay.preview_legacy_reconciliation_batch(directory, original, {})
    engine = create_database_engine(f"sqlite:///{original}")
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(records[0].model_copy(update={"title": "Changed original"}))
    engine.dispose()
    with pytest.raises(ValueError, match="changed"):
        replay.enqueue_legacy_reconciliation_batch(directory, original, _body(plan))
    runtime = InvestigationRuntime(directory)
    try:
        assert runtime.queue.list_jobs() == []
    finally:
        runtime.close()


def test_scoped_approval_and_all_jobs_rollback_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original, directory, _ = _sources(tmp_path)
    plan = replay.preview_legacy_reconciliation_batch(directory, original, {})
    add = IntelligenceStore.add_runtime_event
    count = 0

    def fail_second(self: IntelligenceStore, event: Any) -> Any:
        nonlocal count
        if event.source_service == "original_source_replay_approval":
            count += 1
            if count == 2:
                raise ValueError("injected second approval failure")
        return add(self, event)

    monkeypatch.setattr(IntelligenceStore, "add_runtime_event", fail_second)
    with pytest.raises(ValueError, match="second approval"):
        replay.enqueue_legacy_reconciliation_batch(directory, original, _body(plan))
    runtime = InvestigationRuntime(directory)
    try:
        assert runtime.queue.list_jobs() == []
        with managed_session(runtime.queue.factory) as session:
            assert IntelligenceStore(session).runtime_event_cursor() == 0
    finally:
        runtime.close()


def test_scoped_replay_is_bounded_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original, directory, _ = _sources(tmp_path)
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    for scope in ({"limit": 26}, {"limit": True}, {"offset": -1}, {"county": "Other"},
                  {"unknown": True}, {"query": "x" * 201}):
        with pytest.raises(ValueError):
            replay.preview_legacy_reconciliation_batch(directory, original, scope)
    monkeypatch.setattr(replay, "MAX_INPUT_BYTES", 1)
    with pytest.raises(ValueError, match="size"):
        replay.preview_legacy_reconciliation_batch(directory, original, {})
    assert not directory.exists()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


def test_scoped_replay_rechecks_native_eligibility_under_the_queue_write_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original, directory, records = _sources(tmp_path)
    plan = replay.preview_legacy_reconciliation_batch(directory, original, {})
    queue = replay._queue_sources

    def race(*args: Any, **kwargs: Any) -> Any:
        runtime = InvestigationRuntime(directory)
        try:
            with managed_session(runtime.queue.factory) as session:
                InvestigationService(IntelligenceStore(session)).ingest(from_domain(records[-1]))
        finally:
            runtime.close()
        return queue(*args, **kwargs)

    monkeypatch.setattr(replay, "_queue_sources", race)
    with pytest.raises(ValueError, match="source changed in native"):
        replay.enqueue_legacy_reconciliation_batch(directory, original, _body(plan))
    runtime = InvestigationRuntime(directory)
    try:
        assert runtime.queue.list_jobs() == []
    finally:
        runtime.close()


def test_scoped_http_requires_exact_origin_confirmation_and_bounded_query(tmp_path: Path) -> None:
    original, directory, _ = _sources(tmp_path)
    original_bytes = original.read_bytes()
    server = make_server(snapshot(), 0, directory, operator_database=original)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as client:
            path = "/api/source-reconciliation-scope"
            for query in ("kind=ceqa&kind=permit", "limit=26", "unknown=1", "offset=-1"):
                assert client.get(path + "?" + query).status_code == 409
            response = client.get(path, params={"county": "Riverside", "limit": "3"})
            assert response.status_code == 200, response.text
            plan = response.json()
            assert plan["eligible_count"] == 3
            assert not (directory / "investigations.sqlite3").exists()
            body = _body(plan)
            post = path + "-queue"
            assert client.post(post, json=body).status_code == 403
            assert client.post(
                post, json=body, headers={"Origin": "https://other.test"}
            ).status_code == 403
            for bad in ({**body, "caller_confirmation": 1},
                        {**body, "expected_plan_sha256": "0" * 64},
                        {**body, "extra": "permit"}):
                assert client.post(post, json=bad, headers={"Origin": base}).status_code == 400
            assert client.post(post + "?extra=1", json=body,
                               headers={"Origin": base}).status_code == 400
            accepted = client.post(post, json=body, headers={"Origin": base})
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["queued_count"] == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert original.read_bytes() == original_bytes


def test_original_source_database_cannot_alias_native_store(tmp_path: Path) -> None:
    original, directory, _ = _sources(tmp_path)
    directory.mkdir(mode=0o700)
    (directory / "investigations.sqlite3").hardlink_to(original)
    before = original.read_bytes()
    with pytest.raises(ValueError, match="separate"):
        replay.preview_legacy_reconciliation_batch(directory, original, {})
    with pytest.raises(ValueError, match="separate"):
        replay.preview_legacy_reconciliation(
            directory, original, kind="ceqa", record_id="scoped:ceqa:0"
        )
    assert original.read_bytes() == before
