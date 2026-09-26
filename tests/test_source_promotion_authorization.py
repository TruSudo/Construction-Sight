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
from constructionsight.operator_services.source_promotion_service import (
    build_authorized_source_promotion_plan,
)
from constructionsight.source_readiness_models import HttpReachabilityResult
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


def test_authorized_promotion_plan_is_report_only_and_source_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)

    report = build_authorized_source_promotion_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_observation()],
        caller_confirmation=True,
        authorization_reason="Build one reviewed promotion plan.",
        operator_id="operator:tyler",
    )

    assert report.source_count == 1
    assert checker.calls == ["https://ceqanet.opr.ca.gov/"]
    assert report.rows[0].proposed_registry_status == "partial"


def test_boolean_confirmation_cannot_authorize_promotion_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        build_authorized_source_promotion_plan(
            [_source()],
            default_adapter_family_specs(),
            observations=[_observation()],
            caller_confirmation=False,
            authorization_reason="Attempt a live promotion plan without confirmation.",
            operator_id="operator:tyler",
        )

    assert checker.calls == []


def test_exact_replay_returns_promotion_plan_without_repeating_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(checklist_service, "_check_source_verification", checker)
    first = build_authorized_source_promotion_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_observation()],
        caller_confirmation=True,
        authorization_reason="Build one reviewed promotion plan.",
        operator_id="operator:tyler",
    )
    assert first.source_count == 1
    replay = build_authorized_source_promotion_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_observation()],
        caller_confirmation=True,
        authorization_reason="Build one reviewed promotion plan.",
        operator_id="operator:tyler",
    )

    assert replay == first
    assert checker.calls == ["https://ceqanet.opr.ca.gov/"]


def test_authorized_promotion_plan_does_not_accept_http_checker() -> None:
    parameters = inspect.signature(build_authorized_source_promotion_plan).parameters
    assert "http_checker" not in parameters
    assert "ledger" not in parameters
    assert "now" not in parameters
