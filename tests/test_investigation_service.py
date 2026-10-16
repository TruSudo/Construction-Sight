from datetime import UTC, datetime, timedelta

import pytest

from constructionsight.intelligence.artifact_identity import IdentityArtifactType as Artifact
from constructionsight.intelligence.investigation_service import (
    InvestigationObservation,
    InvestigationService,
)
from constructionsight.intelligence.schemas import (
    EvidenceRecord,
    LifecyclePhase,
    RelationshipStatus,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore

AT = datetime(2026, 10, 16, tzinfo=UTC)


def observation(key="a", *, day=0, county="Riverside", apn="123-456-789", sch=None):
    artifacts = {Artifact.APN: [apn], Artifact.EXACT_SITE_ADDRESS: ["123 Main St"]}
    if sch:
        artifacts[Artifact.CEQA_SCH_NUMBER] = [sch]
    return InvestigationObservation(
        evidence=EvidenceRecord(
            evidence_id=f"evidence:{key}:{day}",
            source_family=f"family:{key}",
            source_name=f"Synthetic source {key}",
            source_record_id=key,
            record_type="synthetic_test_observation",
            jurisdiction="Synthetic jurisdiction",
            retrieved_at=AT + timedelta(days=day),
            observed_at=AT + timedelta(days=day),
            raw_observations={"apn": apn, "county": county},
        ),
        title="Synthetic project",
        county=county,
        artifacts=artifacts,
    )


@pytest.fixture
def factory(tmp_path):
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'investigations.sqlite3'}")
    initialize_database(engine)
    yield session_factory(engine)
    engine.dispose()


def test_observation_replay_and_restart_preserve_one_unverified_investigation(factory):
    item = observation()
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        first = service.ingest(item)
        event_count = len(store.list_runtime_events())
        assert service.ingest(item) == first
        assert len(store.list_runtime_events()) == event_count
        assert first.lifecycle_phase == LifecyclePhase.UNKNOWN
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        assert len(store.list_project_clusters()) == 1
        assert len(store.list_entities()) == 1
        assert len(store.list_evidence()) == 1
        assert InvestigationService(store).current_observation(item.source_entity_id) == item
        assert store.list_relationships()[0].relationship_status == RelationshipStatus.UNRESOLVED


def test_caller_rollback_does_not_publish_savepoint_contents(factory):
    with pytest.raises(RuntimeError), managed_session(factory) as session:
        InvestigationService(IntelligenceStore(session)).ingest(observation())
        raise RuntimeError("synthetic outer transaction failure")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        assert store.list_evidence() == []
        assert store.list_project_clusters() == []
        assert store.list_runtime_events() == []


def test_normalization_cannot_change_under_the_same_evidence_receipt(factory):
    item = observation()
    with managed_session(factory) as session:
        service = InvestigationService(IntelligenceStore(session))
        service.ingest(item)
        with pytest.raises(ValueError, match="changed normalization"):
            service.ingest(item.model_copy(update={"title": "Rebound title"}))


def test_out_of_order_source_revision_retains_history_without_regressing_current_state(factory):
    newer = observation(day=2, apn="999-888-777")
    older = observation(day=0)
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(newer)
        cluster = service.ingest(older)
        assert cluster.apns == ["999-888-777"]
        assert cluster.first_seen == older.effective_at
        assert cluster.last_seen == newer.effective_at
        assert len(cluster.evidence_record_ids) == 2
        assert service.current_observation(older.source_entity_id) == newer


def test_same_parcel_generates_only_candidate_and_keeps_distinct_projects(factory):
    left, right = observation("a"), observation("b")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(left)
        service.ingest(right)
        candidate = service.correlate(left.source_entity_id, right.source_entity_id)
        count = len(store.list_runtime_events())
        service.correlate(right.source_entity_id, left.source_entity_id)
        assert len(store.list_runtime_events()) == count
        assert candidate.review_required
        assert len(store.list_project_clusters()) == 2
        relationships = [
            r
            for r in store.list_relationships()
            if r.predicate == "possible_same_project_requires_review"
        ]
        assert len(relationships) == 1
        assert relationships[0].relationship_status == RelationshipStatus.POSSIBLE
        assert set(relationships[0].supporting_evidence_ids) == {
            left.evidence.evidence_id,
            right.evidence.evidence_id,
        }


def test_same_parcel_with_conflicting_sch_numbers_retains_contradiction(factory):
    left = observation("a", sch="2026010001")
    right = observation("b", sch="2026010002")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(left)
        service.ingest(right)
        candidate = service.correlate(left.source_entity_id, right.source_entity_id)
        assert candidate.conflicts
        relationship = next(
            r
            for r in store.list_relationships()
            if r.predicate == "possible_same_project_requires_review"
        )
        assert relationship.relationship_status == RelationshipStatus.CONFLICTING
        assert len(relationship.contradictory_evidence_ids) == 2


def test_same_identifiers_in_different_counties_do_not_correlate(factory):
    left, right = observation("a"), observation("b", county="San Bernardino")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(left)
        service.ingest(right)
        with pytest.raises(ValueError, match="same explicitly known county"):
            service.correlate(left.source_entity_id, right.source_entity_id)
        assert len(store.list_relationships()) == 2  # Source-to-investigation only.


def test_revised_source_marks_candidate_stale_without_silently_revalidating_it(factory):
    left, right = observation("a"), observation("b")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(left)
        service.ingest(right)
        service.correlate(left.source_entity_id, right.source_entity_id)
        service.ingest(observation("a", day=1, apn="999-888-777"))
        relation = next(
            r
            for r in store.list_relationships()
            if r.predicate == "possible_same_project_requires_review"
        )
        assert relation.relationship_status is RelationshipStatus.STALE
        service.correlate(left.source_entity_id, right.source_entity_id)
        assert store.get_relationship(relation.relationship_id).relationship_status is (
            RelationshipStatus.CONFLICTING
        )


def test_correlation_cannot_reopen_a_reviewed_rejection(factory):
    left, right = observation("a"), observation("b")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(left)
        service.ingest(right)
        service.correlate(left.source_entity_id, right.source_entity_id)
        relation = next(
            r
            for r in store.list_relationships()
            if r.predicate == "possible_same_project_requires_review"
        )
        store.upsert_relationship(
            relation.model_copy(
                update={
                    "relationship_status": RelationshipStatus.SUPERSEDED,
                }
            )
        )
        with pytest.raises(ValueError, match="reviewed relationship"):
            service.correlate(left.source_entity_id, right.source_entity_id)


def test_fault_after_evidence_retention_rolls_back_entire_observation(factory, monkeypatch):
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)

        def fail(*args, **kwargs):
            raise ValueError("synthetic graph failure")

        monkeypatch.setattr(service.graph, "upsert_entity", fail)
        with pytest.raises(ValueError, match="synthetic graph failure"):
            service.ingest(observation())
        assert store.list_evidence() == []
        assert store.list_project_clusters() == []
        assert store.list_runtime_events() == []


def test_observation_rejects_naive_time_incomplete_location_and_unbound_identity():
    item = observation()
    payload = item.model_dump(mode="json")
    payload["evidence"]["source_family"] = None
    payload["evidence"]["content_hash"] = None
    with pytest.raises(ValueError, match="source family"):
        InvestigationObservation.model_validate(payload)
    with pytest.raises(ValueError, match="both coordinates"):
        InvestigationObservation.model_validate(
            item.model_copy(update={"latitude": 34}).model_dump()
        )
