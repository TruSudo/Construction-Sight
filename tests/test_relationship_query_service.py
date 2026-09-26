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
)
from constructionsight.intelligence.relationship_query_service import RelationshipQueryService
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


def _database_url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'relationship_query.sqlite3'}"


def _seed_relationship_graph(store: IntelligenceStore) -> None:
    store.upsert_evidence(
        EvidenceRecord(
            evidence_id="ev-graph",
            source_name="Synthetic Graph Evidence",
            record_type="synthetic",
            evidence_value="retained graph support",
        )
    )
    store.upsert_entity(
        EntityIdentity(
            entity_id="gc-1",
            entity_type=EntityType.GENERAL_CONTRACTOR,
            canonical_name="ABC Construction Inc.",
            confidence_score=92,
            identity_status=IdentityStatus.CONFIRMED_SAME,
            evidence_record_ids=["ev-graph"],
        )
    )
    store.upsert_entity(
        EntityIdentity(
            entity_id="developer-1",
            entity_type=EntityType.DEVELOPER,
            canonical_name="XYZ Development LLC",
            confidence_score=88,
            identity_status=IdentityStatus.PROBABLE_SAME,
            evidence_record_ids=["ev-graph"],
        )
    )
    store.upsert_project_cluster(
        ProjectCluster(
            project_cluster_id="pc-1",
            project_name="Synthetic Warehouse TI",
            normalized_address="123 Main St, Fontana, CA",
            jurisdiction="Fontana, CA",
            coverage_status=CoverageStatus.IN_ZONE,
            monitoring_status=MonitoringStatus.ACTIVE,
            cluster_status=ProjectClusterStatus.PROBABLE,
            lifecycle_phase=LifecyclePhase.VERTICAL_CONSTRUCTION,
            cluster_confidence=84,
            evidence_record_ids=["ev-graph"],
        )
    )
    store.upsert_project_cluster(
        ProjectCluster(
            project_cluster_id="pc-2",
            project_name="Synthetic Retail Shell",
            normalized_address="456 Market St, Ontario, CA",
            jurisdiction="Ontario, CA",
            coverage_status=CoverageStatus.IN_ZONE,
            monitoring_status=MonitoringStatus.ACTIVE,
            cluster_status=ProjectClusterStatus.POSSIBLE,
            lifecycle_phase=LifecyclePhase.PRECONSTRUCTION,
            cluster_confidence=64,
            evidence_record_ids=["ev-graph"],
        )
    )
    store.upsert_relationship(
        RelationshipAssertion(
            relationship_id="rel-gc-project",
            subject_entity_id="gc-1",
            predicate="general_contractor_for",
            object_entity_id="pc-1",
            relationship_status=RelationshipStatus.PROBABLE,
            confidence_score=86,
            evidence_summary="Synthetic contractor field supports GC relationship.",
            supporting_evidence_ids=["ev-graph"],
        )
    )
    store.upsert_relationship(
        RelationshipAssertion(
            relationship_id="rel-developer-project",
            subject_entity_id="developer-1",
            predicate="developer_for",
            object_entity_id="pc-1",
            relationship_status=RelationshipStatus.PROBABLE,
            confidence_score=82,
            evidence_summary="Synthetic planning record supports developer relationship.",
            supporting_evidence_ids=["ev-graph"],
        )
    )
    store.upsert_relationship(
        RelationshipAssertion(
            relationship_id="rel-gc-developer",
            subject_entity_id="gc-1",
            predicate="worked_with",
            object_entity_id="developer-1",
            relationship_status=RelationshipStatus.POSSIBLE,
            confidence_score=61,
            evidence_summary="Synthetic shared project supports candidate working relationship.",
            supporting_evidence_ids=["ev-graph"],
        )
    )
    store.upsert_opportunity(
        OpportunitySignal(
            opportunity_id="opp-1",
            category=OpportunityCategory.CONSTRUCTION_SITE_SECURITY,
            opportunity_status=OpportunityStatus.ACTIVE,
            project_cluster_id="pc-1",
            related_entity_ids=["gc-1"],
            confidence_score=81,
            evidence_summary="Active construction and known GC support security opportunity.",
            lifecycle_phase_basis=LifecyclePhase.VERTICAL_CONSTRUCTION,
            evidence_record_ids=["ev-graph"],
        )
    )
    store.upsert_opportunity(
        OpportunitySignal(
            opportunity_id="opp-2",
            category=OpportunityCategory.TEMPORARY_FENCING,
            opportunity_status=OpportunityStatus.CANDIDATE,
            project_cluster_id="pc-2",
            related_entity_ids=[],
            confidence_score=58,
            evidence_summary="Preconstruction project may need temporary fencing.",
            lifecycle_phase_basis=LifecyclePhase.PRECONSTRUCTION,
            evidence_record_ids=["ev-graph"],
        )
    )


def test_relationship_query_service_returns_entity_relationships_and_connected_entities(
    tmp_path,
) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        _seed_relationship_graph(store)

    with managed_session(factory) as session:
        service = RelationshipQueryService(IntelligenceStore(session))
        relationships = service.get_relationships_for_entity("gc-1")
        connected_entities = service.get_entities_connected_to_entity("gc-1")

    relationship_ids = {relationship.relationship_id for relationship in relationships}
    connected_entity_ids = {entity.entity_id for entity in connected_entities}

    assert relationship_ids == {"rel-gc-project", "rel-gc-developer"}
    assert connected_entity_ids == {"developer-1"}


def test_relationship_query_service_returns_projects_and_project_opportunities(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        _seed_relationship_graph(store)

    with managed_session(factory) as session:
        service = RelationshipQueryService(IntelligenceStore(session))
        projects = service.get_projects_for_entity("gc-1")
        project_relationships = service.get_relationships_for_project("pc-1")
        project_opportunities = service.get_opportunities_for_project("pc-1")

    assert {project.project_cluster_id for project in projects} == {"pc-1"}
    assert {relationship.relationship_id for relationship in project_relationships} == {
        "rel-gc-project",
        "rel-developer-project",
    }
    assert [opportunity.opportunity_id for opportunity in project_opportunities] == ["opp-1"]


def test_relationship_query_service_returns_direct_and_project_derived_entity_opportunities(
    tmp_path,
) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        _seed_relationship_graph(store)

    with managed_session(factory) as session:
        service = RelationshipQueryService(IntelligenceStore(session))
        gc_opportunities = service.get_opportunities_for_entity("gc-1")
        developer_opportunities = service.get_opportunities_for_entity("developer-1")

    assert {opportunity.opportunity_id for opportunity in gc_opportunities} == {"opp-1"}
    assert {opportunity.opportunity_id for opportunity in developer_opportunities} == {"opp-1"}



def test_relationship_query_does_not_truncate_records_older_than_one_hundred(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.upsert_evidence(
            EvidenceRecord(
                evidence_id="ev-scale",
                source_name="Synthetic Scale Evidence",
                record_type="synthetic",
                evidence_value="retained scale support",
            )
        )
        store.upsert_entity(
            EntityIdentity(
                entity_id="target-entity",
                entity_type=EntityType.ORGANIZATION,
                canonical_name="Target Entity",
                identity_status=IdentityStatus.CONFIRMED_SAME,
                evidence_record_ids=["ev-scale"],
            )
        )
        store.upsert_project_cluster(
            ProjectCluster(
                project_cluster_id="scale-project",
                project_name="Scale Project",
                evidence_record_ids=["ev-scale"],
            )
        )
        store.upsert_relationship(
            RelationshipAssertion(
                relationship_id="target-old-relationship",
                subject_entity_id="target-entity",
                predicate="associated_with",
                object_entity_id="scale-project",
                evidence_summary="Old target relationship remains queryable.",
                supporting_evidence_ids=["ev-scale"],
            )
        )
        for index in range(105):
            entity_id = f"noise-{index:03d}"
            store.upsert_entity(
                EntityIdentity(
                    entity_id=entity_id,
                    entity_type=EntityType.ORGANIZATION,
                    canonical_name=f"Noise Entity {index:03d}",
                    identity_status=IdentityStatus.CONFIRMED_SAME,
                    evidence_record_ids=["ev-scale"],
                )
            )
            store.upsert_relationship(
                RelationshipAssertion(
                    relationship_id=f"noise-rel-{index:03d}",
                    subject_entity_id=entity_id,
                    predicate="associated_with",
                    object_entity_id="scale-project",
                    evidence_summary="Synthetic noise relationship.",
                    supporting_evidence_ids=["ev-scale"],
                )
            )

    with managed_session(factory) as session:
        service = RelationshipQueryService(IntelligenceStore(session))
        relationships = service.get_relationships_for_entity("target-entity")

    assert [item.relationship_id for item in relationships] == [
        "target-old-relationship"
    ]
