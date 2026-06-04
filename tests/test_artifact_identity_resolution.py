import pytest
from pydantic import ValidationError

from constructionsight.intelligence import (
    ArtifactConflict,
    ArtifactMatch,
    ArtifactObservation,
    ArtifactTier,
    IdentityArtifactType,
    IdentityFingerprint,
    IdentityResolutionCandidate,
    MemoryCandidate,
    MemoryKind,
    MemoryLifecycleStatus,
    ResolutionDecisionType,
    RippleEvent,
    RippleEventType,
    SourceLayoutMemory,
    artifact_tier,
    artifact_weight,
    calculate_resolution_score,
)


def _match(
    artifact_type: IdentityArtifactType,
    left_observation_id: str,
    right_observation_id: str,
    strength: int = 100,
    source_families: list[str] | None = None,
) -> ArtifactMatch:
    return ArtifactMatch(
        artifact_type=artifact_type,
        left_observation_id=left_observation_id,
        right_observation_id=right_observation_id,
        left_value="same",
        right_value="same",
        match_strength=strength,
        source_families=source_families or [],
        evidence_record_ids=[f"ev-{left_observation_id}-{right_observation_id}"],
        explanation="Synthetic artifact match for deterministic test coverage.",
    )


def test_artifact_registry_maps_artifacts_to_expected_tiers_and_weights() -> None:
    assert artifact_tier(IdentityArtifactType.APN) == ArtifactTier.NEAR_UNIQUE
    assert artifact_tier(IdentityArtifactType.EXACT_SITE_ADDRESS) == ArtifactTier.STRONG_RELATIONAL
    assert artifact_tier(IdentityArtifactType.PROJECT_TITLE) == ArtifactTier.CONTEXTUAL
    assert artifact_tier(IdentityArtifactType.GENERIC_PROJECT_WORD) == ArtifactTier.WEAK_ASSISTIVE

    assert artifact_weight(IdentityArtifactType.APN) > artifact_weight(
        IdentityArtifactType.EXACT_SITE_ADDRESS
    )
    assert artifact_weight(IdentityArtifactType.EXACT_SITE_ADDRESS) > artifact_weight(
        IdentityArtifactType.PROJECT_TITLE
    )
    assert artifact_weight(IdentityArtifactType.PROJECT_TITLE) > artifact_weight(
        IdentityArtifactType.GENERIC_PROJECT_WORD
    )


def test_artifact_observation_preserves_raw_and_normalized_values() -> None:
    observation = ArtifactObservation(
        observation_id="obs-apn-1",
        artifact_type=IdentityArtifactType.APN,
        raw_value="  APN 0292-123-45  ",
        normalized_value="0292-123-45",
        source_name="Synthetic CEQA Source",
        source_family="ceqanet",
        source_record_id="sch-2025060123",
        jurisdiction="Hesperia, CA",
        observed_field="project_description",
        evidence_record_id="ev-1",
        confidence_score=95,
    )

    assert observation.raw_value == "APN 0292-123-45"
    assert observation.normalized_value == "0292-123-45"
    assert observation.tier == ArtifactTier.NEAR_UNIQUE
    assert observation.weight == artifact_weight(IdentityArtifactType.APN)
    assert observation.observed_at.tzinfo is not None

    with pytest.raises(ValidationError, match="artifact values must not be blank"):
        ArtifactObservation(
            observation_id="obs-blank",
            artifact_type=IdentityArtifactType.PROJECT_TITLE,
            raw_value="   ",
            normalized_value="warehouse",
            source_name="Synthetic Source",
        )


def test_identity_fingerprint_requires_observations_and_unique_observation_ids() -> None:
    apn_observation = ArtifactObservation(
        observation_id="obs-apn",
        artifact_type=IdentityArtifactType.APN,
        raw_value="0292-123-45",
        normalized_value="0292-123-45",
        source_name="Synthetic CEQA Source",
    )
    title_observation = ArtifactObservation(
        observation_id="obs-title",
        artifact_type=IdentityArtifactType.PROJECT_TITLE,
        raw_value="Commerce Center II",
        normalized_value="commerce center ii",
        source_name="Synthetic Agenda Packet",
    )

    fingerprint = IdentityFingerprint(
        fingerprint_id="fingerprint-1",
        target_identity_id="project-1",
        artifact_observations=[apn_observation, title_observation],
        evidence_record_ids=["ev-1", "ev-2"],
    )

    assert fingerprint.artifact_types == {
        IdentityArtifactType.APN,
        IdentityArtifactType.PROJECT_TITLE,
    }
    assert fingerprint.near_unique_observations == [apn_observation]

    with pytest.raises(ValidationError, match="identity fingerprint requires"):
        IdentityFingerprint(
            fingerprint_id="fingerprint-empty",
            target_identity_id="project-empty",
        )

    with pytest.raises(ValidationError, match="artifact observation IDs must contain unique"):
        IdentityFingerprint(
            fingerprint_id="fingerprint-duplicate",
            target_identity_id="project-duplicate",
            artifact_observations=[apn_observation, apn_observation],
        )


def test_artifact_match_rejects_self_match_and_scores_contribution() -> None:
    match = _match(
        IdentityArtifactType.EXACT_SITE_ADDRESS,
        left_observation_id="left-address",
        right_observation_id="right-address",
        strength=50,
    )

    assert match.tier == ArtifactTier.STRONG_RELATIONAL
    assert match.contribution == round(artifact_weight(IdentityArtifactType.EXACT_SITE_ADDRESS) / 2)

    with pytest.raises(ValidationError, match="cannot compare an observation to itself"):
        _match(
            IdentityArtifactType.APN,
            left_observation_id="same-observation",
            right_observation_id="same-observation",
        )


def test_resolution_score_rewards_independent_source_convergence_and_caps_at_100() -> None:
    matches = [
        _match(
            IdentityArtifactType.APN,
            left_observation_id="left-apn",
            right_observation_id="right-apn",
            source_families=["ceqanet", "agenda_packet"],
        ),
        _match(
            IdentityArtifactType.PLANNING_CASE_NUMBER,
            left_observation_id="left-case",
            right_observation_id="right-case",
            source_families=["permit_portal"],
        ),
    ]

    assert calculate_resolution_score(matches, conflicts=[]) == 100

    candidate = IdentityResolutionCandidate(
        candidate_id="candidate-auto-link",
        left_identity_id="project-a",
        right_identity_id="project-b",
        supporting_matches=matches,
        evidence_summary="APN and planning case converge across independent source families.",
    )

    assert candidate.resolution_score == 100
    assert candidate.has_near_unique_support is True
    assert candidate.recommended_decision == ResolutionDecisionType.AUTO_LINK


def test_weak_artifact_support_can_queue_search_but_cannot_auto_link() -> None:
    weak_match = _match(
        IdentityArtifactType.GENERIC_PROJECT_WORD,
        left_observation_id="left-word",
        right_observation_id="right-word",
        source_families=["agenda_packet"],
    )

    candidate = IdentityResolutionCandidate(
        candidate_id="candidate-weak-only",
        left_identity_id="project-a",
        right_identity_id="project-b",
        supporting_matches=[weak_match],
        evidence_summary="Only a generic project word overlaps.",
    )

    assert candidate.has_only_weak_support is True
    assert candidate.resolution_score == artifact_weight(IdentityArtifactType.GENERIC_PROJECT_WORD)
    assert candidate.recommended_decision == ResolutionDecisionType.QUEUE_FOLLOWUP_SEARCH


def test_near_unique_conflict_blocks_identity_convergence() -> None:
    conflict = ArtifactConflict(
        artifact_type=IdentityArtifactType.CEQA_SCH_NUMBER,
        left_value="SCH-2025060123",
        right_value="SCH-2025999999",
        conflict_strength=100,
        evidence_record_ids=["ev-left", "ev-right"],
        explanation="Different CEQA SCH numbers indicate different environmental records.",
    )

    candidate = IdentityResolutionCandidate(
        candidate_id="candidate-conflict",
        left_identity_id="project-a",
        right_identity_id="project-b",
        conflicts=[conflict],
        evidence_summary="Near-unique CEQA identifiers conflict.",
    )

    assert candidate.has_near_unique_conflict is True
    assert candidate.resolution_score == 0
    assert candidate.recommended_decision == ResolutionDecisionType.REJECT_MATCH


def test_identity_resolution_candidate_rejects_self_match_and_empty_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot compare an identity to itself"):
        IdentityResolutionCandidate(
            candidate_id="candidate-self",
            left_identity_id="project-a",
            right_identity_id="project-a",
            supporting_matches=[
                _match(
                    IdentityArtifactType.APN,
                    left_observation_id="left-apn",
                    right_observation_id="right-apn",
                )
            ],
            evidence_summary="Invalid self comparison.",
        )

    with pytest.raises(ValidationError, match="requires support or conflict artifacts"):
        IdentityResolutionCandidate(
            candidate_id="candidate-empty",
            left_identity_id="project-a",
            right_identity_id="project-b",
            evidence_summary="No artifacts means no evaluable candidate.",
        )


def test_source_layout_memory_records_where_artifacts_are_found() -> None:
    memory = SourceLayoutMemory(
        source_layout_memory_id="layout-hesperia-agenda",
        source_name="Synthetic Hesperia Agenda Packets",
        source_family="agenda_packet",
        jurisdiction="Hesperia, CA",
        artifact_field_hints={
            IdentityArtifactType.APN: ["staff_report.parcel_table", "attachments.apn_list"],
            IdentityArtifactType.PLANNING_CASE_NUMBER: ["staff_report.header"],
        },
        evidence_record_ids=["ev-layout-1"],
    )

    assert memory.status == MemoryLifecycleStatus.CANDIDATE
    assert memory.artifact_field_hints[IdentityArtifactType.APN] == [
        "staff_report.parcel_table",
        "attachments.apn_list",
    ]

    with pytest.raises(ValidationError, match="source-layout memory requires"):
        SourceLayoutMemory(
            source_layout_memory_id="layout-empty",
            source_name="Synthetic Source",
            source_family="agenda_packet",
        )


def test_memory_candidate_cannot_overwrite_raw_evidence_and_requires_promotion_support() -> None:
    with pytest.raises(ValidationError, match="may never overwrite raw evidence"):
        MemoryCandidate(
            memory_id="memory-bad-overwrite",
            memory_kind=MemoryKind.SEARCH_ALIAS,
            proposed_value="FLC means Foothill Logistics Center",
            raw_evidence_overwrite_allowed=True,
        )

    with pytest.raises(ValidationError, match="promoted memory requires"):
        MemoryCandidate(
            memory_id="memory-promoted-without-support",
            memory_kind=MemoryKind.SEARCH_ALIAS,
            status=MemoryLifecycleStatus.PROMOTED,
            proposed_value="FLC means Foothill Logistics Center",
        )

    promoted = MemoryCandidate(
        memory_id="memory-promoted",
        memory_kind=MemoryKind.SEARCH_ALIAS,
        status=MemoryLifecycleStatus.PROMOTED,
        proposed_value="FLC means Foothill Logistics Center",
        scope_jurisdiction="Hesperia, CA",
        supporting_observation_ids=["obs-title", "obs-permit-title"],
        evidence_record_ids=["ev-1", "ev-2"],
        promotion_requirements=[
            "observed in at least two independent source families",
            "does not overwrite raw source title",
        ],
    )

    assert promoted.raw_evidence_overwrite_allowed is False
    assert promoted.status == MemoryLifecycleStatus.PROMOTED


def test_ripple_event_requires_explicit_trigger_and_target() -> None:
    event = RippleEvent(
        ripple_event_id="ripple-1",
        event_type=RippleEventType.FOLLOWUP_SEARCH_QUEUED,
        triggering_observation_id="obs-apn",
        project_cluster_id="pc-1",
        queued_actions=[ResolutionDecisionType.QUEUE_FOLLOWUP_SEARCH],
        evidence_record_ids=["ev-1"],
        message="New APN observation queued follow-up alias searches.",
        requires_user_attention=True,
    )

    assert event.event_type == RippleEventType.FOLLOWUP_SEARCH_QUEUED
    assert event.requires_user_attention is True

    with pytest.raises(ValidationError, match="requires a triggering observation or candidate"):
        RippleEvent(
            ripple_event_id="ripple-no-trigger",
            event_type=RippleEventType.ARTIFACT_OBSERVED,
            project_cluster_id="pc-1",
            message="Invalid ripple event.",
        )

    with pytest.raises(ValidationError, match="requires a target identity or project cluster"):
        RippleEvent(
            ripple_event_id="ripple-no-target",
            event_type=RippleEventType.ARTIFACT_OBSERVED,
            triggering_observation_id="obs-apn",
            message="Invalid ripple event.",
        )
