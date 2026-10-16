from datetime import UTC, datetime, timedelta

import pytest

import constructionsight.effect_consumption as effect_consumption
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.intelligence.artifact_identity import IdentityArtifactType as Artifact
from constructionsight.intelligence.graph_service import IntelligenceGraphService
from constructionsight.intelligence.investigation_location_service import (
    InvestigationLocationService,
)
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.investigation_review_service import InvestigationReviewService
from constructionsight.intelligence.investigation_service import (
    InvestigationObservation,
    InvestigationService,
)
from constructionsight.intelligence.schemas import (
    EvidenceRecord,
    LifecyclePhase,
    RelationshipStatus,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
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


def test_temporal_reversion_retains_each_real_change_and_resumable_event_cursor(factory):
    item = observation()
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(item)
        entity = store.get_entity(item.source_entity_id)
        updated = entity.model_copy(update={"canonical_name": "Revised source title"})
        for value in [updated, entity, updated]:
            service.graph.upsert_entity(value)
        revisions = [
            event
            for event in store.list_runtime_events()
            if event.source_service == "intelligence_store_revision"
            and event.payload["record_kind"] == "entity"
        ]
        assert len(revisions) == 4
        assert len({event.event_id for event in revisions}) == 4
        assert all(event.event_type.value != "entity_merged" for event in revisions)
        first = store.runtime_event_page(limit=3)
        assert len(first) == 3
        cursor = first[-1][0]
        remaining = store.runtime_event_page(after=cursor)
        assert not (
            {event.event_id for _, event in first} & {event.event_id for _, event in remaining}
        )
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        assert store.runtime_event_page(after=cursor) == remaining
        with pytest.raises(ValueError, match="cursor"):
            store.runtime_event_page(after=True)


def test_shared_dossier_preserves_chronology_uncertainty_conflicts_and_unmapped_records(factory):
    older = observation("a")
    newer = observation("a", day=2, sch="2026010001")
    conflicting = observation("b", sch="2026010002")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(newer)
        service.ingest(older)
        service.ingest(conflicting)
        service.correlate(newer.source_entity_id, conflicting.source_entity_id)
        before = store.runtime_event_cursor()
        dossier = InvestigationQueryService(store).dossier(older.investigation_id)
        assert dossier["event_cursor"] == before == store.runtime_event_cursor()
        assert len(dossier["evidence"]) == 3
        assert dossier["evidence_context"][conflicting.evidence.evidence_id] == (
            "cited_relationship_evidence_only"
        )
        assert len(dossier["chronology"]) == 2
        assert dossier["chronology"][0]["evidence_id"] == older.evidence.evidence_id
        assert (
            dossier["source_observations"][0]["evidence"]["evidence_id"]
            == newer.evidence.evidence_id
        )
        assert dossier["contradictions"]
        assert dossier["source_claimed_points"] == []
        assessment = dossier["assessment"]
        assert assessment["investigation_completeness"] == "partial"
        assert assessment["identity_independently_verified"] is False
        assert assessment["construction_activity"] == "unknown"
        assert assessment["commercial_readiness"] == "unassessed"
        bounded = InvestigationQueryService(store).dossier(older.investigation_id, evidence_limit=1)
        assert bounded["evidence_truncated"] is True
        with pytest.raises(ValueError, match="unknown investigation"):
            InvestigationQueryService(store).dossier("absent")


def test_parcel_assessment_reuses_existing_resolution_retains_evidence_and_invalidates_on_change(
    factory,
):
    item = observation()
    parcel = ParcelCoreRecord(
        parcel_record_id="parcel:synthetic",
        source_key="synthetic:assessor",
        source_record_id="p-1",
        apn="123-456-789",
        normalized_apn="123456789",
        county="Riverside",
        created_at=AT,
    )
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        service.ingest(item)
        locations = InvestigationLocationService(store)
        first = locations.resolve(item.source_entity_id, [parcel])
        cursor = store.runtime_event_cursor()
        assert locations.resolve(item.source_entity_id, [parcel]) == first
        assert store.runtime_event_cursor() == cursor
        dossier = InvestigationQueryService(store).dossier(item.investigation_id)
        assert len(dossier["location_assessments"]) == 1
        assert dossier["location_assessments"][0]["candidate_pool_complete"] is False
        assert dossier["location_assessments"][0]["project_identity_verified"] is False
        assert len(dossier["evidence"]) == 2
        assert dossier["source_claimed_points"] == []
        service.ingest(observation(day=1))
        assert (
            InvestigationQueryService(store).dossier(item.investigation_id)["location_assessments"]
            == []
        )
        relation = next(
            r for r in store.list_relationships() if r.predicate == "parcel_location_candidate"
        )
        assert relation.relationship_status is RelationshipStatus.STALE


def test_empty_parcel_assessment_is_persistable_idempotent_and_honestly_incomplete(factory):
    item = observation()
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        InvestigationService(store).ingest(item)
        locations = InvestigationLocationService(store)
        result = locations.resolve(item.source_entity_id, [])
        assert "no parcel core record matched site signals" in result.limitations
        assert locations.resolve(item.source_entity_id, []) == result


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


def test_authorized_association_and_rejection_control_one_dossier_without_erasing_sources(
    factory,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        effect_consumption, "_CONSUMPTION_DATABASE_PATH", tmp_path / "review-effects.sqlite3"
    )
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
    reviews = InvestigationReviewService(factory.kw["bind"])
    preview = reviews.preview(relation.relationship_id)
    with pytest.raises(AuthorizationDeniedError):
        reviews.review(
            relation.relationship_id,
            decision="associate",
            target_id=left.investigation_id,
            expected_identity=preview["expected_identity"],
            reason="Synthetic explicit source review",
            caller_confirmation=False,
        )
    result = reviews.review(
        relation.relationship_id,
        decision="associate",
        target_id=left.investigation_id,
        expected_identity=preview["expected_identity"],
        reason="Synthetic explicit source review",
        caller_confirmation=True,
        operator_id="operator:synthetic-test",
    )
    assert result["identity_independently_verified"] is False
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        query = InvestigationQueryService(store)
        for identity in [left.investigation_id, right.investigation_id]:
            dossier = query.dossier(identity)
            assert dossier["investigation"]["project_cluster_id"] == left.investigation_id
            assert len(dossier["source_observations"]) == 2
            assert dossier["pending_association_reviews"] == []
            assert dossier["assessment"]["identity_independently_verified"] is False
        assert len(store.list_project_clusters()) == 2
        assert len(store.list_evidence()) == 2
        inventory = query.inventory(limit=10)
        assert inventory["total"] == 1
        assert inventory["rows"][0]["investigation_id"] == left.investigation_id
        InvestigationService(store).ingest(observation("b", day=1))
        revised = query.dossier(left.investigation_id)
        assert revised["pending_association_reviews"]
        assert len(revised["chronology"]) == 3
        assert len(revised["evidence"]) == 3
    fresh = reviews.preview(relation.relationship_id)
    reviews.review(
        relation.relationship_id,
        decision="reject",
        target_id=None,
        expected_identity=fresh["expected_identity"],
        reason="Synthetic rejection after new evidence",
        caller_confirmation=True,
        operator_id="operator:synthetic-test",
    )
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        assert store.get_relationship(relation.relationship_id).relationship_status is (
            RelationshipStatus.REJECTED
        )
        for item in [left, right]:
            dossier = InvestigationQueryService(store).dossier(item.investigation_id)
            assert dossier["investigation"]["project_cluster_id"] == item.investigation_id
            assert len(dossier["source_observations"]) == 1
        assert len(store.list_evidence()) == 3
        assert InvestigationQueryService(store).inventory()["total"] == 2
        with pytest.raises(ValueError, match="reviewed relationship"):
            InvestigationService(store).correlate(left.source_entity_id, right.source_entity_id)


def test_stale_review_cannot_apply_after_new_source_evidence(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(
        effect_consumption, "_CONSUMPTION_DATABASE_PATH", tmp_path / "stale-review-effects.sqlite3"
    )
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
    reviews = InvestigationReviewService(factory.kw["bind"])
    preview = reviews.preview(relation.relationship_id)
    with managed_session(factory) as session:
        InvestigationService(IntelligenceStore(session)).ingest(observation("b", day=1))
    with pytest.raises(AuthorizationDeniedError):
        reviews.review(
            relation.relationship_id,
            decision="associate",
            target_id=left.investigation_id,
            expected_identity=preview["expected_identity"],
            reason="Synthetic stale review",
            caller_confirmation=True,
        )


def test_failed_association_rolls_back_alias_context_and_candidate_together(
    factory,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        effect_consumption, "_CONSUMPTION_DATABASE_PATH", tmp_path / "failed-review-effects.sqlite3"
    )
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
        cursor = store.runtime_event_cursor()
    reviews = InvestigationReviewService(factory.kw["bind"])
    preview = reviews.preview(relation.relationship_id)
    original = IntelligenceGraphService.upsert_relationship

    def inject_failure(self, relationship):
        if relationship.predicate == "reviewed_source_context":
            raise ValueError("synthetic failure after alias write")
        return original(self, relationship)

    monkeypatch.setattr(IntelligenceGraphService, "upsert_relationship", inject_failure)
    with pytest.raises(ValueError, match="after alias write"):
        reviews.review(
            relation.relationship_id,
            decision="associate",
            target_id=left.investigation_id,
            expected_identity=preview["expected_identity"],
            reason="Synthetic failure rollback verification",
            caller_confirmation=True,
        )
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        assert store.runtime_event_cursor() == cursor
        assert store.get_relationship(relation.relationship_id).relationship_status is (
            RelationshipStatus.POSSIBLE
        )
        dossier = InvestigationQueryService(store).dossier(right.investigation_id)
        assert dossier["investigation"]["project_cluster_id"] == right.investigation_id


def test_three_reviewed_sources_share_revision_aware_chronology_without_identity_upgrade(
    factory, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        effect_consumption,
        "_CONSUMPTION_DATABASE_PATH",
        tmp_path / "three-source-review-effects.sqlite3",
    )
    left, middle, right = observation("ceqa"), observation("permit"), observation("planning")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        service = InvestigationService(store)
        for record in (left, middle, right):
            service.ingest(record)
        for record in (middle, right):
            service.correlate(left.source_entity_id, record.source_entity_id)
        relations = {
            r.object_entity_id if r.subject_entity_id == left.investigation_id
            else r.subject_entity_id: r.relationship_id
            for r in store.list_relationships()
            if r.predicate == "possible_same_project_requires_review"
            and left.investigation_id in {r.subject_entity_id, r.object_entity_id}
        }
        assert set(relations) == {middle.investigation_id, right.investigation_id}
        unreviewed = InvestigationQueryService(store).dossier(left.investigation_id)
        assert len(unreviewed["source_observations"]) == 1
        assert len(unreviewed["candidate_source_links"]) == 2
        assert unreviewed["cross_source_investigation"]["reviewed_context_source_count"] == 0
        assert unreviewed["source_membership"][0]["membership_basis"] == "source_anchor"

    reviews = InvestigationReviewService(factory.kw["bind"])
    for record in (middle, right):
        relation_id = relations[record.investigation_id]
        preview = reviews.preview(relation_id)
        applied = reviews.review(
            relation_id,
            decision="associate",
            target_id=left.investigation_id,
            expected_identity=preview["expected_identity"],
            reason="Synthetic three-family investigation context review",
            caller_confirmation=True,
            operator_id="operator:three-source-test",
        )
        assert applied["identity_independently_verified"] is False

    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        query = InvestigationQueryService(store)
        assert query.inventory()["total"] == 1
        dossier = query.dossier(right.investigation_id)
        assert dossier["investigation"]["project_cluster_id"] == left.investigation_id
        membership = dossier["source_membership"]
        assert {item["source_family"] for item in membership} == {
            "family:ceqa", "family:permit", "family:planning"
        }
        assert len(membership) == 3
        assert sum(item["membership_basis"] == "source_anchor" for item in membership) == 1
        assert sum(
            item["membership_basis"] == "reviewed_source_context" for item in membership
        ) == 2
        assert all(item["retained_revision_count"] == 1 for item in membership)
        assert len(dossier["chronology"]) == 3
        assert all(event["is_current_source_revision"] for event in dossier["chronology"])
        assert len(dossier["association_review_states"]) == 2
        assert all(
            not state["requires_reassessment"] for state in dossier["association_review_states"]
        )
        assert dossier["cross_source_investigation"]["reviewed_context_source_count"] == 2
        assert dossier["assessment"]["identity_independently_verified"] is False
        assert dossier["assessment"]["commercial_authority_granted"] is False

    # New conflicting location claim stays attributable to its own source.
    revised_source = observation("planning", day=2, apn="999-888-777")
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        InvestigationService(store).ingest(revised_source)
        dossier = InvestigationQueryService(store).dossier(left.investigation_id)
        membership = dossier["source_membership"]
        revised_member = next(
            item for item in membership if item["source_family"] == "family:planning"
        )
        assert revised_member["retained_revision_count"] == 2
        assert revised_member["current_evidence_id"] == revised_source.evidence.evidence_id
        assert len(dossier["chronology"]) == 4
        history = [
            event for event in dossier["chronology"]
            if event["source_family"] == "family:planning"
        ]
        assert len(history) == 2
        assert [event["is_current_source_revision"] for event in history] == [False, True]
        assert history[-1]["effective_at"] == revised_source.effective_at.isoformat()
        assert history[-1]["membership_basis"] == "reviewed_source_context"
        assert len(dossier["pending_association_reviews"]) >= 1
        stale = [
            state for state in dossier["association_review_states"]
            if state["requires_reassessment"]
        ]
        assert stale
        assert any(
            change["source_id"] == revised_source.source_entity_id
            and revised_source.evidence.evidence_id in change["current_evidence_ids"]
            for state in stale for change in state["changed_sources"]
        )
        assert dossier["cross_source_investigation"]["requires_association_reassessment"]
        assert dossier["cross_source_investigation"]["source_record_count"] == 3
        assert dossier["cross_source_investigation"]["source_families"] == [
            "family:ceqa", "family:permit", "family:planning"
        ]
        assert dossier["cross_source_investigation"]["identity_independently_verified"] is False
        assert dossier["cross_source_investigation"]["commercial_authority_granted"] is False
        assert dossier["cross_source_investigation"]["source_history_truncated"] is False
        assert len(store.list_project_clusters()) == 3
        assert len(store.list_evidence()) == 4
