from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

import constructionsight.investigation_jobs as jobs
from constructionsight.intelligence.investigation_service import (
    InvestigationObservation,
    InvestigationService,
)
from constructionsight.intelligence.schemas import EvidenceRecord
from constructionsight.investigation_jobs import InvestigationJobQueue, JobDefinition, StaleJobLease
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


@pytest.fixture
def queue(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'jobs.sqlite3'}")
    initialize_database(engine)
    yield InvestigationJobQueue(engine)
    engine.dispose()


def definition(number=1, **kwargs):
    return JobDefinition(kind="retained_json_replay", inputs={"fixture": number}, **kwargs)


def test_job_replay_restart_and_dependencies_are_durable(queue):
    root = queue.enqueue(definition())
    assert queue.enqueue(definition()) == root
    child = queue.enqueue(definition(2, depends_on=[root.job_id]))
    with pytest.raises(ValueError, match="already retained"):
        queue.enqueue(definition(3, depends_on=["missing-job"]))
    claim = queue.claim("worker:a")
    assert claim.job_id == root.job_id
    assert queue.claim("worker:b") is None
    with managed_session(queue.factory) as session:
        queue.begin_write(session)
        queue.complete_in_transaction(IntelligenceStore(session), claim, {"processed": 1})
    restarted = InvestigationJobQueue(queue.factory.kw["bind"])
    following = restarted.claim("worker:b")
    assert following.job_id == child.job_id
    assert following.attempt == 1
    assert len(restarted.list_jobs()) == 2


def test_two_workers_cannot_claim_the_same_attempt(queue):
    queue.enqueue(definition())
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(queue.claim, f"worker:{n}") for n in range(2)]
        claims = [future.result(timeout=10) for future in futures]
    assert sum(claim is not None for claim in claims) == 1


def test_expired_lease_recovers_after_restart_and_rejects_stale_completion(queue, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(jobs, "_now", lambda: clock[0])
    queue.enqueue(definition(lease_seconds=10))
    first = queue.claim("worker:crashed")
    clock[0] += 11
    restarted = InvestigationJobQueue(queue.factory.kw["bind"])
    second = restarted.claim("worker:recovered")
    assert second.job_id == first.job_id
    assert second.attempt == 2
    assert second.lease_token != first.lease_token
    with pytest.raises(StaleJobLease), managed_session(queue.factory) as session:
        queue.begin_write(session)
        queue.complete_in_transaction(IntelligenceStore(session), first, {"incorrect": True})
    with managed_session(queue.factory) as session:
        queue.begin_write(session)
        queue.complete_in_transaction(IntelligenceStore(session), second, {"processed": 1})
    assert restarted.list_jobs()[0].status == "completed"


def test_retries_are_bounded_and_failed_dependencies_block_children(queue, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(jobs, "_now", lambda: clock[0])
    root = queue.enqueue(definition(max_attempts=2))
    queue.enqueue(definition(2, depends_on=[root.job_id]))
    first = queue.claim("worker:a")
    waiting = queue.fail(first, error_code="synthetic_transient_failure", retryable=True)
    assert waiting.status == "retry_wait"
    assert queue.claim("worker:a") is None
    clock[0] = waiting.available_at + 1
    second = queue.claim("worker:a")
    assert second.attempt == 2
    assert (
        queue.fail(second, error_code="synthetic_transient_failure", retryable=True).status
        == "failed"
    )
    assert queue.claim("worker:a") is None
    assert {state.status for state in queue.list_jobs()} == {"failed", "blocked"}


def test_knowledge_and_job_completion_rollback_and_commit_together(queue, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(jobs, "_now", lambda: clock[0])
    queue.enqueue(definition(lease_seconds=10))
    claim = queue.claim("worker:a")
    item = InvestigationObservation(
        evidence=EvidenceRecord(
            evidence_id="evidence:job-atomicity",
            source_name="Synthetic test source",
            source_family="synthetic",
            source_record_id="one",
            record_type="synthetic_test",
            retrieved_at=datetime(2026, 10, 16, tzinfo=UTC),
            raw_observations={"title": "Synthetic test"},
        ),
        title="Synthetic test",
    )
    with pytest.raises(RuntimeError), managed_session(queue.factory) as session:
        queue.begin_write(session)
        store = IntelligenceStore(session)
        InvestigationService(store).ingest(item)
        queue.complete_in_transaction(store, claim, {"investigation_id": item.investigation_id})
        raise RuntimeError("synthetic interruption before outer commit")
    with managed_session(queue.factory) as session:
        store = IntelligenceStore(session)
        assert store.list_evidence() == []
        assert queue.current(store, claim.job_id).status == "running"
    clock[0] += 11
    recovered = queue.claim("worker:b")
    with managed_session(queue.factory) as session:
        queue.begin_write(session)
        store = IntelligenceStore(session)
        InvestigationService(store).ingest(item)
        queue.complete_in_transaction(store, recovered, {"investigation_id": item.investigation_id})
    with managed_session(queue.factory) as session:
        store = IntelligenceStore(session)
        assert len(store.list_evidence()) == 1
        assert queue.current(store, claim.job_id).status == "completed"
