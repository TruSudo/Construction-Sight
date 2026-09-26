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
from constructionsight.intelligence.graph_neighborhood_service import GraphNeighborhoodService
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


def _database_url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'graph_neighborhood.sqlite3'}"


def _seed_neighborhood_graph(store: IntelligenceStore) -> None:
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


def test_graph_neighborhood_service_returns_entity_neighborhood(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        _seed_neighborhood_graph(IntelligenceStore(session))

    with managed_session(factory) as session:
        neighborhood = GraphNeighborhoodService(IntelligenceStore(session)).get_entity_neighborhood(
            "gc-1"
        )

    assert neighborhood.center_node_id == "gc-1"
    assert neighborhood.center_node_kind == "entity"
    assert {entity.entity_id for entity in neighborhood.connected_entities} == {"developer-1"}
    assert {project.project_cluster_id for project in neighborhood.connected_projects} == {"pc-1"}
    assert {relationship.relationship_id for relationship in neighborhood.relationships} == {
        "rel-gc-project",
        "rel-gc-developer",
    }
    assert {opportunity.opportunity_id for opportunity in neighborhood.opportunities} == {"opp-1"}
    assert neighborhood.node_count == 4
    assert neighborhood.edge_count == 2


def test_graph_neighborhood_service_returns_project_neighborhood(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        _seed_neighborhood_graph(IntelligenceStore(session))

    with managed_session(factory) as session:
        neighborhood = GraphNeighborhoodService(
            IntelligenceStore(session)
        ).get_project_neighborhood("pc-1")

    assert neighborhood.center_node_id == "pc-1"
    assert neighborhood.center_node_kind == "project_cluster"
    assert {entity.entity_id for entity in neighborhood.connected_entities} == {
        "gc-1",
        "developer-1",
    }
    assert neighborhood.connected_projects == []
    assert {relationship.relationship_id for relationship in neighborhood.relationships} == {
        "rel-gc-project",
        "rel-developer-project",
    }
    assert {opportunity.opportunity_id for opportunity in neighborhood.opportunities} == {"opp-1"}
    assert neighborhood.node_count == 4
    assert neighborhood.edge_count == 2
