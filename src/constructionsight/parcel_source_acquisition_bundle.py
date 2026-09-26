"""Build and independently verify portable bounded ArcGIS proof bundles."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_probe_plan,
)
from constructionsight.parcel_source_acquisition_bundle_models import (
    ParcelArcGISBoundedProofBundle,
    ParcelArcGISBoundedProofVerification,
    ParcelArcGISProofPersistenceReceipt,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionAssessment,
    ParcelArcGISAcquisitionStatus,
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbeObservation,
    ParcelArcGISProbePlan,
    digest_identity,
)
from constructionsight.parcel_source_verification_models import (
    ParcelSourceEvidence,
    ParcelSourceVerificationProfile,
)

_DEFAULT_LIMITATIONS = (
    "A bounded proof cannot authorize or establish complete parcel acquisition.",
    "A subsequent complete rehearsal requires separate checkpoints and authorization.",
    "The bundle proves only the exact metadata and four response payloads it contains.",
)


def build_arcgis_bounded_proof_bundle(
    profile: ParcelSourceVerificationProfile,
    source_evidence: Iterable[ParcelSourceEvidence],
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISProbePlan,
    observations: Iterable[ParcelArcGISProbeObservation],
    assessment: ParcelArcGISAcquisitionAssessment,
    *,
    limitations: tuple[str, ...] = _DEFAULT_LIMITATIONS,
    created_at: datetime | None = None,
) -> ParcelArcGISBoundedProofBundle:
    """Bind one complete bounded proof chain into a portable immutable artifact."""

    canonical_evidence = tuple(
        sorted(source_evidence, key=lambda item: item.evidence_id)
    )
    reviewed_observations = tuple(observations)
    if len(reviewed_observations) != len(plan.requests):
        raise ValueError("ArcGIS bounded proof requires one observation per request")
    observation_by_request = {
        observation.request_id: observation for observation in reviewed_observations
    }
    if len(observation_by_request) != len(reviewed_observations):
        raise ValueError("ArcGIS bounded proof rejects duplicate request observations")
    try:
        canonical_observations = tuple(
            observation_by_request[request.request_id] for request in plan.requests
        )
    except KeyError as exc:
        raise ValueError(
            "ArcGIS bounded proof requires every planned request observation"
        ) from exc
    rebuilt_plan = build_arcgis_probe_plan(
        snapshot,
        sample_size=plan.sample_size,
        generated_at=plan.generated_at,
    )
    if rebuilt_plan != plan:
        raise ValueError("ArcGIS bounded-proof plan failed independent recomputation")
    rebuilt_assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        canonical_observations,
        generated_at=assessment.generated_at,
    )
    if rebuilt_assessment != assessment:
        raise ValueError("ArcGIS bounded-proof assessment failed independent recomputation")
    canonical_limitations = tuple(sorted(set(limitations), key=str.casefold))
    candidate = ParcelArcGISBoundedProofBundle.model_construct(
        bundle_id="parcel-arcgis-bounded-proof-bundle:" + ("0" * 64),
        source_key=profile.source_key,
        county=profile.county,
        profile=profile,
        source_evidence=canonical_evidence,
        snapshot=snapshot,
        plan=plan,
        observations=canonical_observations,
        assessment=assessment,
        network_request_count=1 + len(plan.requests),
        bulk_run_authorized=False,
        limitations=canonical_limitations,
        created_at=created_at or datetime.now(UTC),
    )
    payload = candidate.model_dump(mode="json", exclude={"bundle_id", "created_at"})
    return ParcelArcGISBoundedProofBundle.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "bundle_id": digest_identity(
                "parcel-arcgis-bounded-proof-bundle",
                payload,
            ),
        }
    )


def verify_arcgis_bounded_proof_bundle(
    bundle: ParcelArcGISBoundedProofBundle,
    *,
    verified_at: datetime | None = None,
) -> ParcelArcGISBoundedProofVerification:
    """Recompute every derived bounded-proof component without network access."""

    rebuilt = build_arcgis_bounded_proof_bundle(
        bundle.profile,
        bundle.source_evidence,
        bundle.snapshot,
        bundle.plan,
        bundle.observations,
        bundle.assessment,
        limitations=bundle.limitations,
        created_at=bundle.created_at,
    )
    if rebuilt != bundle:
        raise ValueError("ArcGIS bounded-proof bundle failed independent recomputation")
    if bundle.assessment.status == ParcelArcGISAcquisitionStatus.BLOCKED:
        next_action = (
            "retain the failed bounded proof and resolve its explicit assessment gaps "
            "before another probe"
        )
    else:
        next_action = (
            "persist the verified bounded proof and design a separately controlled "
            "complete rehearsal"
        )
    candidate = ParcelArcGISBoundedProofVerification.model_construct(
        verification_id="parcel-arcgis-bounded-proof-verification:" + ("0" * 64),
        bundle_id=bundle.bundle_id,
        source_key=bundle.source_key,
        county=bundle.county,
        status=bundle.assessment.status,
        assessment_id=bundle.assessment.assessment_id,
        evidence_count=len(bundle.source_evidence),
        observation_count=len(bundle.observations),
        network_request_count=bundle.network_request_count,
        assessment_recomputed=True,
        response_digests_recomputed=True,
        valid=True,
        bulk_run_authorized=False,
        next_action=next_action,
        verified_at=verified_at or datetime.now(UTC),
    )
    payload = candidate.model_dump(
        mode="json",
        exclude={"verification_id", "verified_at"},
    )
    return ParcelArcGISBoundedProofVerification.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "verification_id": digest_identity(
                "parcel-arcgis-bounded-proof-verification",
                payload,
            ),
        }
    )


def build_arcgis_proof_persistence_receipt(
    bundle: ParcelArcGISBoundedProofBundle,
    *,
    persisted_at: datetime | None = None,
) -> ParcelArcGISProofPersistenceReceipt:
    """Build a receipt after an authorized transactional bundle write."""

    verify_arcgis_bounded_proof_bundle(bundle)
    candidate = ParcelArcGISProofPersistenceReceipt.model_construct(
        receipt_id="parcel-arcgis-proof-persistence:" + ("0" * 64),
        bundle_id=bundle.bundle_id,
        source_key=bundle.source_key,
        county=bundle.county,
        profile_id=bundle.profile.profile_id,
        snapshot_id=bundle.snapshot.snapshot_id,
        plan_id=bundle.plan.plan_id,
        observation_ids=tuple(
            sorted(item.observation_id for item in bundle.observations)
        ),
        assessment_id=bundle.assessment.assessment_id,
        evidence_count=len(bundle.source_evidence),
        mutation_authorized=True,
        replay_policy="insert_or_exact_replay",
        bulk_run_authorized=False,
        persisted_at=persisted_at or datetime.now(UTC),
    )
    payload = candidate.model_dump(mode="json", exclude={"receipt_id"})
    return ParcelArcGISProofPersistenceReceipt.model_validate(
        {
            **payload,
            "receipt_id": digest_identity(
                "parcel-arcgis-proof-persistence",
                payload,
            ),
        }
    )
