"""Reviewed original revisions reach the same engine without replacing history."""

from __future__ import annotations

import threading
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

import constructionsight.effect_consumption as effects
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.command_center_legacy_reconciliation import (
    enqueue_legacy_reconciliation,
    original_source_replay_audit,
    preview_legacy_reconciliation,
    preview_legacy_reconciliation_batch,
)
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.investigation_review_service import InvestigationReviewService
from constructionsight.intelligence.investigation_service import InvestigationService
from constructionsight.intelligence.investigation_sources import from_domain
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.live_command_center import make_server
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.database import create_database_engine, managed_session
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.operator_read_store import create_operator_read_engine
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_native_scoped_reconciliation import _sources


def _body(preview: dict[str, Any], *, revision: bool = False) -> dict[str, Any]:
    return {
        "kind": preview["original_source"]["kind"],
        "record_id": preview["original_source"]["record_id"],
        "expected_source_sha256": preview["original_source"]["source_sha256"],
        "expected_native_evidence_id": preview["native_evidence_id"],
        "action": "retain_revision" if revision else "retain_missing",
        "caller_confirmation": True,
        "review_reason": "Reviewed this exact original source and current native evidence.",
    }


def _store_original(database: Path, record: CeqaRecord | PermitRecord) -> None:
    engine = create_database_engine(f"sqlite:///{database}")
    try:
        with Session(engine) as session, session.begin():
            if isinstance(record, CeqaRecord):
                CeqaStore(session).upsert(record)
            else:
                PermitStore(session).upsert(record)
    finally:
        engine.dispose()


def _changed(record: CeqaRecord | PermitRecord, *, days: int = 1) -> CeqaRecord | PermitRecord:
    return record.model_copy(update={
        "title" if isinstance(record, CeqaRecord) else "permit_number": "Revised original source",
        "provenance": [item.model_copy(update={
            "captured_at": item.captured_at + timedelta(days=days),
        }) for item in record.provenance],
    })


def _setup(tmp_path: Path, kind: str = "ceqa"):
    original, directory, records = _sources(tmp_path)
    record = records[0 if kind == "ceqa" else 4]
    identity = record.ceqa_key if isinstance(record, CeqaRecord) else record.permit_key
    initial = preview_legacy_reconciliation(directory, original, kind=kind, record_id=identity)
    receipt = enqueue_legacy_reconciliation(directory, original, _body(initial))
    runtime = InvestigationRuntime(directory)
    try:
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
    finally:
        runtime.close()
    return original, directory, record, identity, receipt


@pytest.mark.parametrize("kind", ["ceqa", "permit"])
def test_reviewed_revision_updates_same_investigation_preserving_old_approval_and_evidence(
    tmp_path: Path, kind: str,
) -> None:
    original, directory, old, identity, original_job = _setup(tmp_path, kind)
    current = preview_legacy_reconciliation(directory, original, kind=kind, record_id=identity)
    updated = _changed(old)
    _store_original(original, updated)
    original_bytes = original.read_bytes()
    preview = preview_legacy_reconciliation(directory, original, kind=kind, record_id=identity)
    assert preview["replay_eligible"] is False
    assert preview["revision_replay_eligible"] is True
    assert preview["native_evidence_id"] == current["native_evidence_id"]
    assert preview_legacy_reconciliation_batch(
        directory, original, {"kind": kind, "query": "Revised original"},
    )["requires_review_count"] == 1  # Page approval never updates a conflicting observation.
    with pytest.raises(ValueError, match="already present or contradictory"):
        enqueue_legacy_reconciliation(directory, original, _body(preview))
    receipt = enqueue_legacy_reconciliation(directory, original, _body(preview, revision=True))
    assert receipt == enqueue_legacy_reconciliation(
        directory, original, _body(preview, revision=True),
    )
    assert receipt["previous_native_evidence_id"] == current["native_evidence_id"]
    queued = original_source_replay_audit(directory, job_id=receipt["job_id"])
    assert queued["approval"]["previous_evidence_id"] == current["native_evidence_id"]
    assert "previous_evidence_id" not in original_source_replay_audit(
        directory, job_id=original_job["job_id"],
    )["approval"]
    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            assert InvestigationService(store).current_observation(
                preview["source_entity_id"],
            ).evidence.evidence_id == current["native_evidence_id"]
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            assert InvestigationService(store).current_observation(
                preview["source_entity_id"],
            ).evidence.evidence_id == preview["expected_evidence_id"]
            assert store.get_evidence(current["native_evidence_id"]) is not None
            assert store.get_evidence(preview["expected_evidence_id"]) is not None
            inventory = InvestigationQueryService(store).inventory()
            assert inventory["total"] == 1
            row = inventory["rows"][0]
            assert row["investigation_id"] == current["canonical_investigation_id"]
            assert row["assessment"]["identity_independently_verified"] is False
            assert row["assessment"]["commercial_authority_granted"] is False
        assert runtime.process(max_jobs=100)["processed_jobs"] == 0
    finally:
        runtime.close()
    checked = preview_legacy_reconciliation(directory, original, kind=kind, record_id=identity)
    assert checked["native_state"] == "exact_observation_already_retained"
    assert checked["revision_replay_eligible"] is False
    assert original_source_replay_audit(directory, job_id=receipt["job_id"])["job_status"] == (
        "completed"
    )
    assert original.read_bytes() == original_bytes


def test_revision_worker_rejects_intervening_native_evidence_without_losing_either_history(
    tmp_path: Path,
) -> None:
    original, directory, old, identity, _ = _setup(tmp_path)
    updated = _changed(old)
    _store_original(original, updated)
    preview = preview_legacy_reconciliation(directory, original, kind="ceqa", record_id=identity)
    receipt = enqueue_legacy_reconciliation(directory, original, _body(preview, revision=True))
    newer = _changed(old, days=2)
    runtime = InvestigationRuntime(directory)
    try:
        with managed_session(runtime.queue.factory) as session:
            InvestigationService(IntelligenceStore(session)).ingest(from_domain(newer))
        outcome = runtime.process(max_jobs=100)
        assert outcome["failed_jobs"] == 1
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            assert InvestigationService(store).current_observation(
                preview["source_entity_id"],
            ).evidence.evidence_id == from_domain(newer).evidence.evidence_id
            assert store.get_evidence(preview["expected_evidence_id"]) is None
            assert store.get_evidence(from_domain(old).evidence.evidence_id) is not None
    finally:
        runtime.close()
    audit = original_source_replay_audit(directory, job_id=receipt["job_id"])
    assert audit["job_status"] == "failed"


@pytest.mark.parametrize("restore_old", [True, False])
def test_older_or_previously_retained_original_is_not_a_current_revision(
    tmp_path: Path, restore_old: bool,
) -> None:
    original, directory, old, identity, _ = _setup(tmp_path)
    if restore_old:
        newer = _changed(old, days=2)
        runtime = InvestigationRuntime(directory)
        try:
            runtime.enqueue_bytes(newer.model_dump_json(round_trip=True).encode(), "ceqa")
            assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        finally:
            runtime.close()
    else:
        _store_original(original, _changed(old, days=-1))
    preview = preview_legacy_reconciliation(directory, original, kind="ceqa", record_id=identity)
    assert preview["revision_replay_eligible"] is False
    with pytest.raises(ValueError, match="historical"):
        enqueue_legacy_reconciliation(directory, original, _body(preview, revision=True))


def test_original_revision_reuses_relationship_reassessment_in_the_shared_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(effects, "_CONSUMPTION_DATABASE_PATH", tmp_path / "review-effects.sqlite3")
    original, directory, old, identity, _ = _setup(tmp_path)
    # Reuse the other independent source already retained in the original database.
    engine = create_operator_read_engine(original)
    with Session(engine) as session:
        permit = PermitStore(session).get("scoped:permit:0")
    engine.dispose()
    assert permit is not None
    runtime = InvestigationRuntime(directory)
    try:
        runtime.enqueue_bytes(permit.model_dump_json(round_trip=True).encode(), "permit")
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            relation = next(r for r in store.list_relationships()
                            if r.predicate == "possible_same_project_requires_review")
        reviewer = InvestigationReviewService(runtime.engine)
        review = reviewer.preview(relation.relationship_id)
        target = review["target_choices"][0]
        reviewer.review(
            relation.relationship_id, decision="associate", target_id=target,
            expected_identity=review["expected_identity"],
            reason="Synthetic exact retained source context association only.",
            caller_confirmation=True, operator_id="operator:original-revision-test",
        )
        _store_original(original, _changed(old))
        preview = preview_legacy_reconciliation(
            directory, original, kind="ceqa", record_id=identity,
        )
        enqueue_legacy_reconciliation(directory, original, _body(preview, revision=True))
        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
        with managed_session(runtime.queue.factory) as session:
            store = IntelligenceStore(session)
            query = InvestigationQueryService(store)
            dossier = query.dossier(target)
            assert dossier["cross_source_investigation"]["requires_association_reassessment"]
            assert dossier["pending_association_reviews"]
            assert dossier["assessment"]["identity_independently_verified"] is False
            assert dossier["assessment"]["commercial_authority_granted"] is False
            # Preserve the operator's recorded context rather than silently
            # rewriting it; the same engine explicitly calls for reassessment.
            assert query.inventory()["total"] == 1
    finally:
        runtime.close()


def test_revision_http_requires_explicit_action_exact_evidence_and_same_origin(
    tmp_path: Path,
) -> None:
    original, directory, old, identity, _ = _setup(tmp_path)
    _store_original(original, _changed(old))
    original_bytes = original.read_bytes()
    server = make_server(snapshot(), 0, directory, operator_database=original)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as client:
            preview = client.get("/api/source-reconciliation", params={
                "kind": "ceqa", "record_id": identity,
            }).json()
            payload = _body(preview, revision=True)
            endpoint = "/api/source-reconciliation-queue"
            assert client.post(endpoint, json=payload).status_code == 403
            for changed in (
                {"action": "retain_missing"}, {"action": "overwrite"},
                {"expected_native_evidence_id": None}, {"expected_source_sha256": "0" * 64},
                {"caller_confirmation": 1},
            ):
                assert client.post(endpoint, json={**payload, **changed},
                                   headers={"Origin": base}).status_code == 400
            accepted = client.post(endpoint, json=payload, headers={"Origin": base})
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["reconciliation_action"] == "retain_revision"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert original.read_bytes() == original_bytes
