from collections.abc import Mapping
from dataclasses import dataclass

import httpx
import pytest

from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionPolicy,
    CeqanetListingReadOnlyExecutor,
)
from constructionsight.legal import AccessDecision, AccessPolicyResult


@dataclass(frozen=True)
class FakeResponse:
    status_code: int
    text: str
    url: str
    headers: Mapping[str, str]


class FakeClient:
    def __init__(self, responses: tuple[FakeResponse, ...]) -> None:
        self.responses = list(responses)
        self.requested_urls: list[str] = []
        self.follow_redirects_values: list[bool] = []
        self.timeout_values: list[float] = []

    def get(self, url: str, *, follow_redirects: bool, timeout: float) -> FakeResponse:
        self.requested_urls.append(url)
        self.follow_redirects_values.append(follow_redirects)
        self.timeout_values.append(timeout)
        return self.responses.pop(0)


class FailingClient:
    def __init__(self) -> None:
        self.requested_urls: list[str] = []

    def get(self, url: str, *, follow_redirects: bool, timeout: float) -> FakeResponse:
        self.requested_urls.append(url)
        raise httpx.ConnectError("connection refused")


def _allowed() -> AccessPolicyResult:
    return AccessPolicyResult(
        decision=AccessDecision.ALLOWED,
        reason="No known access restriction blocks lawful public collection.",
    )


def _blocked() -> AccessPolicyResult:
    return AccessPolicyResult(
        decision=AccessDecision.BLOCKED,
        reason="Source presents captcha; ConstructionSight does not bypass captchas.",
    )


def test_ceqanet_listing_executor_executes_bounded_get_requests_with_fake_client() -> None:
    query = CeqanetListingQuery(
        counties=("San Bernardino",),
        page_size=25,
        max_pages=2,
    )
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())
    client = FakeClient(
        responses=(
            FakeResponse(
                status_code=200,
                text="<html>page one</html>",
                url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino&page=1",
                headers={"content-type": "text/html; charset=utf-8"},
            ),
            FakeResponse(
                status_code=204,
                text="",
                url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino&page=2",
                headers={},
            ),
        )
    )

    report = CeqanetListingReadOnlyExecutor(
        client=client,
        timeout_seconds=7.5,
    ).run(plan)

    assert report.allowed is True
    assert report.planned_request_count == 2
    assert report.executed_request_count == 2
    assert report.successful_response_count == 2
    assert report.failed_response_count == 0
    assert report.maximum_records == 50
    assert all(value is True for value in client.follow_redirects_values)
    assert client.timeout_values == [7.5, 7.5]
    assert len(client.requested_urls) == 2
    assert client.requested_urls[0].endswith("County=San+Bernardino&page=1")
    assert report.snapshots[0].status_code == 200
    assert report.snapshots[0].content_type == "text/html; charset=utf-8"
    assert report.snapshots[0].body_text == "<html>page one</html>"
    assert report.snapshots[0].body_truncated is False
    assert report.snapshots[0].executed is True


def test_ceqanet_listing_executor_returns_no_requests_when_plan_is_blocked() -> None:
    query = CeqanetListingQuery(
        counties=("San Bernardino",),
        page_size=25,
        max_pages=2,
    )
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _blocked())
    client = FakeClient(responses=())

    report = CeqanetListingReadOnlyExecutor(client=client).run(plan)

    assert report.allowed is False
    assert report.planned_request_count == 0
    assert report.executed_request_count == 0
    assert report.successful_response_count == 0
    assert report.failed_response_count == 0
    assert report.maximum_records == 0
    assert report.snapshots == ()
    assert client.requested_urls == []
    assert "captcha" in report.reason


def test_ceqanet_listing_executor_records_http_errors_as_snapshots() -> None:
    query = CeqanetListingQuery(counties=("Riverside",))
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())
    client = FailingClient()

    report = CeqanetListingReadOnlyExecutor(client=client).run(plan)

    assert len(client.requested_urls) == 1
    assert report.allowed is True
    assert report.planned_request_count == 1
    assert report.executed_request_count == 1
    assert report.successful_response_count == 0
    assert report.failed_response_count == 1
    assert report.snapshots[0].status_code is None
    assert report.snapshots[0].body_text == ""
    assert report.snapshots[0].executed is True
    assert report.snapshots[0].error == "ConnectError"


def test_ceqanet_listing_executor_classifies_oversized_response_as_failure() -> None:
    query = CeqanetListingQuery(counties=("San Bernardino",))
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())
    client = FakeClient(
        responses=(
            FakeResponse(
                status_code=200,
                text="abcdef",
                url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
                headers={"content-type": "text/html"},
            ),
        )
    )

    report = CeqanetListingReadOnlyExecutor(
        client=client,
        max_body_chars=3,
    ).run(plan)

    assert report.snapshots[0].body_text == "abc"
    assert report.snapshots[0].body_length == 6
    assert report.snapshots[0].body_truncated is True
    assert report.snapshots[0].reachable is False
    assert report.snapshots[0].error == "ResponseTooLarge"


def test_ceqanet_listing_executor_rejects_redirects() -> None:
    plan = CeqanetReadOnlyListingPlanner().build_plan(
        CeqanetListingQuery(counties=("San Bernardino",)),
        _allowed(),
    )
    client = FakeClient(
        responses=(
            FakeResponse(
                status_code=302,
                text="redirect body must not be retained",
                url="https://ceqanet.lci.ca.gov/Search",
                headers={"location": "https://example.invalid/"},
            ),
        )
    )

    report = CeqanetListingReadOnlyExecutor(client=client).run(plan)

    assert report.snapshots[0].reachable is False
    assert report.snapshots[0].error == "RedirectDenied"
    assert report.snapshots[0].body_text == ""
    assert client.follow_redirects_values == [True]


def test_ceqanet_listing_executor_rejects_invalid_runtime_bounds() -> None:
    with pytest.raises(ValueError, match="between 0 and 20"):
        CeqanetListingReadOnlyExecutor(timeout_seconds=0)
    with pytest.raises(ValueError, match="between 1 and 50000"):
        CeqanetListingReadOnlyExecutor(max_body_chars=0)
    with pytest.raises(ValueError, match="exactly one attempt"):
        CeqanetListingExecutionPolicy(
            max_attempts=2,
            retry_delays_seconds=(0.1,),
        )
