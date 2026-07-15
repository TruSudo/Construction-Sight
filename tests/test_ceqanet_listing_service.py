from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionError,
    CeqanetListingExecutionPolicy,
)
from constructionsight.adapters.ceqanet_listing_models import (
    CeqanetListingExecutionResult,
    CeqanetListingPageExecutionResult,
    CeqanetListingPlan,
)
from constructionsight.adapters.ceqanet_listing_planner import build_ceqanet_listing_plan
from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.ceqanet_listing_service import (
    CeqanetListingServiceError,
    execute_authorized_ceqanet_listing,
)
from constructionsight.legal import SourceAccessProfile

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


class _Executor:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, int, int]] = []

    def __call__(
        self,
        plan: CeqanetListingPlan,
        *,
        policy: CeqanetListingExecutionPolicy,
    ) -> CeqanetListingExecutionResult:
        self.calls.append(
            (plan.plan_id, policy.max_attempts, policy.max_response_bytes)
        )
        if self.fail:
            raise CeqanetListingExecutionError("synthetic terminal failure")
        request = plan.requests[0]
        page = CeqanetListingPageExecutionResult(
            request_id=request.request_id,
            page_number=request.page_number,
            request_url=request.request_url,
            final_url=request.request_url,
            status_code=200,
            response_headers={"content-type": "text/html"},
            content_type="text/html",
            response_encoding="utf-8",
            response_body="<html>page</html>",
            response_size_bytes=17,
            body_truncated=False,
            attempt_count=1,
            attempts=(),
            failure_kind="none",
            error_type=None,
            error_message=None,
            retry_exhausted=False,
            access_control_terminal=False,
            has_next_page=False,
            end_of_results=True,
        )
        return CeqanetListingExecutionResult(
            plan_id=plan.plan_id,
            county=plan.county,
            requested_max_pages=plan.max_pages,
            planned_request_count=plan.request_count,
            access_allowed=True,
            execution_started=True,
            page_results=(page,),
        )


def _profile(**changes: object) -> SourceAccessProfile:
    return SourceAccessProfile(
        public_url="https://ceqanet.lci.ca.gov/",
        **changes,
    )


def _plan(profile: SourceAccessProfile | None = None) -> CeqanetListingPlan:
    return build_ceqanet_listing_plan(
        county="San Bernardino",
        document_type="EIR",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 7, 15),
        max_pages=1,
        profile=profile or _profile(),
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
        now=lambda: _NOW,
        ledger=ledger,
        executor=executor,
    )


def test_listing_service_binds_exact_plan_policy_and_denied_authority() -> None:
    executor = _Executor()
    plan = _plan()

    payload = _execute(executor, plan=plan)

    authorization = payload["authorization"]
    assert isinstance(authorization, dict)
    assert authorization["resource_id"] == plan.plan_id
    assert authorization["action"] == "execute-ceqanet-listing-plan"
    assert str(authorization["decision_id"]).startswith("authorization-decision:")
    assert str(authorization["preflight_id"]).startswith("authorization-preflight:")
    assert "page-count expansion" in authorization["denied_authority"]
    assert "query mutation" in authorization["denied_authority"]
    assert payload["executed_request_count"] == 1
    assert executor.calls == [(plan.plan_id, 3, 50_000)]


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
    assert first["authorization"]
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _execute(executor, plan=plan, ledger=ledger)

    assert executor.calls == [(plan.plan_id, 3, 50_000)]


def test_transport_failure_remains_distinct_and_visible() -> None:
    executor = _Executor(fail=True)

    with pytest.raises(CeqanetListingServiceError, match="synthetic terminal failure"):
        _execute(executor)

    assert len(executor.calls) == 1
