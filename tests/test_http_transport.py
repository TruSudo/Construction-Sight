from __future__ import annotations

import inspect
import socket
import ssl
from collections.abc import Callable
from typing import Any

import httpcore
import httpx
import pytest

import constructionsight.http_transport as http_transport_module
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


def _install_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> None:
    def build_client() -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
            trust_env=False,
            **kwargs,
        )

    monkeypatch.setattr(http_transport_module, "_build_http_client", build_client)


def test_bounded_http_production_boundary_does_not_accept_client_injection() -> None:
    assert "client" not in inspect.signature(execute_bounded_http).parameters


def test_bounded_http_owned_client_disables_ambient_environment_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://attacker:secret@proxy.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://attacker:secret@proxy.invalid:8080")
    monkeypatch.setenv("ALL_PROXY", "http://attacker:secret@proxy.invalid:8080")
    monkeypatch.setenv("SSL_CERT_FILE", "/tmp/attacker-ca.pem")
    monkeypatch.setenv("SSL_CERT_DIR", "/tmp/attacker-ca-dir")
    captured: dict[str, Any] = {}

    class StubClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(http_transport_module.httpx, "Client", StubClient)

    client = http_transport_module._build_http_client()

    assert isinstance(client, StubClient)
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False
    assert isinstance(captured["transport"], http_transport_module._PinnedHttpTransport)
    assert set(captured) == {"follow_redirects", "transport", "trust_env"}


def test_bounded_http_owns_tls_roots_and_requires_hostname_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubContext:
        verify_mode: ssl.VerifyMode | None = None
        check_hostname = False

        def __init__(self) -> None:
            self.protocol: int | None = None
            self.loaded_cafile: str | None = None

        def load_verify_locations(self, *, cafile: str) -> None:
            self.loaded_cafile = cafile

    context = StubContext()

    def build_context(protocol: int) -> StubContext:
        context.protocol = protocol
        return context

    monkeypatch.setattr(http_transport_module.ssl, "SSLContext", build_context)
    monkeypatch.setattr(http_transport_module.certifi, "where", lambda: "/reviewed/ca.pem")

    result = http_transport_module._owned_tls_context()

    assert result is context
    assert context.protocol == ssl.PROTOCOL_TLS_CLIENT
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.loaded_cafile == "/reviewed/ca.pem"


@pytest.mark.parametrize(
    "url",
    (
        "https://127.0.0.1/public/data",
        "https://169.254.169.254/public/data",
        "https://localhost/public/data",
        "https://service.internal/public/data",
    ),
)
def test_public_egress_rejects_literal_and_special_use_authorities(url: str) -> None:
    with pytest.raises(ValueError, match="outside public egress authority"):
        http_transport_module._resolve_public_authority(url)


def test_public_egress_rejects_any_non_public_dns_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
    ]
    monkeypatch.setattr(http_transport_module.socket, "getaddrinfo", lambda *_a, **_k: answers)

    with pytest.raises(ValueError, match="resolved to a non-public address"):
        http_transport_module._resolve_public_authority("https://public.example.com/data")


@pytest.mark.parametrize("numeric_host", ("2130706433", "0x7f000001"))
def test_public_egress_rejects_legacy_numeric_host_forms_after_resolution(
    numeric_host: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))
    ]
    monkeypatch.setattr(http_transport_module.socket, "getaddrinfo", lambda *_a, **_k: answers)

    with pytest.raises(ValueError, match="resolved to a non-public address"):
        http_transport_module._resolve_public_authority(
            f"https://{numeric_host}/public/data"
        )


def test_public_egress_resolves_alias_once_and_retains_alias_as_tls_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[tuple[str, int]] = []

    def resolve(host: str, port: int, **_kwargs: Any) -> list[tuple[Any, ...]]:
        queries.append((host, port))
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "canonical.public.example.com",
                ("93.184.216.34", 443),
            )
        ]

    monkeypatch.setattr(http_transport_module.socket, "getaddrinfo", resolve)

    authority = http_transport_module._resolve_public_authority(
        "https://alias.public.example.com/data"
    )

    assert queries == [("alias.public.example.com", 443)]
    assert authority.host == "alias.public.example.com"
    assert authority.address == "93.184.216.34"


def test_public_egress_pins_single_resolution_to_tcp_and_preserves_tls_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = 0

    def resolve(*_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        nonlocal resolutions
        resolutions += 1
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 443),
            )
        ]

    class StubStream(httpcore.NetworkStream):
        def __init__(self) -> None:
            self.tls_hostnames: list[str | None] = []

        def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
            return b""

        def write(self, buffer: bytes, timeout: float | None = None) -> None:
            return None

        def close(self) -> None:
            return None

        def start_tls(
            self,
            ssl_context: ssl.SSLContext,
            server_hostname: str | None = None,
            timeout: float | None = None,
        ) -> httpcore.NetworkStream:
            self.tls_hostnames.append(server_hostname)
            return self

    class StubBackend(httpcore.NetworkBackend):
        def __init__(self) -> None:
            self.connections: list[tuple[str, int, str | None]] = []
            self.stream = StubStream()

        def connect_tcp(
            self,
            host: str,
            port: int,
            timeout: float | None = None,
            local_address: str | None = None,
            socket_options: Any = None,
        ) -> httpcore.NetworkStream:
            self.connections.append((host, port, local_address))
            return self.stream

        def connect_unix_socket(
            self,
            path: str,
            timeout: float | None = None,
            socket_options: Any = None,
        ) -> httpcore.NetworkStream:
            raise AssertionError(path)

    monkeypatch.setattr(http_transport_module.socket, "getaddrinfo", resolve)
    authority = http_transport_module._resolve_public_authority(
        "https://public.example.com/data"
    )
    underlying = StubBackend()
    backend = http_transport_module._PinnedNetworkBackend(authority, underlying)

    stream = backend.connect_tcp("public.example.com", 443)
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    stream.start_tls(tls_context, server_hostname="public.example.com")

    assert resolutions == 1
    assert underlying.connections == [("93.184.216.34", 443, None)]
    assert underlying.stream.tls_hostnames == ["public.example.com"]


def test_owned_transport_preserves_original_http_authority_in_core_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = http_transport_module._ResolvedPublicAuthority(
        host="public.example.com",
        port=443,
        address="93.184.216.34",
    )
    captured: dict[str, Any] = {}

    class StubPool:
        def __init__(self, **kwargs: Any) -> None:
            captured["pool_kwargs"] = kwargs
            captured["pool"] = self
            self.closed = False

        def handle_request(self, request: httpcore.Request) -> httpcore.Response:
            captured["request"] = request
            return httpcore.Response(
                200,
                headers=[(b"content-type", b"text/plain")],
                content=[b"owned"],
            )

        def close(self) -> None:
            self.closed = True

    tls_context = object()
    monkeypatch.setattr(
        http_transport_module,
        "_resolve_public_authority",
        lambda _url: authority,
    )
    monkeypatch.setattr(http_transport_module, "_owned_tls_context", lambda: tls_context)
    monkeypatch.setattr(http_transport_module.httpcore, "ConnectionPool", StubPool)

    with http_transport_module._build_http_client() as client:
        response = client.send(
            httpx.Request("GET", "https://public.example.com/data"),
            stream=True,
        )
        assert response.read() == b"owned"
        response.close()

    request = captured["request"]
    assert isinstance(request, httpcore.Request)
    assert request.url.host == b"public.example.com"
    assert request.url.target == b"/data"
    pool_kwargs = captured["pool_kwargs"]
    assert isinstance(pool_kwargs, dict)
    assert pool_kwargs["ssl_context"] is tls_context
    assert isinstance(pool_kwargs["network_backend"], http_transport_module._PinnedNetworkBackend)
    pool = captured["pool"]
    assert isinstance(pool, StubPool)
    assert pool.closed is True


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
def test_bounded_http_rejects_ambiguous_url_forms_before_execution(
    url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal executed
        executed = True
        return httpx.Response(200, content=b"unexpected", request=request)

    _install_client(monkeypatch, handler)
    with pytest.raises(ValueError):
        execute_bounded_http(url, "GET", _policy())

    assert executed is False


def test_bounded_http_requires_executable_authority_for_any_query() -> None:
    with pytest.raises(ValueError, match="query is outside policy"):
        execute_bounded_http(
            "https://example.test/public/data?page=1",
            "GET",
            _policy(),
        )


def test_bounded_http_authorizes_and_transmits_one_exact_url_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    _install_client(monkeypatch, handler)
    policy = _policy(allowed_request_urls=(url,))
    observation = execute_bounded_http(url, "GET", policy)

    assert transmitted == [url]
    assert observation.request_url == url
    assert observation.final_url == url
    assert observation.response_body == b"exact"


def test_bounded_http_test_seam_cannot_merge_client_query_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/public/data"
    transmitted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        transmitted.append(str(request.url))
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"exact",
            request=request,
        )

    _install_client(monkeypatch, handler, params={"unauthorized": "true"})
    observation = execute_bounded_http(url, "GET", _policy())

    assert transmitted == [url]
    assert observation.request_url == url
    assert observation.final_url == url


def test_bounded_http_test_seam_disables_client_auth_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/public/data"
    mutated_url = "https://example.test/public/data?unauthorized=true"
    auth_invoked = False
    transmitted: list[str] = []

    def rewrite_request(request: httpx.Request) -> httpx.Request:
        nonlocal auth_invoked
        auth_invoked = True
        request.url = httpx.URL(mutated_url)
        return request

    def handler(request: httpx.Request) -> httpx.Response:
        transmitted.append(str(request.url))
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"exact",
            request=request,
        )

    _install_client(monkeypatch, handler, auth=rewrite_request)
    observation = execute_bounded_http(url, "GET", _policy())

    assert auth_invoked is False
    assert transmitted == [url]
    assert observation.request_url == url
    assert observation.final_url == url


def test_bounded_http_test_seam_rejects_request_hooks_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/public/data"
    transmitted: list[str] = []

    def rewrite_request(request: httpx.Request) -> None:
        request.url = httpx.URL(
            "https://example.test/public/data?unauthorized=true"
        )

    def handler(request: httpx.Request) -> httpx.Response:
        transmitted.append(str(request.url))
        return httpx.Response(200, content=b"unexpected", request=request)

    _install_client(monkeypatch, handler, event_hooks={"request": [rewrite_request]})
    with pytest.raises(ValueError, match="must not define request event hooks"):
        execute_bounded_http(url, "GET", _policy())

    assert transmitted == []


def test_bounded_http_test_seam_rejects_response_hooks_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/public/data"
    transmitted = False
    response_hook_invoked = False

    def rewrite_response(response: httpx.Response) -> None:
        nonlocal response_hook_invoked
        response_hook_invoked = True
        response.status_code = 200

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal transmitted
        transmitted = True
        return httpx.Response(
            403,
            headers={"content-type": "text/plain"},
            content=b"access denied",
            request=request,
        )

    _install_client(monkeypatch, handler, event_hooks={"response": [rewrite_response]})
    with pytest.raises(ValueError, match="must not define response event hooks"):
        execute_bounded_http(url, "GET", _policy())

    assert transmitted is False
    assert response_hook_invoked is False


def test_bounded_http_rejects_forged_response_request_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.test/public/data"
    forged_request = httpx.Request("GET", url, headers={"X-Forged": "true"})
    transmitted: list[str] = []

    class ForgingClient:
        event_hooks: dict[str, list[object]] = {"request": [], "response": []}

        def __enter__(self) -> ForgingClient:
            return self

        def __exit__(
            self,
            _exc_type: object,
            _exc: object,
            _traceback: object,
        ) -> None:
            return None

        def send(self, request: httpx.Request, **_kwargs: Any) -> httpx.Response:
            transmitted.append(str(request.url))
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                content=b"forged evidence",
                request=forged_request,
            )

    monkeypatch.setattr(http_transport_module, "_build_http_client", ForgingClient)

    with pytest.raises(ValueError, match="replaced the authorized request"):
        execute_bounded_http(url, "GET", _policy())

    assert transmitted == [url]


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorized_url = (
        "https://example.test/public/data?County=San+Bernardino&page=1"
    )
    executed = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal executed
        executed = True
        return httpx.Response(200, content=b"unexpected", request=request)

    _install_client(monkeypatch, handler)
    policy = _policy(allowed_request_urls=(authorized_url,))
    with pytest.raises(ValueError, match="canonical identity is outside policy"):
        execute_bounded_http(
            unauthorized_url,
            "GET",
            policy,
        )

    assert executed is False


def test_http_policy_rejects_noncanonical_exact_request_identity() -> None:
    with pytest.raises(ValueError, match="ambiguous encoded separator"):
        _policy(
            allowed_request_urls=(
                "https://example.test/public/%2Fprivate?scope=approved",
            )
        )


def test_bounded_http_rejects_legacy_client_keyword_before_execution() -> None:
    class LegacyClient:
        def get(self, url: str, *, follow_redirects: bool, timeout: float) -> object:
            raise AssertionError((url, follow_redirects, timeout))

    legacy_client: Any = LegacyClient()
    execute: Any = execute_bounded_http
    with pytest.raises(TypeError, match="unexpected keyword argument 'client'"):
        execute(
            "https://example.test/public/data",
            "GET",
            _policy(),
            client=legacy_client,
        )


def test_bounded_http_retains_successful_exact_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=b"verified evidence",
            request=request,
        )

    _install_client(monkeypatch, handler)
    observation = execute_bounded_http(
        "https://example.test/public/data",
        "GET",
        _policy(),
    )

    assert observation.succeeded is True
    assert observation.failure_kind is HttpFailureKind.NONE
    assert observation.response_body == b"verified evidence"
    assert observation.response_size == len(b"verified evidence")
    assert observation.decode_text(("utf-8",)) == "verified evidence"


def test_bounded_http_denies_redirect_without_following_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "https://other.test/private"},
            request=request,
        )

    _install_client(monkeypatch, handler)
    observation = execute_bounded_http(
        "https://example.test/public/data",
        "GET",
        _policy(),
    )

    assert requested == ["https://example.test/public/data"]
    assert observation.failure_kind is HttpFailureKind.REDIRECT
    assert observation.succeeded is False
    assert observation.error_type == "RedirectDenied"


def test_bounded_http_rejects_declared_oversized_response_without_body_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/plain",
                "content-length": "100",
            },
            content=b"x" * 100,
            request=request,
        )

    _install_client(monkeypatch, handler)
    observation = execute_bounded_http(
        "https://example.test/public/data",
        "GET",
        _policy(max_response_bytes=16),
    )

    assert observation.failure_kind is HttpFailureKind.OVERSIZED_RESPONSE
    assert observation.body_truncated is True
    assert observation.response_size == 100
    assert observation.response_body == b""


def test_bounded_http_preserves_access_control_as_terminal_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"content-type": "text/plain"},
            content=b"login required",
            request=request,
        )

    _install_client(monkeypatch, handler)
    observation = execute_bounded_http(
        "https://example.test/public/data",
        "GET",
        _policy(),
    )

    assert observation.failure_kind is HttpFailureKind.ACCESS_CONTROL
    assert observation.response_body == b""
    assert observation.status_code == 403
