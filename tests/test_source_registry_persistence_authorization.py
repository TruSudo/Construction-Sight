from __future__ import annotations

import json
from pathlib import Path

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
