from dataclasses import dataclass, replace

import httpx
import pytest

import constructionsight.http_transport as http_transport_module
from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionError,
    CeqanetListingExecutionPolicy,
    CeqanetListingReadOnlyExecutor,
)
from constructionsight.legal import AccessDecision, AccessPolicyResult


@dataclass(frozen=True)
class FakeResponse:
    status_code: int
    text: str
    url: str
    headers: dict[str, str]


class FakeClient:
    def __init__(self, responses: tuple[FakeResponse, ...]) -> None:
        self.responses = list(responses)
        self.requested_urls: list[str] = []
        self.timeout_values: list[float] = []

    def build(self) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(self._handle_request),
            follow_redirects=False,
            trust_env=False,
        )

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requested_urls.append(str(request.url))
        self.timeout_values.append(float(request.extensions["timeout"]["read"]))
        response = self.responses.pop(0)
        return httpx.Response(
            response.status_code,
            text=response.text,
            headers=response.headers,
            request=request,
        )


class FailingClient:
    def __init__(self) -> None:
        self.requested_urls: list[str] = []

    def build(self) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(self._handle_request),
            follow_redirects=False,
            trust_env=False,
        )

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requested_urls.append(str(request.url))
        raise httpx.ConnectError("connection refused", request=request)


def _install_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient | FailingClient) -> None:
    monkeypatch.setattr(http_transport_module, "_build_http_client", client.build)


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


def test_ceqanet_listing_executor_executes_bounded_get_requests_with_fake_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    _install_client(monkeypatch, client)

    report = CeqanetListingReadOnlyExecutor(timeout_seconds=7.5).run(plan)

    assert report.allowed is True
    assert report.planned_request_count == 2
    assert report.executed_request_count == 2
    assert report.successful_response_count == 2
    assert report.failed_response_count == 0
    assert report.maximum_records == 50
    assert client.timeout_values == [7.5, 7.5]
    assert len(client.requested_urls) == 2
    assert client.requested_urls[0].endswith("County=San+Bernardino&page=1")
    assert report.snapshots[0].status_code == 200
    assert report.snapshots[0].content_type == "text/html"
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

    report = CeqanetListingReadOnlyExecutor().run(plan)

    assert report.allowed is False
    assert report.planned_request_count == 0
    assert report.executed_request_count == 0
    assert report.successful_response_count == 0
    assert report.failed_response_count == 0
    assert report.maximum_records == 0
    assert report.snapshots == ()
    assert "captcha" in report.reason


def test_ceqanet_listing_executor_records_http_errors_as_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = CeqanetListingQuery(counties=("Riverside",))
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())
    client = FailingClient()
    _install_client(monkeypatch, client)

    report = CeqanetListingReadOnlyExecutor().run(plan)

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


def test_ceqanet_listing_executor_classifies_oversized_response_as_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    _install_client(monkeypatch, client)

    report = CeqanetListingReadOnlyExecutor(max_body_chars=3).run(plan)

    assert report.snapshots[0].body_text == ""
    assert report.snapshots[0].body_length == 6
    assert report.snapshots[0].body_truncated is True
    assert report.snapshots[0].reachable is False
    assert report.snapshots[0].error == "DeclaredResponseTooLarge"


def test_ceqanet_listing_executor_rejects_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    _install_client(monkeypatch, client)

    report = CeqanetListingReadOnlyExecutor().run(plan)

    assert report.snapshots[0].reachable is False
    assert report.snapshots[0].error == "RedirectDenied"
    assert report.snapshots[0].body_text == ""
    assert client.requested_urls == [
        "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino"
    ]


def test_ceqanet_listing_executor_rejects_forged_base_url_before_http() -> None:
    plan = CeqanetReadOnlyListingPlanner().build_plan(
        CeqanetListingQuery(counties=("San Bernardino",)),
        _allowed(),
    )
    forged_page = replace(
        plan.pages[0],
        search_url="https://ceqanet.lci.ca.gov/Search/Unreviewed",
    )
    forged_plan = replace(plan, pages=(forged_page,))

    with pytest.raises(
        CeqanetListingExecutionError,
        match="differs from the canonical planner output",
    ):
        CeqanetListingReadOnlyExecutor().run(forged_plan)


def test_ceqanet_listing_executor_rejects_forged_query_before_http() -> None:
    plan = CeqanetReadOnlyListingPlanner().build_plan(
        CeqanetListingQuery(counties=("San Bernardino",)),
        _allowed(),
    )
    forged_page = replace(
        plan.pages[0],
        params=(("County", "Riverside"), ("unreviewed", "true")),
    )
    forged_plan = replace(plan, pages=(forged_page,))

    with pytest.raises(
        CeqanetListingExecutionError,
        match="differs from the canonical planner output",
    ):
        CeqanetListingReadOnlyExecutor().run(forged_plan)


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
