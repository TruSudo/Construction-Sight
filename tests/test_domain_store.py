from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.domain_store import EntityStore, SiteStore


def test_site_store_round_trip() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    provenance = Provenance(source_name="Synthetic Public Source", confidence_score=90, verified=True)
    site = Site(
        site_key="site:test:001",
        county="Test County",
        city="Test City",
        apn="0000-000-00-0000",
        provenance=[provenance],
    )

    with managed_session(factory) as session:
        store = SiteStore(session)
        store.upsert(site)
        persisted = store.get("site:test:001")

    assert persisted is not None
    assert persisted.site_key == "site:test:001"
    assert persisted.apn == "0000-000-00-0000"
    assert persisted.provenance[0].band.value == "verified"


def test_entity_store_round_trip_and_update() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    entity = Entity(
        entity_key="entity:test:001",
        name="Synthetic Entity LLC",
        role=PartyRole.APPLICANT,
    )
    updated = entity.model_copy(update={"role": PartyRole.DEVELOPER})

    with managed_session(factory) as session:
        store = EntityStore(session)
        store.upsert(entity)
        store.upsert(updated)
        persisted = store.get("entity:test:001")
        all_entities = store.list_all()

    assert persisted is not None
    assert persisted.role is PartyRole.DEVELOPER
    assert len(all_entities) == 1
