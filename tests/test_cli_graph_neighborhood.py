from typer.testing import CliRunner

from constructionsight.cli import app
from constructionsight.intelligence import (
    CoverageStatus,
    EntityIdentity,
    EntityType,
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
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore

runner = CliRunner()


def _database_url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'cli_graph_neighborhood.sqlite3'}"


def _seed_cli_neighborhood_graph(database_url: str) -> None:
    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.upsert_entity(
            EntityIdentity(
                entity_id="gc-1",
                entity_type=EntityType.GENERAL_CONTRACTOR,
                canonical_name="ABC Construction Inc.",
                confidence_score=92,
                identity_status=IdentityStatus.CONFIRMED_SAME,
            )
        )
        store.upsert_entity(
            EntityIdentity(
                entity_id="developer-1",
                entity_type=EntityType.DEVELOPER,
                canonical_name="XYZ Development LLC",
                confidence_score=88,
                identity_status=IdentityStatus.PROBABLE_SAME,
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
                evidence_summary=(
                    "Synthetic shared project supports candidate working relationship."
                ),
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
            )
        )


def test_cli_shows_entity_neighborhood(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_cli_neighborhood_graph(database_url)

    result = runner.invoke(
        app,
        [
            "show-entity-neighborhood",
            "--entity-id",
            "gc-1",
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert "Entity Neighborhood gc-1" in result.output
    assert "gc-1" in result.output
    assert "entity" in result.output
    assert "Node count" in result.output
    assert "Edge count" in result.output
    assert "developer-1" in result.output
    assert "pc-1" in result.output
    assert "opp-1" in result.output


def test_cli_shows_project_neighborhood(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_cli_neighborhood_graph(database_url)

    result = runner.invoke(
        app,
        [
            "show-project-neighborhood",
            "--project-cluster-id",
            "pc-1",
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert "Project Neighborhood pc-1" in result.output
    assert "pc-1" in result.output
    assert "project_cluster" in result.output
    assert "Node count" in result.output
    assert "Edge count" in result.output
    assert "gc-1" in result.output
    assert "developer-1" in result.output
    assert "opp-1" in result.output
