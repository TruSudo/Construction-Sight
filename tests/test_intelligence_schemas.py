from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from constructionsight.intelligence import (
    AuthorityState,
    AuthorityStatus,
    CoverageStatus,
    EntityIdentity,
    EntityType,
    EvidenceRecord,
    IdentityCandidate,
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


def test_evidence_record_requires_payload_and_preserves_utc_timestamp() -> None:
    record = EvidenceRecord(
        evidence_id="ev-1",
        source_name="Synthetic Permit Portal",
        record_type="permit",
        evidence_field="contractor",
        evidence_value="ABC Construction",
        confidence_contribution=88,
    )

    assert record.retrieved_at.tzinfo is not None
    assert record.confidence_contribution == 88

    with pytest.raises(ValidationError, match="evidence must include"):
        EvidenceRecord(
            evidence_id="ev-empty",
            source_name="Synthetic Permit Portal",
            record_type="permit",
        )


def test_entity_identity_rejects_duplicate_identity_lists() -> None:
    entity = EntityIdentity(
        entity_id="ent-1",
        entity_type=EntityType.GENERAL_CONTRACTOR,
        canonical_name="ABC Construction Inc.",
        normalized_name="abc construction",
        aliases=["ABC Construction"],
        source_names=["A.B.C. Construction"],
        identifiers={"cslb": "123456"},
        confidence_score=94,
        identity_status=IdentityStatus.CONFIRMED_SAME,
    )

    assert entity.entity_type == EntityType.GENERAL_CONTRACTOR
    assert entity.identity_status == IdentityStatus.CONFIRMED_SAME

    with pytest.raises(ValidationError, match="unique values"):
        EntityIdentity(
            entity_id="ent-duplicate",
            entity_type=EntityType.ORGANIZATION,
            canonical_name="ABC Construction Inc.",
            aliases=["ABC", "ABC"],
        )


def test_identity_candidate_rejects_self_match() -> None:
    candidate = IdentityCandidate(
        candidate_id="cand-1",
        left_entity_id="ent-1",
        right_entity_id="ent-2",
        candidate_score=77,
        matching_signals=["same normalized name", "same license number"],
        proposed_status=IdentityStatus.PROBABLE_SAME,
        explanation="Synthetic candidate uses shared identifiers.",
    )

    assert candidate.candidate_score == 77
    assert candidate.proposed_status == IdentityStatus.PROBABLE_SAME

    with pytest.raises(ValidationError, match="cannot match an entity to itself"):
        IdentityCandidate(
            candidate_id="cand-self",
            left_entity_id="ent-1",
            right_entity_id="ent-1",
            candidate_score=50,
            explanation="Invalid self-match.",
        )


def test_relationship_assertion_rejects_self_relationship() -> None:
    relationship = RelationshipAssertion(
        relationship_id="rel-1",
        subject_entity_id="gc-1",
        predicate="general_contractor_for",
        object_entity_id="project-1",
        relationship_status=RelationshipStatus.PROBABLE,
        confidence_score=86,
        evidence_summary="Synthetic permit contractor field supports the relationship.",
        supporting_evidence_ids=["ev-1"],
    )

    assert relationship.relationship_status == RelationshipStatus.PROBABLE
    assert relationship.supporting_evidence_ids == ["ev-1"]

    with pytest.raises(ValidationError, match="subject and object must differ"):
        RelationshipAssertion(
            relationship_id="rel-self",
            subject_entity_id="ent-1",
            predicate="related_to",
            object_entity_id="ent-1",
            evidence_summary="Invalid self-edge.",
        )


def test_authority_state_requires_reason_when_unresolved() -> None:
    state = AuthorityState(
        authority_state_id="auth-1",
        project_cluster_id="pc-1",
        authority_status=AuthorityStatus.AUTHORITY_PARTIALLY_RESOLVED,
        known_authority_entity_ids=["gc-1"],
        missing_authority_roles=["developer", "director"],
        confidence_score=70,
    )

    assert state.authority_status == AuthorityStatus.AUTHORITY_PARTIALLY_RESOLVED

    with pytest.raises(ValidationError, match="requires unresolved_reason"):
        AuthorityState(
            authority_state_id="auth-unresolved",
            project_cluster_id="pc-1",
            authority_status=AuthorityStatus.AUTHORITY_UNRESOLVED_WITH_REASON,
        )


def test_project_cluster_requires_anchor_and_supports_lifecycle_fields() -> None:
    cluster = ProjectCluster(
        project_cluster_id="pc-1",
        project_name="Synthetic Warehouse TI",
        normalized_address="123 Main St, Fontana, CA",
        apns=["0000-000-00-0000"],
        jurisdiction="Fontana, CA",
        coverage_status=CoverageStatus.IN_ZONE,
        monitoring_status=MonitoringStatus.ACTIVE,
        cluster_status=ProjectClusterStatus.PROBABLE,
        lifecycle_phase=LifecyclePhase.ROUGH_IN_TRADES,
        cluster_confidence=82,
        major_project_probability=74,
        standalone_probability=18,
    )

    assert cluster.coverage_status == CoverageStatus.IN_ZONE
    assert cluster.lifecycle_phase == LifecyclePhase.ROUGH_IN_TRADES

    with pytest.raises(ValidationError, match="requires name, address, APN, or evidence"):
        ProjectCluster(project_cluster_id="pc-empty")


def test_opportunity_signal_requires_target() -> None:
    signal = OpportunitySignal(
        opportunity_id="opp-1",
        category=OpportunityCategory.CONSTRUCTION_SITE_SECURITY,
        project_cluster_id="pc-1",
        opportunity_status=OpportunityStatus.ACTIVE,
        confidence_score=81,
        evidence_summary="Active construction phase and known GC support security outreach.",
        lifecycle_phase_basis=LifecyclePhase.VERTICAL_CONSTRUCTION,
    )

    assert signal.category == OpportunityCategory.CONSTRUCTION_SITE_SECURITY
    assert signal.lifecycle_phase_basis == LifecyclePhase.VERTICAL_CONSTRUCTION

    with pytest.raises(ValidationError, match="requires a project, site, or related entity target"):
        OpportunitySignal(
            opportunity_id="opp-empty",
            category=OpportunityCategory.ELECTRICAL,
            evidence_summary="No target should fail.",
        )


def test_runtime_event_schema_supports_graph_update_payloads() -> None:
    created_at = datetime.now(UTC)
    event = RuntimeEvent(
        event_id="evt-1",
        event_type=RuntimeEventType.PROJECT_CLUSTER_CREATED,
        severity=RuntimeEventSeverity.HIGH,
        created_at=created_at,
        source_service="project_clusterer",
        correlation_id="run-1",
        operational_region_id="san-bernardino-riverside",
        jurisdiction="Fontana, CA",
        project_cluster_refs=["pc-1"],
        payload={"cluster_status": "probable"},
        message="New probable project cluster created.",
        confidence_delta=12,
        requires_user_attention=True,
    )

    assert event.event_type == RuntimeEventType.PROJECT_CLUSTER_CREATED
    assert event.severity == RuntimeEventSeverity.HIGH
    assert event.payload["cluster_status"] == "probable"


def test_watchlist_item_schema_tracks_user_attention_targets() -> None:
    item = WatchlistItem(
        watchlist_item_id="watch-1",
        workspace_id="workspace-1",
        target_type=EntityType.GENERAL_CONTRACTOR,
        target_id="gc-1",
        status=WatchlistStatus.ACTIVE,
        priority=90,
        notes="Watch this GC for new in-zone activity.",
    )

    assert item.status == WatchlistStatus.ACTIVE
    assert item.priority == 90
