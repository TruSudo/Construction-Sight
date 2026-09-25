from __future__ import annotations

import inspect

import pytest

import constructionsight.source_verification_checklist_service as checklist_service
from constructionsight.adapters.specs import default_adapter_family_specs
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.models import (
    Jurisdiction,
    PlatformFamily,
    PublicSource,
    SourceType,
    VerificationStatus,
)
from constructionsight.source_readiness_models import HttpReachabilityResult
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_authorized_source_verification_checklist_report,
    build_source_verification_checklist_report,
)


def _source() -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="Test City",
            county="San Bernardino",
            jurisdiction_type="city",
        ),
        source_name="Test Source",
        source_type=SourceType.CITY_PORTAL,
        platform_family=PlatformFamily.ACCELA_ACA,
        public_url="https://example.invalid/source",
        verification_status=VerificationStatus.UNVERIFIED,
    )


def _observations() -> tuple[SourceVerificationObservation, ...]:
    return (
        SourceVerificationObservation(
            source_name="Test Source",
            public_entry_observed=True,
            access_barrier_observed=False,
            evidence_refs=["manual:test"],
        ),
    )


class _Checker:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, source: PublicSource) -> HttpReachabilityResult:
        self.calls.append(str(source.public_url))
        return HttpReachabilityResult(
            checked=True,
            reachable=True,
            status_code=200,
            method="GET",
            final_url=str(source.public_url),
        )


def test_offline_checklist_does_not_acquire_network_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)

    report = build_source_verification_checklist_report(
        [_source()],
        default_adapter_family_specs(),
        check_http=False,
        observations=_observations(),
    )

    assert report.source_count == 1
    assert checker.calls == []
    assert report.rows[0].evidence_refs == ["manual:test"]


def test_offline_checklist_rejects_live_http_request() -> None:
    with pytest.raises(ValueError, match="requires build_authorized"):
        build_source_verification_checklist_report(
            [_source()],
            default_adapter_family_specs(),
            check_http=True,
            observations=_observations(),
        )


def test_authorized_checklist_binds_exact_source_and_observation_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)

    report = build_authorized_source_verification_checklist_report(
        [_source()],
        default_adapter_family_specs(),
        observations=_observations(),
        caller_confirmation=True,
        authorization_reason="Perform one reviewed source verification check.",
        operator_id="operator:tyler",
    )

    assert report.source_count == 1
    assert checker.calls == ["https://example.invalid/source"]
    assert report.rows[0].http_status_code == 200
    assert report.rows[0].evidence_refs == ["manual:test"]


def test_boolean_confirmation_cannot_authorize_live_checklist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        build_authorized_source_verification_checklist_report(
            [_source()],
            default_adapter_family_specs(),
            observations=_observations(),
            caller_confirmation=False,
            authorization_reason="Attempt a live checklist without confirmation.",
            operator_id="operator:tyler",
        )

    assert checker.calls == []


def test_exact_replay_returns_checklist_without_repeating_live_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)
    first = build_authorized_source_verification_checklist_report(
        [_source()],
        default_adapter_family_specs(),
        observations=_observations(),
        caller_confirmation=True,
        authorization_reason="Perform one reviewed source verification check.",
        operator_id="operator:tyler",
    )
    assert first.source_count == 1
    replay = build_authorized_source_verification_checklist_report(
        [_source()],
        default_adapter_family_specs(),
        observations=_observations(),
        caller_confirmation=True,
        authorization_reason="Perform one reviewed source verification check.",
        operator_id="operator:tyler",
    )

    assert replay == first
    assert checker.calls == ["https://example.invalid/source"]


def test_authorized_checklist_does_not_accept_caller_selected_http_checker() -> None:
    parameters = inspect.signature(
        build_authorized_source_verification_checklist_report
    ).parameters
    assert "http_checker" not in parameters
    assert "ledger" not in parameters
    assert "now" not in parameters
