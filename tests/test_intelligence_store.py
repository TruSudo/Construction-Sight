import pytest

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
    RuntimeEvent,
    RuntimeEventSeverity,
    RuntimeEventType,
    WatchlistItem,
    WatchlistStatus,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore


def _database_url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'intelligence.sqlite3'}"


def test_intelligence_store_round_trips_core_records(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    evidence = EvidenceRecord(
        evidence_id="ev-1",
        source_name="Synthetic Permit Portal",
        record_type="permit",
        evidence_field="contractor",
        evidence_value="ABC Construction",
        confidence_contribution=91,
    )
    entity = EntityIdentity(
        entity_id="gc-1",
        entity_type=EntityType.GENERAL_CONTRACTOR,
        canonical_name="ABC Construction Inc.",
        normalized_name="abc construction",
        confidence_score=93,
        identity_status=IdentityStatus.CONFIRMED_SAME,
        evidence_record_ids=["ev-1"],
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
        confidence_score=82,
        evidence_summary="Active project with known GC supports security outreach.",
        evidence_record_ids=["ev-1"],
        lifecycle_phase_basis=LifecyclePhase.VERTICAL_CONSTRUCTION,
    )
    event = RuntimeEvent(
        event_id="evt-1",
        event_type=RuntimeEventType.PROJECT_CLUSTER_CREATED,
        severity=RuntimeEventSeverity.HIGH,
        source_service="project_clusterer",
        project_cluster_refs=["pc-1"],
        payload={"cluster_status": "probable"},
        message="Synthetic project cluster created.",
        requires_user_attention=True,
    )
    watchlist_item = WatchlistItem(
        watchlist_item_id="watch-1",
        workspace_id="workspace-1",
        target_type=EntityType.GENERAL_CONTRACTOR,
        target_id="gc-1",
        status=WatchlistStatus.ACTIVE,
        priority=90,
    )

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.upsert_evidence(evidence)
        store.upsert_entity(entity)
        store.upsert_project_cluster(cluster)
        store.upsert_relationship(relationship)
        store.upsert_opportunity(opportunity)
        store.add_runtime_event(event)
        store.upsert_watchlist_item(watchlist_item)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        assert store.list_evidence()[0].evidence_id == "ev-1"
        assert store.list_entities()[0].entity_id == "gc-1"
        assert store.list_project_clusters()[0].project_cluster_id == "pc-1"
        assert store.list_relationships()[0].relationship_id == "rel-1"
        assert store.list_opportunities()[0].opportunity_id == "opp-1"
        assert store.list_runtime_events()[0].event_id == "evt-1"
        assert store.list_watchlist_items()[0].watchlist_item_id == "watch-1"


def test_intelligence_store_upsert_replaces_payload_without_duplicate_rows(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    first = EntityIdentity(
        entity_id="gc-1",
        entity_type=EntityType.GENERAL_CONTRACTOR,
        canonical_name="ABC Construction",
        confidence_score=70,
        identity_status=IdentityStatus.POSSIBLE_SAME,
        evidence_record_ids=["ev-1"],
    )
    second = EntityIdentity(
        entity_id="gc-1",
        entity_type=EntityType.GENERAL_CONTRACTOR,
        canonical_name="ABC Construction Inc.",
        confidence_score=95,
        identity_status=IdentityStatus.CONFIRMED_SAME,
        aliases=["ABC Construction"],
        evidence_record_ids=["ev-1"],
    )

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.upsert_evidence(
            EvidenceRecord(
                evidence_id="ev-1",
                source_name="Synthetic Permit Portal",
                record_type="permit",
                evidence_value="ABC Construction",
            )
        )
        store.upsert_entity(first)
        store.upsert_entity(second)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        records = store.list_entities(limit=10)
        revision_events = [
            event
            for event in store.list_runtime_events(limit=20)
            if event.source_service == "intelligence_store_revision"
            and event.payload.get("record_kind") == "entity"
            and event.payload.get("logical_id") == "gc-1"
        ]

    assert len(records) == 1
    assert records[0].canonical_name == "ABC Construction Inc."
    assert records[0].confidence_score == 95
    assert records[0].identity_status == IdentityStatus.CONFIRMED_SAME
    assert len(revision_events) == 2
    assert any(event.payload["previous_payload"] is None for event in revision_events)
    assert any(
        event.payload["previous_payload"] is not None
        and event.payload["current_payload"]["canonical_name"] == "ABC Construction Inc."
        for event in revision_events
    )


def test_intelligence_store_filters_watchlist_items_by_workspace(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.upsert_watchlist_item(
            WatchlistItem(
                watchlist_item_id="watch-1",
                workspace_id="workspace-1",
                target_type=EntityType.PROJECT,
                target_id="pc-1",
            )
        )
        store.upsert_watchlist_item(
            WatchlistItem(
                watchlist_item_id="watch-2",
                workspace_id="workspace-2",
                target_type=EntityType.GENERAL_CONTRACTOR,
                target_id="gc-1",
                status=WatchlistStatus.PAUSED,
            )
        )

    with managed_session(factory) as session:
        workspace_one_items = IntelligenceStore(session).list_watchlist_items(
            workspace_id="workspace-1"
        )

    assert len(workspace_one_items) == 1
    assert workspace_one_items[0].watchlist_item_id == "watch-1"
    assert workspace_one_items[0].workspace_id == "workspace-1"



def test_intelligence_store_rejects_missing_evidence_and_dangling_targets(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.upsert_evidence(
            EvidenceRecord(
                evidence_id="ev-1",
                source_name="Synthetic Permit Portal",
                record_type="permit",
                evidence_value="ABC Construction",
            )
        )
        store.upsert_entity(
            EntityIdentity(
                entity_id="gc-1",
                entity_type=EntityType.GENERAL_CONTRACTOR,
                canonical_name="ABC Construction Inc.",
                confidence_score=92,
                identity_status=IdentityStatus.CONFIRMED_SAME,
                evidence_record_ids=["ev-1"],
            )
        )

        with pytest.raises(ValueError, match="retained evidence"):
            store.upsert_relationship(
                RelationshipAssertion(
                    relationship_id="rel-no-evidence",
                    subject_entity_id="gc-1",
                    predicate="general_contractor_for",
                    object_entity_id="pc-missing",
                    evidence_summary="Unsupported relationship must fail.",
                )
            )

        with pytest.raises(ValueError, match="missing graph target"):
            store.upsert_relationship(
                RelationshipAssertion(
                    relationship_id="rel-dangling",
                    subject_entity_id="gc-1",
                    predicate="general_contractor_for",
                    object_entity_id="pc-missing",
                    evidence_summary="Referenced evidence exists but target does not.",
                    supporting_evidence_ids=["ev-1"],
                )
            )



def test_intelligence_evidence_id_cannot_be_rebound_to_changed_content(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    first = EvidenceRecord(
        evidence_id="ev-immutable",
        source_name="Synthetic Permit Portal",
        record_type="permit",
        evidence_value="ABC Construction",
    )
    changed = EvidenceRecord(
        evidence_id="ev-immutable",
        source_name="Synthetic Permit Portal",
        record_type="permit",
        evidence_value="Different Contractor",
    )

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.upsert_evidence(first)
        with pytest.raises(ValueError, match="evidence ID collision"):
            store.upsert_evidence(changed)


def test_runtime_event_id_is_immutable(tmp_path) -> None:
    engine = create_database_engine(_database_url(tmp_path))
    initialize_database(engine)
    factory = session_factory(engine)

    first = RuntimeEvent(
        event_id="evt-immutable",
        event_type=RuntimeEventType.ENTITY_CREATED,
        source_service="test",
        message="First retained event.",
        payload={"revision": 1},
    )
    changed = RuntimeEvent(
        event_id="evt-immutable",
        event_type=RuntimeEventType.ENTITY_CREATED,
        source_service="test",
        message="Changed event must fail.",
        payload={"revision": 2},
    )

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        store.add_runtime_event(first)
        with pytest.raises(ValueError, match="runtime event ID collision"):
            store.add_runtime_event(changed)
