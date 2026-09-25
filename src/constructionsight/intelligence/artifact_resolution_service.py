"""Deterministic artifact-based identity resolution service.

This service compares two identity fingerprints and produces a governed
IdentityResolutionCandidate. It is intentionally pure and side-effect free:
it does not persist, merge, mutate graph state, run source searches, or call
AI/API systems.
"""

from __future__ import annotations

from collections import defaultdict

from constructionsight.intelligence.artifact_identity import (
    ArtifactConflict,
    ArtifactMatch,
    ArtifactObservation,
    ArtifactTier,
    IdentityArtifactType,
    IdentityFingerprint,
    IdentityResolutionCandidate,
    artifact_tier,
    canonical_resolution_candidate_id,
)

ObservationGroup = dict[IdentityArtifactType, list[ArtifactObservation]]

CONFLICT_STRENGTH_BY_TYPE: dict[IdentityArtifactType, int] = {
    IdentityArtifactType.CEQA_SCH_NUMBER: 100,
    IdentityArtifactType.PARCEL_GEOMETRY: 95,
    IdentityArtifactType.PLANNING_CASE_NUMBER: 85,
    IdentityArtifactType.EXACT_SITE_ADDRESS: 80,
    IdentityArtifactType.LEGAL_DESCRIPTION: 75,
    IdentityArtifactType.APN: 70,
    IdentityArtifactType.TRACT_MAP_NUMBER: 70,
}

NON_CONFLICTING_RECORD_IDENTIFIERS: set[IdentityArtifactType] = {
    IdentityArtifactType.PERMIT_NUMBER,
}


class ArtifactResolutionService:
    """Compare identity fingerprints using governed artifact rules."""

    def resolve_fingerprints(
        self,
        left: IdentityFingerprint,
        right: IdentityFingerprint,
        *,
        candidate_id: str | None = None,
    ) -> IdentityResolutionCandidate:
        """Return an artifact-driven candidate resolution between two fingerprints."""

        if left.target_identity_id == right.target_identity_id:
            raise ValueError("cannot resolve a fingerprint against the same target identity")
        if left.target_kind != right.target_kind:
            raise ValueError("cannot resolve fingerprints with different target kinds")

        if left.target_identity_id > right.target_identity_id:
            left, right = right, left

        supporting_matches = self.find_matches(left, right)
        conflicts = self.find_conflicts(left, right, supporting_matches)

        if not supporting_matches and not conflicts:
            raise ValueError("fingerprints have no comparable identity artifacts")

        return IdentityResolutionCandidate(
            candidate_id=self._validated_candidate_id(
                candidate_id,
                left.target_identity_id,
                right.target_identity_id,
                target_kind=left.target_kind,
            ),
            left_identity_id=left.target_identity_id,
            right_identity_id=right.target_identity_id,
            target_kind=left.target_kind,
            supporting_matches=supporting_matches,
            conflicts=conflicts,
            evidence_summary=self.build_evidence_summary(supporting_matches, conflicts),
            review_required=True,
        )

    def find_matches(
        self,
        left: IdentityFingerprint,
        right: IdentityFingerprint,
    ) -> list[ArtifactMatch]:
        """Return exact normalized artifact matches between two fingerprints."""

        left_grouped = self.group_by_artifact_type(left.artifact_observations)
        right_grouped = self.group_by_artifact_type(right.artifact_observations)

        matches: list[ArtifactMatch] = []
        comparable_artifact_types = sorted(
            set(left_grouped) & set(right_grouped),
            key=lambda item: item.value,
        )
        for artifact_type in comparable_artifact_types:
            left_by_value = self.group_by_normalized_value(left_grouped[artifact_type])
            right_by_value = self.group_by_normalized_value(right_grouped[artifact_type])

            for normalized_value in sorted(set(left_by_value) & set(right_by_value)):
                left_observations = left_by_value[normalized_value]
                right_observations = right_by_value[normalized_value]
                left_primary = self.primary_observation(left_observations)
                right_primary = self.primary_observation(right_observations)

                matches.append(
                    ArtifactMatch(
                        artifact_type=artifact_type,
                        left_observation_id=left_primary.observation_id,
                        right_observation_id=right_primary.observation_id,
                        left_value=normalized_value,
                        right_value=normalized_value,
                        match_strength=self.match_strength_for(artifact_type),
                        source_families=self.collect_source_families(
                            left_observations + right_observations
                        ),
                        evidence_record_ids=self.collect_evidence_record_ids(
                            left_observations + right_observations
                        ),
                        explanation=self.match_explanation(artifact_type, normalized_value),
                    )
                )

        return matches

    def find_conflicts(
        self,
        left: IdentityFingerprint,
        right: IdentityFingerprint,
        supporting_matches: list[ArtifactMatch],
    ) -> list[ArtifactConflict]:
        """Return safe artifact conflicts without treating aliases as contradictions."""

        left_grouped = self.group_by_artifact_type(left.artifact_observations)
        right_grouped = self.group_by_artifact_type(right.artifact_observations)
        matched_types = {match.artifact_type for match in supporting_matches}

        conflicts: list[ArtifactConflict] = []
        comparable_artifact_types = sorted(
            set(left_grouped) & set(right_grouped),
            key=lambda item: item.value,
        )
        for artifact_type in comparable_artifact_types:
            if artifact_type in matched_types:
                continue
            if artifact_type in NON_CONFLICTING_RECORD_IDENTIFIERS:
                continue
            conflict_strength = CONFLICT_STRENGTH_BY_TYPE.get(artifact_type)
            if conflict_strength is None:
                continue

            left_value = self.primary_observation(left_grouped[artifact_type]).normalized_value
            right_value = self.primary_observation(right_grouped[artifact_type]).normalized_value
            if left_value == right_value:
                continue

            conflicts.append(
                ArtifactConflict(
                    artifact_type=artifact_type,
                    left_value=left_value,
                    right_value=right_value,
                    conflict_strength=conflict_strength,
                    evidence_record_ids=self.collect_evidence_record_ids(
                        left_grouped[artifact_type] + right_grouped[artifact_type]
                    ),
                    explanation=self.conflict_explanation(
                        artifact_type,
                        left_value,
                        right_value,
                        conflict_strength,
                    ),
                )
            )

        return conflicts

    @staticmethod
    def default_candidate_id(
        left_identity_id: str,
        right_identity_id: str,
        *,
        target_kind: ResolutionTargetKind = ResolutionTargetKind.PROJECT,
    ) -> str:
        """Return the canonical symmetric candidate ID for a fingerprint comparison."""

        return canonical_resolution_candidate_id(
            left_identity_id,
            right_identity_id,
            target_kind=target_kind,
        )

    @classmethod
    def _validated_candidate_id(
        cls,
        candidate_id: str | None,
        left_identity_id: str,
        right_identity_id: str,
        *,
        target_kind: ResolutionTargetKind,
    ) -> str:
        expected = cls.default_candidate_id(
            left_identity_id,
            right_identity_id,
            target_kind=target_kind,
        )
        if candidate_id is not None and candidate_id != expected:
            raise ValueError("caller candidate_id does not match canonical identity pair")
        return expected

    @staticmethod
    def group_by_artifact_type(observations: list[ArtifactObservation]) -> ObservationGroup:
        """Group observations by artifact type."""

        grouped: defaultdict[IdentityArtifactType, list[ArtifactObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.artifact_type].append(observation)
        return dict(grouped)

    @staticmethod
    def group_by_normalized_value(
        observations: list[ArtifactObservation],
    ) -> dict[str, list[ArtifactObservation]]:
        """Group observations by normalized artifact value."""

        grouped: defaultdict[str, list[ArtifactObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.normalized_value].append(observation)
        return dict(grouped)

    @staticmethod
    def primary_observation(observations: list[ArtifactObservation]) -> ArtifactObservation:
        """Return deterministic primary observation from a non-empty list."""

        if not observations:
            raise ValueError("primary observation requires at least one observation")
        return sorted(observations, key=lambda observation: observation.observation_id)[0]

    @staticmethod
    def collect_source_families(observations: list[ArtifactObservation]) -> list[str]:
        """Return sorted unique source families for observations."""

        return sorted(
            {
                observation.source_family
                for observation in observations
                if observation.source_family is not None
            }
        )

    @staticmethod
    def collect_evidence_record_ids(observations: list[ArtifactObservation]) -> list[str]:
        """Return sorted unique evidence record IDs for observations."""

        return sorted(
            {
                observation.evidence_record_id
                for observation in observations
                if observation.evidence_record_id is not None
            }
        )

    @staticmethod
    def match_strength_for(artifact_type: IdentityArtifactType) -> int:
        """Return match strength for an exact normalized artifact match."""

        if artifact_tier(artifact_type) == ArtifactTier.WEAK_ASSISTIVE:
            return 80
        return 100

    @staticmethod
    def match_explanation(artifact_type: IdentityArtifactType, normalized_value: str) -> str:
        """Return a deterministic match explanation."""

        return (
            f"Both fingerprints contain exact normalized {artifact_type.value} "
            f"artifact value {normalized_value!r}."
        )

    @staticmethod
    def conflict_explanation(
        artifact_type: IdentityArtifactType,
        left_value: str,
        right_value: str,
        conflict_strength: int,
    ) -> str:
        """Return a deterministic conflict explanation."""

        return (
            f"Both fingerprints contain {artifact_type.value} artifacts, but the "
            f"normalized values differ: {left_value!r} versus {right_value!r}. "
            f"Conflict strength is {conflict_strength}."
        )

    @staticmethod
    def build_evidence_summary(
        supporting_matches: list[ArtifactMatch],
        conflicts: list[ArtifactConflict],
    ) -> str:
        """Return a concise evidence summary for the candidate."""

        match_types = sorted({match.artifact_type.value for match in supporting_matches})
        conflict_types = sorted({conflict.artifact_type.value for conflict in conflicts})
        if match_types and conflict_types:
            return (
                "Artifact comparison found support from "
                f"{', '.join(match_types)} and conflicts from {', '.join(conflict_types)}."
            )
        if match_types:
            return f"Artifact comparison found support from {', '.join(match_types)}."
        return f"Artifact comparison found conflicts from {', '.join(conflict_types)}."


def resolve_identity_fingerprints(
    left: IdentityFingerprint,
    right: IdentityFingerprint,
    *,
    candidate_id: str | None = None,
) -> IdentityResolutionCandidate:
    """Convenience wrapper for one-off fingerprint resolution."""

    return ArtifactResolutionService().resolve_fingerprints(
        left,
        right,
        candidate_id=candidate_id,
    )


def can_artifact_type_conflict(artifact_type: IdentityArtifactType) -> bool:
    """Return true when a differing artifact type can safely create a conflict."""

    return (
        artifact_type in CONFLICT_STRENGTH_BY_TYPE
        and artifact_type not in NON_CONFLICTING_RECORD_IDENTIFIERS
    )
