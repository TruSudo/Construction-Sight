from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.permit_models import PermitRecord
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.domain_store import (
    EntityStore,
    PermitStore,
    PlanningCaseStore,
    SiteStore,
)


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


def test_permit_store_round_trip_and_update() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    site = Site(site_key="site:test:permit", county="Test County")
    entity = Entity(
        entity_key="entity:test:permit-applicant",
        name="Synthetic Applicant LLC",
        role=PartyRole.APPLICANT,
    )
    provenance = Provenance(source_name="Synthetic Public Source", confidence_score=90, verified=True)
    permit = PermitRecord(
        permit_key="permit:test:001",
        permit_number="P-001",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        status="Submitted",
        site=site,
        entities=[entity],
        provenance=[provenance],
    )
    updated = permit.model_copy(update={"status": "Issued"})

    with managed_session(factory) as session:
        store = PermitStore(session)
        store.upsert(permit)
        store.upsert(updated)
        persisted = store.get("permit:test:001")
        all_permits = store.list_all()

    assert persisted is not None
    assert persisted.status == "Issued"
    assert persisted.is_issued is True
    assert persisted.site is not None
    assert persisted.site.site_key == "site:test:permit"
    assert persisted.entities[0].role is PartyRole.APPLICANT
    assert persisted.provenance[0].band.value == "verified"
    assert len(all_permits) == 1


def test_planning_case_store_round_trip_and_update() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    site = Site(site_key="site:test:planning", county="Test County")
    entity = Entity(
        entity_key="entity:test:planning-applicant",
        name="Synthetic Planning Applicant LLC",
        role=PartyRole.APPLICANT,
    )
    provenance = Provenance(source_name="Synthetic Public Source", confidence_score=75)
    planning_case = PlanningCaseRecord(
        case_key="planning:test:001",
        case_number="PC-001",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        status="Filed",
        site=site,
        entities=[entity],
        provenance=[provenance],
    )
    updated = planning_case.model_copy(update={"status": "Approved"})

    with managed_session(factory) as session:
        store = PlanningCaseStore(session)
        store.upsert(planning_case)
        store.upsert(updated)
        persisted = store.get("planning:test:001")
        all_cases = store.list_all()

    assert persisted is not None
    assert persisted.status == "Approved"
    assert persisted.is_approved is True
    assert persisted.site is not None
    assert persisted.site.site_key == "site:test:planning"
    assert persisted.entities[0].role is PartyRole.APPLICANT
    assert persisted.provenance[0].band.value == "high"
    assert len(all_cases) == 1
