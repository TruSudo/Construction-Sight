import pytest

from constructionsight.intelligence import (
    ArtifactResolutionService,
    ArtifactTier,
    IdentityArtifactType,
    IdentityFingerprint,
    ResolutionDecisionType,
    ResolutionTargetKind,
    can_artifact_type_conflict,
    resolve_identity_fingerprints,
)
from constructionsight.intelligence.artifact_identity import (
    ArtifactObservation,
    canonical_artifact_observation_id,
    canonical_identity_fingerprint_id,
    canonical_resolution_candidate_id,
    normalize_artifact_value,
)


def _observation(
    observation_id: str,
    artifact_type: IdentityArtifactType,
    value: str,
    *,
    source_family: str = "synthetic_source",
    evidence_record_id: str | None = None,
) -> ArtifactObservation:
    normalized_value = normalize_artifact_value(artifact_type, value)
    return ArtifactObservation(
        observation_id=canonical_artifact_observation_id(
            artifact_type=artifact_type,
            normalized_value=normalized_value,
            source_name="Synthetic Public Source",
            source_family=source_family,
            source_record_id=None,
            jurisdiction=None,
            observed_field=None,
            evidence_record_id=evidence_record_id,
        ),
        artifact_type=artifact_type,
        raw_value=value,
        normalized_value=normalized_value,
        source_name="Synthetic Public Source",
        source_family=source_family,
        evidence_record_id=evidence_record_id,
        confidence_score=90,
    )


def _fingerprint(
    target_identity_id: str,
    observations: list[ArtifactObservation],
    *,
    target_kind: ResolutionTargetKind = ResolutionTargetKind.PROJECT,
) -> IdentityFingerprint:
    return IdentityFingerprint(
        fingerprint_id=canonical_identity_fingerprint_id(
            target_identity_id=target_identity_id,
            target_kind=target_kind,
            observation_ids=[item.observation_id for item in observations],
            evidence_record_ids=[],
        ),
        target_identity_id=target_identity_id,
        target_kind=target_kind,
        artifact_observations=observations,
    )


def test_service_auto_links_exact_near_unique_and_strong_artifact_convergence() -> None:
    left = _fingerprint(
        "project-left",
        [
            _observation(
                "left-apn",
                IdentityArtifactType.APN,
                "0292-123-45",
                source_family="ceqanet",
                evidence_record_id="ev-left-apn",
            ),
            _observation(
                "left-address",
                IdentityArtifactType.EXACT_SITE_ADDRESS,
                "123 main st fontana ca",
                source_family="agenda_packet",
                evidence_record_id="ev-left-address",
            ),
            _observation(
                "left-title",
                IdentityArtifactType.PROJECT_TITLE,
                "commerce center ii",
                source_family="agenda_packet",
                evidence_record_id="ev-left-title",
            ),
        ],
    )
    right = _fingerprint(
        "project-right",
        [
            _observation(
                "right-apn",
                IdentityArtifactType.APN,
                "0292-123-45",
                source_family="permit_portal",
                evidence_record_id="ev-right-apn",
            ),
            _observation(
                "right-address",
                IdentityArtifactType.EXACT_SITE_ADDRESS,
                "123 main st fontana ca",
                source_family="permit_portal",
                evidence_record_id="ev-right-address",
            ),
            _observation(
                "right-title",
                IdentityArtifactType.PROJECT_TITLE,
                "commerce center ii",
                source_family="ceqanet",
                evidence_record_id="ev-right-title",
            ),
        ],
    )

    candidate = ArtifactResolutionService().resolve_fingerprints(left, right)

    assert candidate.left_identity_id == "project-left"
    assert candidate.right_identity_id == "project-right"
    assert candidate.resolution_score == 98
    assert candidate.recommended_decision == ResolutionDecisionType.AUTO_LINK
    assert {match.artifact_type for match in candidate.supporting_matches} == {
        IdentityArtifactType.APN,
        IdentityArtifactType.EXACT_SITE_ADDRESS,
        IdentityArtifactType.PROJECT_TITLE,
    }
    apn_match = next(
        match
        for match in candidate.supporting_matches
        if match.artifact_type == IdentityArtifactType.APN
    )
    assert apn_match.source_families == ["ceqanet", "permit_portal"]
    assert apn_match.evidence_record_ids == ["ev-left-apn", "ev-right-apn"]


def test_service_queues_followup_search_when_only_weak_artifact_matches() -> None:
    left = _fingerprint(
        "project-left",
        [
            _observation(
                "left-word",
                IdentityArtifactType.GENERIC_PROJECT_WORD,
                "warehouse",
                evidence_record_id="ev-left",
            )
        ],
    )
    right = _fingerprint(
        "project-right",
        [
            _observation(
                "right-word",
                IdentityArtifactType.GENERIC_PROJECT_WORD,
                "warehouse",
                evidence_record_id="ev-right",
            )
        ],
    )

    candidate = ArtifactResolutionService().resolve_fingerprints(left, right)

    assert candidate.has_only_weak_support is True
    assert candidate.recommended_decision == ResolutionDecisionType.QUEUE_FOLLOWUP_SEARCH
    assert candidate.supporting_matches[0].tier == ArtifactTier.WEAK_ASSISTIVE
    assert candidate.supporting_matches[0].match_strength == 80


def test_service_rejects_conflicting_ceqa_sch_numbers_without_support() -> None:
    left = _fingerprint(
        "project-left",
        [
            _observation(
                "left-sch",
                IdentityArtifactType.CEQA_SCH_NUMBER,
                "sch-2025060123",
                evidence_record_id="ev-left-sch",
            )
        ],
    )
    right = _fingerprint(
        "project-right",
        [
            _observation(
                "right-sch",
                IdentityArtifactType.CEQA_SCH_NUMBER,
                "sch-2025999999",
                evidence_record_id="ev-right-sch",
            )
        ],
    )

    candidate = ArtifactResolutionService().resolve_fingerprints(left, right)

    assert candidate.supporting_matches == []
    assert len(candidate.conflicts) == 1
    assert candidate.conflicts[0].conflict_strength == 100
    assert candidate.has_near_unique_conflict is True
    assert candidate.recommended_decision == ResolutionDecisionType.REJECT_MATCH


def test_service_treats_different_apns_as_moderate_conflict_not_hard_rejection() -> None:
    left = _fingerprint(
        "project-left",
        [
            _observation(
                "left-apn",
                IdentityArtifactType.APN,
                "0292-123-45",
                evidence_record_id="ev-left-apn",
            )
        ],
    )
    right = _fingerprint(
        "project-right",
        [
            _observation(
                "right-apn",
                IdentityArtifactType.APN,
                "0292-999-99",
                evidence_record_id="ev-right-apn",
            )
        ],
    )

    candidate = ArtifactResolutionService().resolve_fingerprints(left, right)

    assert candidate.conflicts[0].artifact_type == IdentityArtifactType.APN
    assert candidate.conflicts[0].conflict_strength == 70
    assert candidate.has_near_unique_conflict is False
    assert candidate.recommended_decision == ResolutionDecisionType.CREATE_NEW_IDENTITY


def test_service_does_not_conflict_when_same_artifact_type_has_any_overlap() -> None:
    left = _fingerprint(
        "project-left",
        [
            _observation("left-apn-1", IdentityArtifactType.APN, "0292-123-45"),
            _observation("left-apn-2", IdentityArtifactType.APN, "0292-123-46"),
        ],
    )
    right = _fingerprint(
        "project-right",
        [
            _observation("right-apn-1", IdentityArtifactType.APN, "0292-123-45"),
            _observation("right-apn-2", IdentityArtifactType.APN, "0292-999-99"),
        ],
    )

    candidate = ArtifactResolutionService().resolve_fingerprints(left, right)

    assert [match.artifact_type for match in candidate.supporting_matches] == [
        IdentityArtifactType.APN
    ]
    assert candidate.conflicts == []


def test_service_does_not_treat_different_permit_numbers_as_project_conflicts() -> None:
    left = _fingerprint(
        "project-left",
        [_observation("left-permit", IdentityArtifactType.PERMIT_NUMBER, "bld2025-001")],
    )
    right = _fingerprint(
        "project-right",
        [_observation("right-permit", IdentityArtifactType.PERMIT_NUMBER, "bld2025-002")],
    )

    with pytest.raises(ValueError, match="no comparable identity artifacts"):
        ArtifactResolutionService().resolve_fingerprints(left, right)

    assert can_artifact_type_conflict(IdentityArtifactType.PERMIT_NUMBER) is False


def test_service_rejects_same_identity_and_different_target_kinds() -> None:
    service = ArtifactResolutionService()
    left = _fingerprint(
        "project-same",
        [_observation("left-apn", IdentityArtifactType.APN, "0292-123-45")],
    )
    same_target = _fingerprint(
        "project-same",
        [_observation("right-apn", IdentityArtifactType.APN, "0292-123-45")],
    )
    different_kind = _fingerprint(
        "site-target",
        [_observation("site-apn", IdentityArtifactType.APN, "0292-123-45")],
        target_kind=ResolutionTargetKind.SITE,
    )

    with pytest.raises(ValueError, match="same target identity"):
        service.resolve_fingerprints(left, same_target)

    with pytest.raises(ValueError, match="different target kinds"):
        service.resolve_fingerprints(left, different_kind)


def test_convenience_wrapper_uses_service_resolution() -> None:
    left = _fingerprint(
        "project-left",
        [_observation("left-title", IdentityArtifactType.PROJECT_TITLE, "commerce center ii")],
    )
    right = _fingerprint(
        "project-right",
        [_observation("right-title", IdentityArtifactType.PROJECT_TITLE, "commerce center ii")],
    )

    expected_id = canonical_resolution_candidate_id(
        "project-left",
        "project-right",
        target_kind=ResolutionTargetKind.PROJECT,
    )
    candidate = resolve_identity_fingerprints(
        left,
        right,
        candidate_id=expected_id,
    )

    assert candidate.candidate_id == expected_id
    assert candidate.supporting_matches[0].artifact_type == IdentityArtifactType.PROJECT_TITLE
    assert candidate.recommended_decision == ResolutionDecisionType.CREATE_NEW_IDENTITY


def test_service_reports_no_comparable_artifacts() -> None:
    left = _fingerprint(
        "project-left",
        [_observation("left-title", IdentityArtifactType.PROJECT_TITLE, "commerce center ii")],
    )
    right = _fingerprint(
        "project-right",
        [_observation("right-apn", IdentityArtifactType.APN, "0292-123-45")],
    )

    with pytest.raises(ValueError, match="no comparable identity artifacts"):
        ArtifactResolutionService().resolve_fingerprints(left, right)
