from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread

import pytest

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.models import PublicSource, SourceVerificationResult
from constructionsight.operator_services.source_registry_persistence_service import (
    persist_authorized_source_registry_records,
    persist_authorized_source_verification_result,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore


def _source() -> PublicSource:
    payload = json.loads(Path("data/source_registry.seed.json").read_text(encoding="utf-8"))[0]
    return PublicSource.model_validate(payload)


def _factory():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    return session_factory(engine)


# Regression: CS-SR-082
def test_registry_persistence_requires_scope_bound_confirmation() -> None:
    factory = _factory()

    with managed_session(factory) as session:
        with pytest.raises(AuthorizationDeniedError, match="confirmation"):
            persist_authorized_source_registry_records(
                session,
                [_source()],
                caller_confirmation=False,
                authorization_reason="Attempt unconfirmed registry import.",
                operator_id="operator:test",
            )
        assert SourceRegistryStore(session).list_sources() == []


def test_registry_persistence_applies_exact_reviewed_records() -> None:
    factory = _factory()
    source = _source()

    with managed_session(factory) as session:
        result = persist_authorized_source_registry_records(
            session,
            [source],
            caller_confirmation=True,
            authorization_reason="Import the reviewed source registry.",
            operator_id="operator:test",
        )

    assert result.report.processed_count == 1
    with managed_session(factory) as session:
        persisted = SourceRegistryStore(session).get_by_name(source.source_name)
    assert persisted == source


def test_verification_persistence_is_append_only_for_registry_authority() -> None:
    factory = _factory()
    source = _source()
    with managed_session(factory) as session:
        SourceRegistryStore(session).upsert_source(source)

    result = SourceVerificationResult(
        source_name=source.source_name,
        public_url=source.public_url,
        url_reachable=True,
        confidence_score=99,
        notes="Evidence only; registry authority remains unchanged.",
    )
    with managed_session(factory) as session:
        persisted = persist_authorized_source_verification_result(
            session,
            result,
            caller_confirmation=True,
            authorization_reason="Retain the exact verification evidence.",
            operator_id="operator:test",
        )
        assert persisted.report.verification_id >= 1

    with managed_session(factory) as session:
        current = SourceRegistryStore(session).get_by_name(source.source_name)
        evidence = VerificationStore(session).list_latest()

    assert current == source
    assert len(evidence) == 1


def test_name_only_source_lookup_rejects_ambiguous_identity() -> None:
    factory = _factory()
    source = _source()
    second_payload = source.model_dump(mode="json")
    second_payload["public_url"] = "https://example.invalid/alternate"
    second = PublicSource.model_validate(second_payload)

    with managed_session(factory) as session:
        store = SourceRegistryStore(session)
        store.upsert_source(source)
        store.upsert_source(second)
        with pytest.raises(ValueError, match="source name is ambiguous"):
            store.get_by_name(source.source_name)
        assert store.get_by_identity(source.source_name, str(source.public_url)) == source
        assert store.get_by_identity(second.source_name, str(second.public_url)) == second


def test_registry_persistence_rejects_preexisting_transaction_state() -> None:
    factory = _factory()
    source = _source()

    with managed_session(factory) as session:
        store = SourceRegistryStore(session)
        assert store.list_sources() == []
        with pytest.raises(RuntimeError, match="fresh transaction"):
            persist_authorized_source_registry_records(
                session,
                [source],
                caller_confirmation=True,
                authorization_reason="A stale transaction must not authorize a registry write.",
                operator_id="operator:test",
            )
        session.rollback()
        assert SourceRegistryStore(session).list_sources() == []


def test_registry_mutation_lock_serializes_competing_writers(tmp_path: Path) -> None:
    database = tmp_path / "source-registry-lock.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    factory = session_factory(engine)
    source = _source()
    first_locked = Event()
    release_first = Event()
    second_finished = Event()
    failures: list[BaseException] = []

    def first_writer() -> None:
        try:
            with managed_session(factory) as session:
                store = SourceRegistryStore(session)
                store.acquire_authorized_mutation_lock()
                store.upsert_source(source)
                first_locked.set()
                assert release_first.wait(timeout=5)
        except BaseException as exc:
            failures.append(exc)
            first_locked.set()

    def second_writer() -> None:
        try:
            assert first_locked.wait(timeout=5)
            with managed_session(factory) as session:
                SourceRegistryStore(session).acquire_authorized_mutation_lock()
            second_finished.set()
        except BaseException as exc:
            failures.append(exc)
            second_finished.set()

    first = Thread(target=first_writer)
    second = Thread(target=second_writer)
    first.start()
    assert first_locked.wait(timeout=5)
    second.start()
    assert not second_finished.wait(timeout=0.1)
    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    assert second_finished.is_set()
    engine.dispose()
