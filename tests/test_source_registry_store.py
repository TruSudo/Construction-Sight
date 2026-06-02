import json
from pathlib import Path

from constructionsight.models import PublicSource
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore


def test_source_registry_store_round_trip() -> None:
    records = json.loads(Path("data/source_registry.seed.json").read_text(encoding="utf-8"))
    sources = [PublicSource.model_validate(record) for record in records]

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = SourceRegistryStore(session)
        count = store.upsert_many(sources)
        persisted = store.list_sources()

    assert count == 4
    assert len(persisted) == 4
    assert {source.source_name for source in persisted} == {
        "CEQAnet State Clearinghouse",
        "CSLB Public License Search",
        "San Bernardino County EZOP",
        "Riverside County PLUS Online",
    }


def test_source_registry_upsert_updates_existing_record() -> None:
    record = json.loads(Path("data/source_registry.seed.json").read_text(encoding="utf-8"))[0]
    source = PublicSource.model_validate(record)
    updated = source.model_copy(update={"confidence_score": 95})

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = SourceRegistryStore(session)
        store.upsert_source(source)
        store.upsert_source(updated)
        persisted = store.list_sources()

    assert len(persisted) == 1
    assert persisted[0].confidence_score == 95
