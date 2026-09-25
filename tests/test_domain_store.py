from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.document_models import DocumentRecord
from constructionsight.domain_types import PartyRole, RelationshipType
from constructionsight.entity_models import Entity
from constructionsight.permit_models import PermitRecord
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.provenance import Provenance, ProvenanceConfidenceBasis
from constructionsight.relationship_models import RelationshipRecord
from constructionsight.site_models import Site
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.domain_store import (
    AgendaItemStore,
    CeqaStore,
    DocumentStore,
    EntityStore,
    PermitStore,
    PlanningCaseStore,
    RelationshipStore,
    SiteStore,
)


def test_site_store_round_trip() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
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
    assert persisted.provenance[0].band.value == "high"


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
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
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
    assert persisted.provenance[0].band.value == "high"
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
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
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


def test_ceqa_store_round_trip() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
    record = CeqaRecord(
        ceqa_key="ceqa:test:001",
        title="Synthetic Environmental Review",
        document_type="EIR",
        state_clearinghouse_number="2026000000",
        provenance=[provenance],
    )

    with managed_session(factory) as session:
        store = CeqaStore(session)
        store.upsert(record)
        persisted = store.get("ceqa:test:001")

    assert persisted is not None
    assert persisted.is_high_signal_document is True
    assert persisted.has_state_clearinghouse_number is True
    assert persisted.provenance[0].band.value == "high"


def test_agenda_item_store_round_trip() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    item = AgendaItemRecord(
        agenda_key="agenda:test:001",
        meeting_body="Test Planning Body",
        jurisdiction="Test Jurisdiction",
        county="Test County",
        title="Synthetic Site Plan Review",
        document_urls=["https://example.gov/staff-report.pdf"],
    )

    with managed_session(factory) as session:
        store = AgendaItemStore(session)
        store.upsert(item)
        persisted = store.get("agenda:test:001")

    assert persisted is not None
    assert persisted.has_documents is True
    assert persisted.appears_development_related is True
    assert str(persisted.document_urls[0]) == "https://example.gov/staff-report.pdf"


def test_document_store_round_trip() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
    document = DocumentRecord(
        document_key="document:test:001",
        source_name="Synthetic Public Source",
        url="https://example.gov/document.pdf",
        text_extract="Synthetic document text.",
        provenance=[provenance],
    )

    with managed_session(factory) as session:
        store = DocumentStore(session)
        store.upsert(document)
        persisted = store.get("document:test:001")

    assert persisted is not None
    assert persisted.has_url is True
    assert persisted.has_text is True
    assert persisted.provenance[0].band.value == "high"


def test_relationship_store_round_trip() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    provenance = Provenance(
        source_name="Synthetic Public Source",
        adapter_family="synthetic-test",
        raw_reference="synthetic:test",
        evidence_text="retained synthetic public evidence",
        confidence_basis=ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION,
    )
    relationship = RelationshipRecord(
        relationship_key="relationship:test:001",
        subject_key="entity:test:a",
        relationship_type=RelationshipType.ASSOCIATED_WITH,
        object_key="project:test:b",
        confidence_score=90,
        provenance=[provenance],
    )

    with managed_session(factory) as session:
        store = RelationshipStore(session)
        store.upsert(relationship)
        persisted = store.get("relationship:test:001")

    assert persisted is not None
    assert persisted.is_high_confidence is True
    assert persisted.relationship_type is RelationshipType.ASSOCIATED_WITH
    assert persisted.provenance[0].band.value == "high"
