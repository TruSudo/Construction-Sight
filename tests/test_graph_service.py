from constructionsight.intelligence import (
    CoverageStatus,
    EntityIdentity,
    EntityType,
    EvidenceRecord,
    IdentityStatus,
    LifecyclePhase,
    MonitoringStatus,
    OpportunityCategory,
    OpportunitySignal,
    OpportunityStatus,
    ProjectCluster,
    ProjectClusterStatus,
    RelationshipAssertion,
    RelationshipStatus,
    RuntimeEventType,
)
from constructionsight.intelligence.graph_service import IntelligenceGraphService
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


def _database_url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'graph_service.sqlite3'}"


def test_graph_service_persists_core_graph_records_and_events(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    evidence = EvidenceRecord(
        evidence_id="ev-1",
        source_name="Synthetic Permit Portal",
        record_type="permit",
        evidence_field="contractor",
        evidence_value="ABC Construction",
        confidence_contribution=90,
    )
    entity = EntityIdentity(
        entity_id="gc-1",
        entity_type=EntityType.GENERAL_CONTRACTOR,
        canonical_name="ABC Construction Inc.",
        confidence_score=92,
        identity_status=IdentityStatus.CONFIRMED_SAME,
    )
    cluster = ProjectCluster(
        project_cluster_id="pc-1",
        project_name="Synthetic Warehouse TI",
        normalized_address="123 Main St, Fontana, CA",
        jurisdiction="Fontana, CA",
        coverage_status=CoverageStatus.IN_ZONE,
        monitoring_status=MonitoringStatus.ACTIVE,
        cluster_status=ProjectClusterStatus.PROBABLE,
        lifecycle_phase=LifecyclePhase.VERTICAL_CONSTRUCTION,
        cluster_confidence=84,
        evidence_record_ids=["ev-1"],
    )
    relationship = RelationshipAssertion(
        relationship_id="rel-1",
        subject_entity_id="gc-1",
        predicate="general_contractor_for",
        object_entity_id="pc-1",
        relationship_status=RelationshipStatus.PROBABLE,
        confidence_score=86,
        evidence_summary="Synthetic contractor field supports GC relationship.",
        supporting_evidence_ids=["ev-1"],
    )
    opportunity = OpportunitySignal(
        opportunity_id="opp-1",
        category=OpportunityCategory.CONSTRUCTION_SITE_SECURITY,
        opportunity_status=OpportunityStatus.ACTIVE,
        project_cluster_id="pc-1",
        related_entity_ids=["gc-1"],
        confidence_score=81,
        evidence_summary="Active construction and known GC support security opportunity.",
        evidence_record_ids=["ev-1"],
        lifecycle_phase_basis=LifecyclePhase.VERTICAL_CONSTRUCTION,
    )

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = IntelligenceGraphService(store)
        service.record_evidence(evidence)
        service.upsert_entity(entity)
        service.upsert_project_cluster(cluster)
        service.upsert_relationship(relationship)
        service.upsert_opportunity(opportunity)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        assert store.list_evidence()[0].evidence_id == "ev-1"
        assert store.list_entities()[0].entity_id == "gc-1"
        assert store.list_project_clusters()[0].project_cluster_id == "pc-1"
        assert store.list_relationships()[0].relationship_id == "rel-1"
        assert store.list_opportunities()[0].opportunity_id == "opp-1"

        events = store.list_runtime_events(limit=10)
        event_types = {event.event_type for event in events}
        assert RuntimeEventType.SOURCE_RECORD_DISCOVERED in event_types
        assert RuntimeEventType.ENTITY_CREATED in event_types
        assert RuntimeEventType.PROJECT_CLUSTER_CREATED in event_types
        assert RuntimeEventType.RELATIONSHIP_CREATED in event_types
        assert RuntimeEventType.OPPORTUNITY_SIGNAL_CREATED in event_types


def test_graph_service_event_payloads_preserve_references(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    relationship = RelationshipAssertion(
        relationship_id="rel-1",
        subject_entity_id="gc-1",
        predicate="general_contractor_for",
        object_entity_id="pc-1",
        relationship_status=RelationshipStatus.CONFIRMED,
        confidence_score=94,
        evidence_summary="Synthetic evidence confirms GC relationship.",
        supporting_evidence_ids=["ev-1", "ev-2"],
    )

    with managed_session(factory) as session:
        service = IntelligenceGraphService(
            IntelligenceStore(session), source_service="test_graph_service"
        )
        service.upsert_relationship(relationship)

    with managed_session(factory) as session:
        events = IntelligenceStore(session).list_runtime_events(limit=5)

    relationship_event = next(
        event for event in events if event.event_type == RuntimeEventType.RELATIONSHIP_CREATED
    )
    assert relationship_event.source_service == "test_graph_service"
    assert relationship_event.entity_refs == ["gc-1", "pc-1"]
    assert relationship_event.source_record_refs == ["ev-1", "ev-2"]
    assert relationship_event.payload["relationship_id"] == "rel-1"
    assert relationship_event.payload["confidence_score"] == 94


def test_graph_service_emits_update_events_for_existing_records(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    first_relationship = RelationshipAssertion(
        relationship_id="rel-1",
        subject_entity_id="gc-1",
        predicate="general_contractor_for",
        object_entity_id="pc-1",
        relationship_status=RelationshipStatus.POSSIBLE,
        confidence_score=55,
        evidence_summary="Initial weak synthetic signal.",
        supporting_evidence_ids=["ev-1"],
    )
    updated_relationship = RelationshipAssertion(
        relationship_id="rel-1",
        subject_entity_id="gc-1",
        predicate="general_contractor_for",
        object_entity_id="pc-1",
        relationship_status=RelationshipStatus.CONFIRMED,
        confidence_score=94,
        evidence_summary="Additional synthetic evidence confirms relationship.",
        supporting_evidence_ids=["ev-1", "ev-2"],
    )
    first_cluster = ProjectCluster(
        project_cluster_id="pc-1",
        project_name="Synthetic Warehouse TI",
        normalized_address="123 Main St, Fontana, CA",
        cluster_status=ProjectClusterStatus.POSSIBLE,
        lifecycle_phase=LifecyclePhase.PRECONSTRUCTION,
        cluster_confidence=50,
        evidence_record_ids=["ev-1"],
    )
    updated_cluster = ProjectCluster(
        project_cluster_id="pc-1",
        project_name="Synthetic Warehouse TI",
        normalized_address="123 Main St, Fontana, CA",
        cluster_status=ProjectClusterStatus.PROBABLE,
        lifecycle_phase=LifecyclePhase.VERTICAL_CONSTRUCTION,
        cluster_confidence=88,
        evidence_record_ids=["ev-1", "ev-2"],
    )

    with managed_session(factory) as session:
        service = IntelligenceGraphService(IntelligenceStore(session))
        service.upsert_relationship(first_relationship)
        service.upsert_relationship(updated_relationship)
        service.upsert_project_cluster(first_cluster)
        service.upsert_project_cluster(updated_cluster)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        relationships = store.list_relationships()
        clusters = store.list_project_clusters()
        events = store.list_runtime_events(limit=10)

    assert len(relationships) == 1
    assert relationships[0].confidence_score == 94
    assert relationships[0].relationship_status == RelationshipStatus.CONFIRMED
    assert len(clusters) == 1
    assert clusters[0].cluster_confidence == 88
    assert clusters[0].lifecycle_phase == LifecyclePhase.VERTICAL_CONSTRUCTION

    relationship_update = next(
        event for event in events if event.event_type == RuntimeEventType.RELATIONSHIP_UPDATED
    )
    cluster_update = next(
        event for event in events if event.event_type == RuntimeEventType.PROJECT_CLUSTER_UPDATED
    )
    assert relationship_update.payload["operation"] == "updated"
    assert relationship_update.payload["confidence_score"] == 94
    assert cluster_update.payload["operation"] == "updated"
    assert cluster_update.payload["cluster_confidence"] == 88
