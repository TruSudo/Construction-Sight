from __future__ import annotations

import pytest
from pydantic import ValidationError

from constructionsight.contractor_identity_models import (
    ContractorIdentity,
    canonical_contractor_key,
)
from constructionsight.domain_types import confidence_band
from constructionsight.intelligence.artifact_identity import (
    ArtifactObservation,
    IdentityArtifactType,
    IdentityFingerprint,
    ResolutionTargetKind,
    canonical_artifact_observation_id,
    canonical_identity_fingerprint_id,
    canonical_resolution_candidate_id,
    normalize_artifact_value,
)
from constructionsight.intelligence.artifact_resolution_service import (
    ArtifactResolutionService,
)
from constructionsight.lead_dedupe_models import (
    LeadFingerprint,
    canonical_lead_fingerprint_key,
    normalize_lead_title_value,
)


def test_lead_fingerprint_rejects_forged_normalization_and_stale_key() -> None:
    raw_title = "Warehouse Phase II"
    normalized = normalize_lead_title_value(raw_title)
    valid_key = canonical_lead_fingerprint_key(
        site_key="site:1",
        source_key=None,
        source_record_id=None,
        normalized_title=normalized,
    )

    with pytest.raises(ValidationError, match="normalized_title"):
        LeadFingerprint(
            fingerprint_key=valid_key,
            base_candidate_id="candidate:1",
            site_key="site:1",
            raw_title=raw_title,
            normalized_title="FORGED TITLE",
        )

    stale_key = canonical_lead_fingerprint_key(
        site_key="site:stale",
        source_key=None,
        source_record_id=None,
        normalized_title=normalized,
    )
    with pytest.raises(ValidationError, match="fingerprint_key"):
        LeadFingerprint(
            fingerprint_key=stale_key,
            base_candidate_id="candidate:1",
            site_key="site:1",
            raw_title=raw_title,
            normalized_title=normalized,
        )


def test_contractor_identity_rejects_forged_normalized_name_and_stale_key() -> None:
    valid_key = canonical_contractor_key(
        normalized_name="ACME BUILDERS",
        license_number=None,
        contractor_group_key=None,
    )

    with pytest.raises(ValidationError, match="normalized_name"):
        ContractorIdentity(
            contractor_key=valid_key,
            display_name="Acme Builders",
            normalized_name="FORGED BUILDERS",
            confidence_score=35,
            confidence_band=confidence_band(35),
        )

    stale_key = canonical_contractor_key(
        normalized_name="OTHER BUILDER",
        license_number=None,
        contractor_group_key=None,
    )
    with pytest.raises(ValidationError, match="contractor_key"):
        ContractorIdentity(
            contractor_key=stale_key,
            display_name="Acme Builders",
            normalized_name="ACME BUILDERS",
            confidence_score=35,
            confidence_band=confidence_band(35),
        )


def _observation(
    *,
    source_name: str,
    evidence_record_id: str,
) -> ArtifactObservation:
    artifact_type = IdentityArtifactType.PROJECT_TITLE
    raw_value = "Commerce Center II"
    normalized = normalize_artifact_value(artifact_type, raw_value)
    return ArtifactObservation(
        observation_id=canonical_artifact_observation_id(
            artifact_type=artifact_type,
            normalized_value=normalized,
            source_name=source_name,
            source_family="synthetic",
            source_record_id=None,
            jurisdiction=None,
            observed_field="title",
            evidence_record_id=evidence_record_id,
        ),
        artifact_type=artifact_type,
        raw_value=raw_value,
        normalized_value=normalized,
        source_name=source_name,
        source_family="synthetic",
        observed_field="title",
        evidence_record_id=evidence_record_id,
        confidence_score=75,
    )


def _fingerprint(target_identity_id: str, observation: ArtifactObservation) -> IdentityFingerprint:
    return IdentityFingerprint(
        fingerprint_id=canonical_identity_fingerprint_id(
            target_identity_id=target_identity_id,
            target_kind=ResolutionTargetKind.PROJECT,
            observation_ids=[observation.observation_id],
            evidence_record_ids=[observation.evidence_record_id or ""],
        ),
        target_identity_id=target_identity_id,
        artifact_observations=[observation],
        evidence_record_ids=[observation.evidence_record_id or ""],
    )


def test_artifact_observation_and_fingerprint_reject_forged_derived_state() -> None:
    artifact_type = IdentityArtifactType.APN
    raw_value = "APN 0292-123-45"
    canonical = normalize_artifact_value(artifact_type, raw_value)
    forged = "9999-999-99"
    forged_id = canonical_artifact_observation_id(
        artifact_type=artifact_type,
        normalized_value=forged,
        source_name="County",
        source_family="assessor",
        source_record_id="record:1",
        jurisdiction="San Bernardino",
        observed_field="apn",
        evidence_record_id="evidence:1",
    )
    with pytest.raises(ValidationError, match="normalized_value"):
        ArtifactObservation(
            observation_id=forged_id,
            artifact_type=artifact_type,
            raw_value=raw_value,
            normalized_value=forged,
            source_name="County",
            source_family="assessor",
            source_record_id="record:1",
            jurisdiction="San Bernardino",
            observed_field="apn",
            evidence_record_id="evidence:1",
        )

    observation = ArtifactObservation(
        observation_id=canonical_artifact_observation_id(
            artifact_type=artifact_type,
            normalized_value=canonical,
            source_name="County",
            source_family="assessor",
            source_record_id="record:1",
            jurisdiction="San Bernardino",
            observed_field="apn",
            evidence_record_id="evidence:1",
        ),
        artifact_type=artifact_type,
        raw_value=raw_value,
        normalized_value=canonical,
        source_name="County",
        source_family="assessor",
        source_record_id="record:1",
        jurisdiction="San Bernardino",
        observed_field="apn",
        evidence_record_id="evidence:1",
    )
    with pytest.raises(ValidationError, match="fingerprint_id"):
        IdentityFingerprint(
            fingerprint_id="identity-fingerprint:v2:" + ("0" * 64),
            target_identity_id="project:1",
            artifact_observations=[observation],
        )


def test_resolution_candidate_identity_is_symmetric_and_rejects_stale_override() -> None:
    left = _fingerprint("project:a", _observation(source_name="Source A", evidence_record_id="ev:a"))
    right = _fingerprint("project:b", _observation(source_name="Source B", evidence_record_id="ev:b"))
    service = ArtifactResolutionService()

    forward = service.resolve_fingerprints(left, right)
    reverse = service.resolve_fingerprints(right, left)

    expected = canonical_resolution_candidate_id(
        "project:a",
        "project:b",
        target_kind=ResolutionTargetKind.PROJECT,
    )
    assert forward.candidate_id == reverse.candidate_id == expected
    assert (forward.left_identity_id, forward.right_identity_id) == (
        "project:a",
        "project:b",
    )
    assert (reverse.left_identity_id, reverse.right_identity_id) == (
        "project:a",
        "project:b",
    )

    with pytest.raises(ValueError, match="candidate_id"):
        service.resolve_fingerprints(
            left,
            right,
            candidate_id="artifact-resolution:v2:" + ("0" * 64),
        )
