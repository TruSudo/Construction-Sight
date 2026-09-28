"""Scope-bound application services for ArcGIS probe and proof persistence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
)
from constructionsight.parcel_source_acquisition_bundle import (
    build_arcgis_bounded_proof_bundle,
    build_arcgis_proof_persistence_receipt,
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_bundle_models import (
    ParcelArcGISBoundedProofBundle,
    ParcelArcGISProofPersistenceReceipt,
)
from constructionsight.parcel_source_acquisition_http import (
    ParcelArcGISProbeExecutionError,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionAssessment,
)
from constructionsight.parcel_source_probe_http import execute_arcgis_bounded_probe
from constructionsight.parcel_source_verification_models import (
    ParcelSourceEvidence,
    ParcelSourceVerificationProfile,
    ParcelSourceVerificationStatus,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.parcel_source_acquisition_bundle_store import (
    store_arcgis_bounded_proof_bundle_chain,
)

_PROBE_ACTION = "execute-parcel-arcgis-bounded-probe"
_PROBE_RESOURCE_TYPE = "verified-parcel-arcgis-source"
_PERSIST_ACTION = "persist-parcel-arcgis-bounded-proof"
_PERSIST_RESOURCE_TYPE = "parcel-arcgis-bounded-proof-bundle"
_PROBE_POLICY_ID = "CS-NET-004"
_MAX_SAMPLE_SIZE = 100
_MAX_TIMEOUT_SECONDS = 30.0


class ParcelArcGISOperatorServiceError(RuntimeError):
    """Raised when an authorized parcel operation fails after preflight."""


@dataclass(frozen=True)
class AuthorizedArcGISProbe:
    """One authorized bounded probe and its portable proof bundle."""

    assessment: ParcelArcGISAcquisitionAssessment
    bundle: ParcelArcGISBoundedProofBundle
    authorization: LocalAuthorizationResult


@dataclass(frozen=True)
class AuthorizedArcGISPersistence:
    """One authorized bundle persistence result."""

    receipt: ParcelArcGISProofPersistenceReceipt
    authorization: LocalAuthorizationResult


def _canonical_tuple(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=str.casefold))


def _persist_bundle(
    bundle: ParcelArcGISBoundedProofBundle,
    database_url: str | None,
) -> None:
    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        store_arcgis_bounded_proof_bundle_chain(session, bundle)


def execute_authorized_arcgis_probe(
    *,
    profile: ParcelSourceVerificationProfile,
    source_evidence: Iterable[ParcelSourceEvidence],
    sample_size: int,
    timeout_seconds: float,
    authorization_reason: str,
    caller_confirmation: bool,
    operator_id: str | None = None,
) -> AuthorizedArcGISProbe:
    """Authorize and execute one exact metadata/count/page/replay probe."""

    if profile.status is not ParcelSourceVerificationStatus.VERIFIED_PREVIEW:
        raise AuthorizationDeniedError(
            "ArcGIS probe requires a verified-preview source profile"
        )
    if not profile.public_access_verified:
        raise AuthorizationDeniedError(
            "ArcGIS probe requires independently verified public access"
        )
    if sample_size < 1 or sample_size > _MAX_SAMPLE_SIZE:
        raise ValueError("sample_size must be between 1 and 100")
    if timeout_seconds <= 0 or timeout_seconds > _MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout_seconds cannot exceed the CS-NET-004 ceiling")

    evidence = tuple(sorted(source_evidence, key=lambda item: item.evidence_id))
    if tuple(item.evidence_id for item in evidence) != profile.evidence_ids:
        raise ValueError("ArcGIS probe evidence does not match the verified profile")
    state_identity = authorization_digest(
        "parcel-arcgis-probe-state",
        {
            "profile": profile.model_dump(mode="json"),
            "evidence_ids": [item.evidence_id for item in evidence],
            "sample_size": sample_size,
            "timeout_seconds": timeout_seconds,
            "policy_id": _PROBE_POLICY_ID,
        },
    )
    exact_scope = _canonical_tuple(
        "concurrency:1",
        "geometry:false",
        f"policy:{_PROBE_POLICY_ID}",
        "request-count:5",
        f"sample-size:{sample_size}",
        f"source-key:{profile.source_key}",
        f"timeout-seconds:{timeout_seconds:g}",
    )
    authorization = authorize_local_operator_operation(
        action=_PROBE_ACTION,
        resource_type=_PROBE_RESOURCE_TYPE,
        resource_id=profile.profile_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "execute one exact metadata plus four-request read-only ArcGIS proof",
        ),
        denied_authority=_canonical_tuple(
            "access-control bypass",
            "bulk acquisition",
            "credential use",
            "geometry acquisition",
            "persistence mutation",
            "production recurrence",
            "profile promotion",
            "request expansion",
            "retry expansion",
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=_canonical_tuple(
            "local operator identity is not authentication",
            "probe evidence cannot establish countywide completeness",
            "probe evidence cannot authorize bulk acquisition or persistence",
            "one durable bounded-probe allowance across processes",
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )
    def execute(trusted_at: datetime) -> tuple[
        ParcelArcGISAcquisitionAssessment,
        ParcelArcGISBoundedProofBundle,
    ]:
        try:
            snapshot, plan, observations = execute_arcgis_bounded_probe(
                profile,
                sample_size=sample_size,
                timeout_seconds=timeout_seconds,
            )
            assessment = build_arcgis_acquisition_assessment(
                snapshot,
                plan,
                observations,
            )
            bundle = build_arcgis_bounded_proof_bundle(
                profile,
                evidence,
                snapshot,
                plan,
                observations,
                assessment,
                created_at=trusted_at,
            )
        except (ValueError, ParcelArcGISProbeExecutionError) as exc:
            raise ParcelArcGISOperatorServiceError(str(exc)) from exc
        return assessment, bundle

    assessment, bundle = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "parcel-arcgis-probe-manual-allowance",
            {"profile_id": profile.profile_id, "state_identity": state_identity},
        ),
        content_identity=state_identity,
        implementation_id=(
            "constructionsight.parcel_source_probe_http.execute_arcgis_bounded_probe"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda result: {
            "assessment": result[0].model_dump(mode="json"),
            "bundle": result[1].model_dump(mode="json"),
        },
        decode_result=lambda payload: (
            ParcelArcGISAcquisitionAssessment.model_validate(payload["assessment"]),
            ParcelArcGISBoundedProofBundle.model_validate(payload["bundle"]),
        ),
    )
    return AuthorizedArcGISProbe(
        assessment=assessment,
        bundle=bundle,
        authorization=authorization,
    )


def persist_authorized_arcgis_bundle(
    *,
    bundle: ParcelArcGISBoundedProofBundle,
    expected_bundle_id: str,
    database_url: str | None,
    authorization_reason: str,
    caller_confirmation: bool,
    operator_id: str | None = None,
) -> AuthorizedArcGISPersistence:
    """Authorize and persist one independently verified exact bundle chain."""

    verification = verify_arcgis_bounded_proof_bundle(bundle)
    if not verification.valid:
        raise AuthorizationDeniedError("ArcGIS bounded proof did not verify")
    if bundle.bundle_id != expected_bundle_id:
        raise AuthorizationDeniedError(
            "expected bundle identity does not match the verified artifact"
        )
    destination_identity = authorization_digest(
        "parcel-arcgis-persistence-destination",
        {"database_url": database_url or "default"},
    )
    state_identity = authorization_digest(
        "parcel-arcgis-persistence-state",
        {
            "bundle_id": bundle.bundle_id,
            "verification_id": verification.verification_id,
            "destination_identity": destination_identity,
        },
    )
    exact_scope = _canonical_tuple(
        f"bundle-id:{bundle.bundle_id}",
        f"destination:{destination_identity}",
        "operation:insert-or-exact-replay",
        "transaction:required",
    )
    authorization = authorize_local_operator_operation(
        action=_PERSIST_ACTION,
        resource_type=_PERSIST_RESOURCE_TYPE,
        resource_id=bundle.bundle_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "persist one exact verified bundle chain or identical replay",
        ),
        denied_authority=_canonical_tuple(
            "bulk acquisition",
            "destructive overwrite",
            "generic record editing",
            "identity substitution",
            "profile promotion",
            "production recurrence",
            "stale write",
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=_canonical_tuple(
            "database credentials are not granted by this decision",
            "local operator identity is not authentication",
            "persistence does not authorize acquisition or profile promotion",
            "one durable exact-bundle allowance across processes",
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )
    def persist(trusted_at: datetime) -> ParcelArcGISProofPersistenceReceipt:
        try:
            _persist_bundle(bundle, database_url)
            return build_arcgis_proof_persistence_receipt(
                bundle,
                persisted_at=trusted_at,
            )
        except ValueError as exc:
            raise ParcelArcGISOperatorServiceError(str(exc)) from exc

    receipt = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "parcel-arcgis-persistence-allowance",
            {
                "bundle_id": bundle.bundle_id,
                "destination_identity": destination_identity,
            },
        ),
        content_identity=state_identity,
        implementation_id=(
            "constructionsight.operator_services.parcel_arcgis_service._persist_bundle"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=persist,
        encode_result=lambda result: result.model_dump(mode="json"),
        decode_result=lambda payload: ParcelArcGISProofPersistenceReceipt.model_validate(payload),
    )
    return AuthorizedArcGISPersistence(
        receipt=receipt,
        authorization=authorization,
    )
