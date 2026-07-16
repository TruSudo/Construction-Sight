from __future__ import annotations

from datetime import UTC, datetime

import pytest

from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingPlan,
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionError,
    CeqanetListingExecutionPolicy,
    CeqanetListingExecutionReport,
    CeqanetListingResponseSnapshot,
)
from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.ceqanet_listing_service import (
    CeqanetListingServiceError,
    execute_authorized_ceqanet_listing,
)
from constructionsight.legal import SourceAccessProfile, evaluate_access

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


class _Executor:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[int, int, int]] = []

    def __call__(
        self,
        plan: CeqanetListingPlan,
        *,
        policy: CeqanetListingExecutionPolicy,
    ) -> CeqanetListingExecutionReport:
        self.calls.append((len(plan.pages), policy.max_attempts, policy.max_response_bytes))
        if self.fail:
            raise CeqanetListingExecutionError("synthetic terminal failure")
        snapshot = CeqanetListingResponseSnapshot(
            page_number=1,
            method="GET",
            request_url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
            final_url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
            status_code=200,
            content_type="text/html",
            body_text="<html>page</html>",
            body_length=17,
            body_truncated=False,
            executed=True,
        )
        return CeqanetListingExecutionReport(
            allowed=True,
            reason="synthetic success",
            planned_request_count=len(plan.pages),
            executed_request_count=1,
            successful_response_count=1,
            maximum_records=plan.maximum_records,
            snapshots=(snapshot,),
        )


def _profile(**changes: object) -> SourceAccessProfile:
    return SourceAccessProfile(
        public_url="https://ceqanet.lci.ca.gov/",
        **changes,
    )


def _plan(profile: SourceAccessProfile | None = None) -> CeqanetListingPlan:
    active_profile = profile or _profile()
    query = CeqanetListingQuery(
        counties=("San Bernardino",),
        document_types=("EIR",),
        page_size=25,
        max_pages=1,
    )
    return CeqanetReadOnlyListingPlanner().build_plan(
        query,
        evaluate_access(active_profile),
    )


def _execute(
    executor: _Executor,
    *,
    plan: CeqanetListingPlan | None = None,
    profile: SourceAccessProfile | None = None,
    confirmation: bool = True,
    ledger: AuthorizationUseLedger | None = None,
) -> dict[str, object]:
    active_profile = profile or _profile()
    return execute_authorized_ceqanet_listing(
        plan=plan or _plan(active_profile),
        access_profile=active_profile,
        operator_id="operator:tyler",
        authorization_reason="Execute one reviewed CEQAnet listing plan.",
        caller_confirmation=confirmation,
        timeout_seconds=20.0,
        max_response_bytes=50_000,
        now=lambda: _NOW,
        ledger=ledger,
        executor=executor,
    )


def _metadata(payload: dict[str, object]) -> dict[str, object]:
    value = payload["metadata"]
    assert isinstance(value, dict)
    return value


def test_listing_service_binds_exact_plan_policy_and_denied_authority() -> None:
    executor = _Executor()

    payload = _execute(executor)

    metadata = _metadata(payload)
    authorization = metadata["authorization"]
    assert isinstance(authorization, dict)
    assert authorization["action"] == "execute-ceqanet-listing-plan"
    assert str(authorization["decision_id"]).startswith("authorization-decision:")
    assert str(authorization["preflight_id"]).startswith("authorization-preflight:")
    assert "page-count expansion" in authorization["denied_authority"]
    assert "query mutation" in authorization["denied_authority"]
    assert "retry" in authorization["denied_authority"]
    assert metadata["executed_request_count"] == 1
    assert executor.calls == [(1, 1, 50_000)]


def test_boolean_confirmation_cannot_authorize_listing_execution() -> None:
    executor = _Executor()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _execute(executor, confirmation=False)

    assert executor.calls == []


def test_current_access_state_must_match_immutable_plan() -> None:
    executor = _Executor()
    plan = _plan(_profile())

    with pytest.raises(AuthorizationDeniedError, match="requires_login"):
        _execute(
            executor,
            plan=plan,
            profile=_profile(requires_login=True),
        )

    assert executor.calls == []


def test_shared_ledger_rejects_repeated_listing_execution() -> None:
    executor = _Executor()
    ledger = AuthorizationUseLedger()
    plan = _plan()

    first = _execute(executor, plan=plan, ledger=ledger)
    assert _metadata(first)["authorization"]
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _execute(executor, plan=plan, ledger=ledger)

    assert executor.calls == [(1, 1, 50_000)]


def test_transport_failure_remains_distinct_and_visible() -> None:
    executor = _Executor(fail=True)

    with pytest.raises(CeqanetListingServiceError, match="synthetic terminal failure"):
        _execute(executor)

    assert len(executor.calls) == 1


def test_listing_service_rejects_retry_expansion() -> None:
    with pytest.raises(ValueError, match="exactly one attempt"):
        CeqanetListingExecutionPolicy(
            max_attempts=3,
            retry_delays_seconds=(0.25, 1.0),
        )
