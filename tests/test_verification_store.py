import json
from pathlib import Path

from constructionsight.models import PlatformFamily, PublicSource, SourceVerificationResult
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore


def test_verification_store_persists_evidence_without_mutating_source_authority() -> None:
    seed_record = json.loads(Path("data/source_registry.seed.json").read_text(encoding="utf-8"))[0]
    source = PublicSource.model_validate(seed_record)

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        source_store = SourceRegistryStore(session)
        source_store.upsert_source(source)
        result = SourceVerificationResult(
            source_name=source.source_name,
            public_url=source.public_url,
            url_reachable=True,
            portal_type_detected=PlatformFamily.CEQANET,
            public_search_available=True,
            login_required=False,
            confidence_score=88,
            notes="Verified test source.",
        )
        verification_store = VerificationStore(session)
        verification_store.add_result(result)
        latest = verification_store.list_latest()
        updated_source = source_store.get_by_name(source.source_name)

    assert len(latest) == 1
    assert latest[0].source_name == source.source_name
    assert latest[0].confidence_score == 88
    assert updated_source is not None
    assert updated_source.verification_status == source.verification_status
    assert updated_source.confidence_score == source.confidence_score
