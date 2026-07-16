from __future__ import annotations

from datetime import UTC, datetime

import pytest

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.operator_services.parcel_arcgis_service import (
    execute_authorized_arcgis_probe,
    persist_authorized_arcgis_bundle,
)
from constructionsight.parcel_source_acquisition import (
    build_arcgis_probe_plan,
    get_official_arcgis_capability_snapshots,
    parse_arcgis_probe_observation,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbeKind,
    ParcelArcGISProbeObservation,
    ParcelArcGISProbePlan,
)
from constructionsight.parcel_source_verification import (
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)
from constructionsight.parcel_source_verification_models import (
    ParcelSourceVerificationProfile,
)

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def _profile_and_evidence():
    profile = get_verified_parcel_source_profiles()[0]
    evidence_by_id = {item.evidence_id: item for item in get_parcel_source_evidence()}
    evidence = tuple(evidence_by_id[item] for item in profile.evidence_ids)
    return profile, evidence


def _probe_result(
    profile: ParcelSourceVerificationProfile,
    *,
    sample_size: int,
) -> tuple[
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbePlan,
    tuple[ParcelArcGISProbeObservation, ...],
]:
    snapshot = next(
        item
        for item in get_official_arcgis_capability_snapshots()
        if item.profile_id == profile.profile_id
    )
    plan = build_arcgis_probe_plan(
        snapshot,
        sample_size=sample_size,
        generated_at=_NOW,
    )
    payloads = {
        ParcelArcGISProbeKind.COUNT: {"count": 4},
        ParcelArcGISProbeKind.INITIAL_PAGE: {
            "features": [
                {"attributes": {snapshot.object_id_field: 1}},
                {"attributes": {snapshot.object_id_field: 2}},
            ],
            "exceededTransferLimit": True,
        },
        ParcelArcGISProbeKind.NEXT_PAGE: {
            "features": [
                {"attributes": {snapshot.object_id_field: 3}},
                {"attributes": {snapshot.object_id_field: 4}},
            ],
            "exceededTransferLimit": False,
        },
        ParcelArcGISProbeKind.REPLAY_PAGE: {
            "features": [
                {"attributes": {snapshot.object_id_field: 1}},
                {"attributes": {snapshot.object_id_field: 2}},
            ],
            "exceededTransferLimit": True,
        },
    }
    observations = tuple(
        parse_arcgis_probe_observation(
            request,
            payloads[request.kind],
            observed_at=_NOW,
        )
        for request in plan.requests
    )
    return snapshot, plan, observations


class _ProbeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, float]] = []

    def __call__(
        self,
        profile: ParcelSourceVerificationProfile,
        *,
        sample_size: int,
        timeout_seconds: float,
    ) -> tuple[
        ParcelArcGISCapabilitySnapshot,
        ParcelArcGISProbePlan,
        tuple[ParcelArcGISProbeObservation, ...],
    ]:
        self.calls.append((profile.source_key, sample_size, timeout_seconds))
        return _probe_result(profile, sample_size=sample_size)


class _Persister:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, bundle, database_url: str | None) -> None:
        self.calls.append((bundle.bundle_id, database_url))


def _execute_probe(
    executor: _ProbeExecutor,
    *,
    confirmation: bool = True,
    ledger: AuthorizationUseLedger | None = None,
):
    profile, evidence = _profile_and_evidence()
    return execute_authorized_arcgis_probe(
        profile=profile,
        source_evidence=evidence,
        sample_size=2,
        timeout_seconds=30.0,
        authorization_reason="Execute one reviewed bounded ArcGIS proof.",
        caller_confirmation=confirmation,
        operator_id="operator:tyler",
        now=lambda: _NOW,
        ledger=ledger,
        executor=executor,
    )


def test_probe_service_binds_scope_and_denies_bulk_authority() -> None:
    executor = _ProbeExecutor()

    result = _execute_probe(executor)

    authorization = result.authorization.to_dict()
    assert authorization["action"] == "execute-parcel-arcgis-bounded-probe"
    assert "bulk acquisition" in authorization["denied_authority"]
    assert "geometry acquisition" in authorization["denied_authority"]
    assert result.bundle.bulk_run_authorized is False
    assert executor.calls == [(result.bundle.source_key, 2, 30.0)]


def test_boolean_confirmation_cannot_authorize_probe() -> None:
    executor = _ProbeExecutor()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _execute_probe(executor, confirmation=False)

    assert executor.calls == []


def test_shared_ledger_rejects_repeated_probe() -> None:
    executor = _ProbeExecutor()
    ledger = AuthorizationUseLedger()

    first = _execute_probe(executor, ledger=ledger)
    assert first.bundle.bundle_id
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _execute_probe(executor, ledger=ledger)

    assert len(executor.calls) == 1


def test_persistence_requires_exact_bundle_identity_and_scope_bound_authority() -> None:
    result = _execute_probe(_ProbeExecutor())
    persister = _Persister()

    persisted = persist_authorized_arcgis_bundle(
        bundle=result.bundle,
        expected_bundle_id=result.bundle.bundle_id,
        database_url="sqlite+pysqlite:///:memory:",
        authorization_reason="Persist one reviewed bounded proof bundle.",
        caller_confirmation=True,
        operator_id="operator:tyler",
        now=lambda: _NOW,
        persister=persister,
    )

    authorization = persisted.authorization.to_dict()
    assert authorization["action"] == "persist-parcel-arcgis-bounded-proof"
    assert "destructive overwrite" in authorization["denied_authority"]
    assert persisted.receipt.bundle_id == result.bundle.bundle_id
    assert persisted.receipt.bulk_run_authorized is False
    assert persister.calls == [(result.bundle.bundle_id, "sqlite+pysqlite:///:memory:")]


def test_persistence_rejects_identity_substitution_before_write() -> None:
    result = _execute_probe(_ProbeExecutor())
    persister = _Persister()

    with pytest.raises(AuthorizationDeniedError, match="does not match"):
        persist_authorized_arcgis_bundle(
            bundle=result.bundle,
            expected_bundle_id="parcel-arcgis-bounded-proof-bundle:" + ("0" * 64),
            database_url=None,
            authorization_reason="Attempt a mismatched persistence operation.",
            caller_confirmation=True,
            operator_id="operator:tyler",
            now=lambda: _NOW,
            persister=persister,
        )

    assert persister.calls == []
