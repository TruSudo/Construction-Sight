from __future__ import annotations

import inspect
from datetime import date

import pytest

import constructionsight.source_verification_checklist_service as checklist_service
from constructionsight.adapters import default_adapter_family_specs
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.models import (
    ExtractionDifficulty,
    Jurisdiction,
    PlatformFamily,
    PublicSource,
    RecordCategory,
    SourceType,
    VerificationStatus,
)
from constructionsight.operator_services.source_registry_service import (
    apply_authorized_source_registry_update_plan,
    build_authorized_source_registry_update_plan,
)
from constructionsight.source_readiness_models import HttpReachabilityResult
from constructionsight.source_registry_update_plan_service import (
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)


def _source() -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="CEQAnet",
            county="Statewide",
            state="CA",
            jurisdiction_type="state",
        ),
        source_name="CEQAnet State Clearinghouse",
        source_type=SourceType.STATE_REGISTRY,
        platform_family=PlatformFamily.CEQANET,
        public_url="https://ceqanet.opr.ca.gov/",
        record_categories=[RecordCategory.CEQA],
        search_method="Public CEQA search",
        extraction_difficulty=ExtractionDifficulty.LOW,
        update_frequency="daily",
        confidence_score=75,
        verification_status=VerificationStatus.UNVERIFIED,
        provenance_notes="Seed registry record",
        last_checked_date=date(2026, 7, 10),
    )


def _observation() -> SourceVerificationObservation:
    return SourceVerificationObservation(
        source_name="CEQAnet State Clearinghouse",
        public_entry_observed=True,
        query_behavior_observed=True,
        result_list_observed=True,
        detail_page_observed=True,
        access_barrier_observed=False,
        terms_review_observed=True,
        notes="Reviewed public search and detail behavior.",
        evidence_refs=["evidence/ceqanet-review.json"],
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
            final_url="https://ceqanet.lci.ca.gov/",
        )


def test_authorized_registry_plan_binds_exact_sources_and_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)

    report = build_authorized_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_observation()],
        caller_confirmation=True,
        authorization_reason="Build one reviewed registry update plan.",
        operator_id="operator:tyler",
    )

    assert report.source_count == 1
    assert report.update_count == 1
    assert checker.calls == ["https://ceqanet.opr.ca.gov/"]


def test_boolean_confirmation_cannot_authorize_live_registry_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        build_authorized_source_registry_update_plan(
            [_source()],
            default_adapter_family_specs(),
            observations=[_observation()],
            caller_confirmation=False,
            authorization_reason="Attempt a live plan without confirmation.",
            operator_id="operator:tyler",
        )

    assert checker.calls == []


def test_exact_replay_returns_registry_plan_without_repeating_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)
    first = build_authorized_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_observation()],
        caller_confirmation=True,
        authorization_reason="Build one reviewed registry update plan.",
        operator_id="operator:tyler",
    )
    assert first.update_count == 1
    replay = build_authorized_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_observation()],
        caller_confirmation=True,
        authorization_reason="Build one reviewed registry update plan.",
        operator_id="operator:tyler",
    )

    assert replay == first
    assert checker.calls == ["https://ceqanet.opr.ca.gov/"]


def test_authorized_registry_plan_does_not_accept_http_checker() -> None:
    parameters = inspect.signature(build_authorized_source_registry_update_plan).parameters
    assert "http_checker" not in parameters
    assert "ledger" not in parameters
    assert "now" not in parameters


def test_registry_apply_binds_exact_plan_registry_and_target() -> None:
    sources = [_source()]
    plan = build_source_registry_update_plan(
        sources,
        default_adapter_family_specs(),
        observations=[_observation()],
    )

    result = apply_authorized_source_registry_update_plan(
        sources,
        plan,
        expected_plan_digest=plan.plan_digest,
        expected_registry_digest=plan.registry_digest,
        target_path_identity="data/source_registry.updated.json",
        caller_confirmation=True,
        authorization_reason="Apply one reviewed registry update plan.",
        operator_id="operator:tyler",
    )

    authorization = result.authorization.to_dict()
    assert authorization["action"] == "apply-source-registry-update-plan"
    assert "partial registry mutation" in authorization["denied_authority"]
    assert result.report.applied_count == 1
    assert result.sources[0].verification_status is VerificationStatus.PARTIAL


def test_boolean_confirmation_cannot_authorize_registry_apply() -> None:
    sources = [_source()]
    plan = build_source_registry_update_plan(
        sources,
        default_adapter_family_specs(),
        observations=[_observation()],
    )

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        apply_authorized_source_registry_update_plan(
            sources,
            plan,
            expected_plan_digest=plan.plan_digest,
            expected_registry_digest=plan.registry_digest,
            target_path_identity="data/source_registry.updated.json",
            caller_confirmation=False,
            authorization_reason="Attempt registry apply without confirmation.",
            operator_id="operator:tyler",
        )


def test_registry_apply_rejects_stale_expected_registry_before_authorization() -> None:
    sources = [_source()]
    plan = build_source_registry_update_plan(
        sources,
        default_adapter_family_specs(),
        observations=[_observation()],
    )

    with pytest.raises(ValueError, match="expected registry digest"):
        apply_authorized_source_registry_update_plan(
            sources,
            plan,
            expected_plan_digest=plan.plan_digest,
            expected_registry_digest="0" * 64,
            target_path_identity="data/source_registry.updated.json",
            caller_confirmation=True,
            authorization_reason="Attempt stale registry apply.",
            operator_id="operator:tyler",
        )
