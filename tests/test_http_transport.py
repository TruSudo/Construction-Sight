from __future__ import annotations

from typing import Any

import httpx
import pytest

from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import BoundedHttpPolicy, HttpFailureKind


def _policy(
    *,
    max_response_bytes: int = 32,
    allowed_request_urls: tuple[str, ...] = (),
) -> BoundedHttpPolicy:
    return BoundedHttpPolicy(
        policy_id="CS-NET-TEST",
        allowed_methods=("GET",),
        allowed_hosts=("example.test",),
        allowed_path_prefixes=("/public/",),
        connect_timeout_seconds=1.0,
        read_timeout_seconds=1.0,
        write_timeout_seconds=1.0,
        pool_timeout_seconds=1.0,
        max_response_bytes=max_response_bytes,
        accepted_media_types=("text/plain",),
        accepted_encodings=("utf-8",),
        allowed_request_urls=allowed_request_urls,
    )


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, follow_redirects=False)


def test_bounded_http_rejects_host_outside_policy_before_execution() -> None:
    with pytest.raises(ValueError, match="host is outside policy"):
        execute_bounded_http(
            "https://other.test/public/data",
            "GET",
            _policy(),
        )


def test_bounded_http_rejects_path_prefix_confusion_before_execution() -> None:
    with pytest.raises(ValueError, match="path is outside policy"):
        execute_bounded_http(
            "https://example.test/publicity/data",
            "GET",
            _policy(),
        )


@pytest.mark.parametrize(
    "url",
    (
        "HTTPS://example.test/public/data",
        "https://EXAMPLE.test/public/data",
        "https://example.test:443/public/data",
        "https://user@example.test/public/data",
        "https://example.test/public/data#fragment",
        "https://example.test/public\\data",
        "https://example.test/public/../private",
        "https://example.test/public/%2E%2E/private",
        "https://example.test/public/%2Fprivate",
        "https://example.test/public/%5Cprivate",
        "https://example.test/public/%41",
        "https://example.test/public/%2fprivate",
        "https://example.test/public/%",
        "https://example.test/public//data",
        "https://example.test/public/data?",
        "https://example.test",
    ),
)
def test_bounded_http_rejects_ambiguous_url_forms_before_execution(url: str) -> None:
    executed = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal executed
        executed = True
        return httpx.Response(200, content=b"unexpected", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError),
    ):
        execute_bounded_http(url, "GET", _policy(), client=client)

    assert executed is False


def test_bounded_http_requires_executable_authority_for_any_query() -> None:
    with pytest.raises(ValueError, match="query is outside policy"):
        execute_bounded_http(
            "https://example.test/public/data?page=1",
            "GET",
            _policy(),
        )


def test_bounded_http_authorizes_and_transmits_one_exact_url_identity() -> None:
    url = (
        "https://example.test/public/data?"
        "County=San+Bernardino&DocumentType=EIR+-+Draft+EIR&page=1"
    )
    transmitted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        transmitted.append(str(request.url))
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"exact",
            request=request,
        )

    policy = _policy(allowed_request_urls=(url,))
    with _client(httpx.MockTransport(handler)) as client:
        observation = execute_bounded_http(url, "GET", policy, client=client)

    assert transmitted == [url]
    assert observation.request_url == url
    assert observation.final_url == url
    assert observation.response_body == b"exact"


@pytest.mark.parametrize(
    "unauthorized_url",
    (
        "https://example.test/public/data?County=San+Bernardino&page=2",
        "https://example.test/public/data?page=1&County=San+Bernardino",
        "https://example.test/public/data?County=Riverside&page=1",
        "https://example.test/public/data?county=San+Bernardino&page=1",
        "https://example.test/public/data?County=San+Bernardino&page=1&extra=true",
    ),
)
def test_bounded_http_rejects_any_query_identity_drift(
    unauthorized_url: str,
) -> None:
    authorized_url = (
        "https://example.test/public/data?County=San+Bernardino&page=1"
    )
    executed = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal executed
        executed = True
        return httpx.Response(200, content=b"unexpected", request=request)

    policy = _policy(allowed_request_urls=(authorized_url,))
    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="canonical identity is outside policy"),
    ):
        execute_bounded_http(
            unauthorized_url,
            "GET",
            policy,
            client=client,
        )

    assert executed is False


def test_http_policy_rejects_noncanonical_exact_request_identity() -> None:
    with pytest.raises(ValueError, match="ambiguous encoded separator"):
        _policy(
            allowed_request_urls=(
                "https://example.test/public/%2Fprivate?scope=approved",
            )
        )


def test_bounded_http_rejects_legacy_alternate_client_protocol() -> None:
    class LegacyClient:
        def get(self, url: str, *, follow_redirects: bool, timeout: float) -> object:
            raise AssertionError((url, follow_redirects, timeout))

    legacy_client: Any = LegacyClient()
    with pytest.raises(TypeError, match="must be an httpx.Client"):
        execute_bounded_http(
            "https://example.test/public/data",
            "GET",
            _policy(),
            client=legacy_client,
        )


def test_bounded_http_retains_successful_exact_bytes() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=b"verified evidence",
            request=request,
        )
    )
    with _client(transport) as client:
        observation = execute_bounded_http(
            "https://example.test/public/data",
            "GET",
            _policy(),
            client=client,
        )

    assert observation.succeeded is True
    assert observation.failure_kind is HttpFailureKind.NONE
    assert observation.response_body == b"verified evidence"
    assert observation.response_size == len(b"verified evidence")
    assert observation.decode_text(("utf-8",)) == "verified evidence"


def test_bounded_http_denies_redirect_without_following_location() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "https://other.test/private"},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        observation = execute_bounded_http(
            "https://example.test/public/data",
            "GET",
            _policy(),
            client=client,
        )

    assert requested == ["https://example.test/public/data"]
    assert observation.failure_kind is HttpFailureKind.REDIRECT
    assert observation.succeeded is False
    assert observation.error_type == "RedirectDenied"


def test_bounded_http_rejects_declared_oversized_response_without_body_read() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={
                "content-type": "text/plain",
                "content-length": "100",
            },
            content=b"x" * 100,
            request=request,
        )
    )
    with _client(transport) as client:
        observation = execute_bounded_http(
            "https://example.test/public/data",
            "GET",
            _policy(max_response_bytes=16),
            client=client,
        )

    assert observation.failure_kind is HttpFailureKind.OVERSIZED_RESPONSE
    assert observation.body_truncated is True
    assert observation.response_size == 100
    assert observation.response_body == b""


def test_bounded_http_preserves_access_control_as_terminal_class() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            403,
            headers={"content-type": "text/plain"},
            content=b"login required",
            request=request,
        )
    )
    with _client(transport) as client:
        observation = execute_bounded_http(
            "https://example.test/public/data",
            "GET",
            _policy(),
            client=client,
        )

    assert observation.failure_kind is HttpFailureKind.ACCESS_CONTROL
    assert observation.response_body == b""
    assert observation.status_code == 403
