from __future__ import annotations

import httpx
import pytest

from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import BoundedHttpPolicy, HttpFailureKind


def _policy(*, max_response_bytes: int = 32) -> BoundedHttpPolicy:
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
