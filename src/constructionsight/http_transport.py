"""Single low-level HTTP engine for policy-bound public reads."""

from __future__ import annotations

import ipaddress
import socket
import ssl
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TypedDict
from urllib.parse import urlsplit

import certifi
import httpcore
import httpx

from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
    canonicalize_http_url,
)

_ACCESS_CONTROL_STATUSES = frozenset({401, 403, 407, 451})
_SPECIAL_USE_DNS_SUFFIXES = (
    ".alt",
    ".example",
    ".home.arpa",
    ".internal",
    ".invalid",
    ".local",
    ".localhost",
    ".onion",
    ".test",
)
_IPV6_TRANSITION_NETWORKS = (
    ipaddress.ip_network("::ffff:0:0/96"),
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("2001::/32"),
    ipaddress.ip_network("2002::/16"),
)


@dataclass(frozen=True)
class _ResolvedPublicAuthority:
    host: str
    port: int
    address: str


class _PinnedNetworkStream(httpcore.NetworkStream):
    """Preserve the reviewed TLS hostname over an already-pinned TCP connection."""

    def __init__(self, stream: httpcore.NetworkStream, expected_host: str) -> None:
        self._stream = stream
        self._expected_host = expected_host

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self._stream.read(max_bytes, timeout)

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._stream.write(buffer, timeout)

    def close(self) -> None:
        self._stream.close()

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.NetworkStream:
        if server_hostname != self._expected_host:
            raise httpcore.ConnectError("TLS hostname differs from resolved authority")
        stream = self._stream.start_tls(
            ssl_context,
            server_hostname=self._expected_host,
            timeout=timeout,
        )
        return _PinnedNetworkStream(stream, self._expected_host)

    def get_extra_info(self, info: str) -> Any:
        return self._stream.get_extra_info(info)


class _PinnedNetworkBackend(httpcore.NetworkBackend):
    """Connect only to the public address selected by the single owned resolution."""

    def __init__(
        self,
        authority: _ResolvedPublicAuthority,
        backend: httpcore.NetworkBackend | None = None,
    ) -> None:
        self._authority = authority
        self._backend = backend or httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        normalized_host = host.casefold().rstrip(".")
        if normalized_host != self._authority.host or port != self._authority.port:
            raise httpcore.ConnectError("connection authority differs from resolved authority")
        if local_address is not None:
            raise httpcore.ConnectError("caller-selected local address is prohibited")
        stream = self._backend.connect_tcp(
            host=self._authority.address,
            port=self._authority.port,
            timeout=timeout,
            local_address=None,
            socket_options=socket_options,
        )
        return _PinnedNetworkStream(stream, self._authority.host)

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        raise httpcore.ConnectError("UNIX socket authority is prohibited")


@contextmanager
def _map_httpcore_exceptions() -> Iterator[None]:
    mappings: tuple[tuple[type[Exception], type[httpx.TransportError]], ...] = (
        (httpcore.ConnectTimeout, httpx.ConnectTimeout),
        (httpcore.ReadTimeout, httpx.ReadTimeout),
        (httpcore.WriteTimeout, httpx.WriteTimeout),
        (httpcore.PoolTimeout, httpx.PoolTimeout),
        (httpcore.ConnectError, httpx.ConnectError),
        (httpcore.ReadError, httpx.ReadError),
        (httpcore.WriteError, httpx.WriteError),
        (httpcore.ProxyError, httpx.ProxyError),
        (httpcore.UnsupportedProtocol, httpx.UnsupportedProtocol),
        (httpcore.LocalProtocolError, httpx.LocalProtocolError),
        (httpcore.RemoteProtocolError, httpx.RemoteProtocolError),
    )
    try:
        yield
    except Exception as exc:
        for source_type, target_type in mappings:
            if isinstance(exc, source_type):
                raise target_type(str(exc)) from exc
        raise


class _PinnedResponseStream(httpx.SyncByteStream):
    def __init__(self, stream: Iterable[bytes]) -> None:
        self._stream = stream

    def __iter__(self) -> Iterator[bytes]:
        with _map_httpcore_exceptions():
            yield from self._stream

    def close(self) -> None:
        close = getattr(self._stream, "close", None)
        if close is not None:
            close()


class _PinnedHttpTransport(httpx.BaseTransport):
    """Resolve once, reject non-public answers, and bind connection to that result."""

    def __init__(self) -> None:
        self._pool: httpcore.ConnectionPool | None = None
        self._used = False

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._used:
            raise httpx.ConnectError("bounded HTTP transport is single-use", request=request)
        self._used = True
        authority = _resolve_public_authority(str(request.url))
        self._pool = httpcore.ConnectionPool(
            ssl_context=_owned_tls_context(),
            max_connections=1,
            max_keepalive_connections=0,
            http1=True,
            http2=False,
            retries=0,
            network_backend=_PinnedNetworkBackend(authority),
        )
        assert isinstance(request.stream, httpx.SyncByteStream)
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with _map_httpcore_exceptions():
            response = self._pool.handle_request(core_request)
        if not isinstance(response.stream, Iterable):
            raise httpx.ProtocolError("HTTP core returned a non-synchronous stream")
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_PinnedResponseStream(response.stream),
            extensions=response.extensions,
        )

    def close(self) -> None:
        if self._pool is not None:
            with _map_httpcore_exceptions():
                self._pool.close()


def _owned_tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_verify_locations(cafile=certifi.where())
    return context


def _is_globally_routable_address(address: str) -> bool:
    parsed = ipaddress.ip_address(address)
    if not parsed.is_global:
        return False
    return not (
        isinstance(parsed, ipaddress.IPv6Address)
        and any(parsed in network for network in _IPV6_TRANSITION_NETWORKS)
    )


def _resolve_public_authority(url: str) -> _ResolvedPublicAuthority:
    parsed = urlsplit(url)
    host = parsed.hostname
    if host is None:
        raise ValueError("HTTP URL requires a hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("HTTP URL IP literals are outside public egress authority")
    normalized_host = host.casefold().rstrip(".")
    if normalized_host == "localhost" or normalized_host.endswith(_SPECIAL_USE_DNS_SUFFIXES):
        raise ValueError("HTTP URL special-use hostname is outside public egress authority")
    port = 443 if parsed.scheme == "https" else 80
    try:
        answers = socket.getaddrinfo(
            normalized_host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except OSError as exc:
        raise httpx.ConnectError("public authority resolution failed") from exc
    addresses = sorted({str(answer[4][0]) for answer in answers})
    if not addresses:
        raise httpx.ConnectError("public authority resolution returned no addresses")
    if any(not _is_globally_routable_address(address) for address in addresses):
        raise ValueError("HTTP authority resolved to a non-public address")
    selected_address = min(
        addresses,
        key=lambda address: (
            ipaddress.ip_address(address).version,
            ipaddress.ip_address(address).packed,
        ),
    )
    return _ResolvedPublicAuthority(
        host=normalized_host,
        port=port,
        address=selected_address,
    )


class _ObservationBase(TypedDict):
    policy: BoundedHttpPolicy
    method: str
    request_url: str
    final_url: str
    status_code: int
    content_type: str | None
    content_encoding: str | None


def _host_allowed(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    normalized = host.casefold().rstrip(".")
    for allowed in allowed_hosts:
        candidate = allowed.casefold().rstrip(".")
        if candidate.startswith("*."):
            suffix = candidate[1:]
            if normalized.endswith(suffix) and normalized != suffix[1:]:
                return True
        elif normalized == candidate:
            return True
    return False


def _path_allowed(path: str, allowed_path_prefixes: tuple[str, ...]) -> bool:
    for prefix in allowed_path_prefixes:
        if prefix == "/" or path == prefix:
            return True
        if prefix.endswith("/") and path.startswith(prefix):
            return True
        if path.startswith(f"{prefix}/"):
            return True
    return False


def _validate_scope(url: str, method: str, policy: BoundedHttpPolicy) -> None:
    parsed = urlsplit(url)
    allowed_schemes = {"https"}
    if policy.allow_http:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes:
        raise ValueError("HTTP request scheme is outside policy")
    if not parsed.hostname or not _host_allowed(parsed.hostname, policy.allowed_hosts):
        raise ValueError("HTTP request host is outside policy")
    if not _path_allowed(parsed.path, policy.allowed_path_prefixes):
        raise ValueError("HTTP request path is outside policy")
    if method not in policy.allowed_methods:
        raise ValueError("HTTP request method is outside policy")
    if policy.allowed_request_urls:
        if url not in policy.allowed_request_urls:
            raise ValueError("HTTP request canonical identity is outside policy")
    elif parsed.query:
        raise ValueError("HTTP request query is outside policy")


def _media_type(value: str | None) -> str | None:
    if value is None:
        return None
    return value.split(";", 1)[0].strip().casefold() or None


def _charset(value: str | None) -> str | None:
    if value is None:
        return None
    for component in value.split(";")[1:]:
        name, separator, raw_value = component.partition("=")
        if separator and name.strip().casefold() == "charset":
            return raw_value.strip().strip('"').casefold() or None
    return None


def _observation(
    *,
    policy: BoundedHttpPolicy,
    method: str,
    request_url: str,
    final_url: str | None = None,
    status_code: int | None = None,
    content_type: str | None = None,
    content_encoding: str | None = None,
    response_body: bytes = b"",
    response_size: int = 0,
    body_truncated: bool = False,
    failure_kind: HttpFailureKind,
    error_type: str | None = None,
    error_detail: str | None = None,
) -> BoundedHttpObservation:
    return BoundedHttpObservation(
        policy_id=policy.policy_id,
        method=method,
        request_url=request_url,
        final_url=final_url or request_url,
        status_code=status_code,
        content_type=content_type,
        content_encoding=content_encoding,
        response_body=response_body,
        response_size=response_size,
        body_truncated=body_truncated,
        failure_kind=failure_kind,
        error_type=error_type,
        error_detail=error_detail,
    )


def _read_bounded(chunks: Iterable[bytes], limit: int) -> tuple[bytes, int, bool]:
    retained = bytearray()
    observed_size = 0
    for chunk in chunks:
        observed_size += len(chunk)
        remaining = limit - len(retained)
        if remaining > 0:
            retained.extend(chunk[:remaining])
        if observed_size > limit:
            return bytes(retained), observed_size, True
    return bytes(retained), observed_size, False


def _validate_outbound_request(
    request: httpx.Request,
    *,
    canonical_method: str,
    canonical_url: str,
    policy: BoundedHttpPolicy,
) -> None:
    if request.method != canonical_method:
        raise ValueError("HTTP client cannot preserve the authorized method")
    request_url = str(request.url)
    if request_url != canonical_url:
        raise ValueError("HTTP client cannot preserve the authorized URL identity")
    _validate_scope(request_url, request.method, policy)


def _build_http_client() -> httpx.Client:
    """Construct the sole production HTTP client with reviewed transport authority."""

    return httpx.Client(
        transport=_PinnedHttpTransport(),
        follow_redirects=False,
        trust_env=False,
    )


@contextmanager
def _send_exact_request(
    session: httpx.Client,
    request: httpx.Request,
    *,
    canonical_method: str,
    canonical_url: str,
    policy: BoundedHttpPolicy,
) -> Iterator[httpx.Response]:
    if session.event_hooks.get("request"):
        raise ValueError("bounded HTTP client must not define request event hooks")
    if session.event_hooks.get("response"):
        raise ValueError("bounded HTTP client must not define response event hooks")
    _validate_outbound_request(
        request,
        canonical_method=canonical_method,
        canonical_url=canonical_url,
        policy=policy,
    )
    response = session.send(
        request,
        stream=True,
        auth=None,
        follow_redirects=False,
    )
    try:
        if response.request is not request:
            raise ValueError("HTTP client replaced the authorized request")
        _validate_outbound_request(
            response.request,
            canonical_method=canonical_method,
            canonical_url=canonical_url,
            policy=policy,
        )
        yield response
    finally:
        response.close()


def execute_bounded_http(
    url: str,
    method: str,
    policy: BoundedHttpPolicy,
) -> BoundedHttpObservation:
    """Execute one attempt under a validated complete policy and classify the outcome."""

    canonical_method = method.upper()
    canonical_url = canonicalize_http_url(url)
    outbound_url = httpx.URL(canonical_url)
    if str(outbound_url) != canonical_url:
        raise ValueError("HTTP client cannot preserve the authorized URL representation")
    _validate_scope(canonical_url, canonical_method, policy)
    timeout = httpx.Timeout(
        connect=policy.connect_timeout_seconds,
        read=policy.read_timeout_seconds,
        write=policy.write_timeout_seconds,
        pool=policy.pool_timeout_seconds,
    )
    request = httpx.Request(
        canonical_method,
        outbound_url,
        headers={
            "Accept": policy.request_accept or ", ".join(policy.accepted_media_types),
            "Accept-Encoding": "identity",
            "User-Agent": policy.user_agent,
        },
        extensions={"timeout": timeout.as_dict()},
    )
    try:
        with _build_http_client() as session, _send_exact_request(
            session,
            request,
            canonical_method=canonical_method,
            canonical_url=canonical_url,
            policy=policy,
        ) as response:
            final_url = str(response.url)
            raw_content_type = response.headers.get("content-type")
            content_type = _media_type(raw_content_type)
            charset = _charset(raw_content_type)
            transfer_encoding = response.headers.get("content-encoding")
            base: _ObservationBase = {
                "policy": policy,
                "method": canonical_method,
                "request_url": canonical_url,
                "final_url": final_url,
                "status_code": response.status_code,
                "content_type": content_type,
                "content_encoding": charset,
            }
            if transfer_encoding not in {None, "", "identity"}:
                return _observation(
                    **base,
                    failure_kind=HttpFailureKind.ENCODING,
                    error_type="UnsupportedContentEncoding",
                    error_detail=transfer_encoding,
                )
            if 300 <= response.status_code < 400:
                return _observation(
                    **base,
                    failure_kind=HttpFailureKind.REDIRECT,
                    error_type="RedirectDenied",
                    error_detail=response.headers.get("location"),
                )
            if response.status_code in _ACCESS_CONTROL_STATUSES:
                return _observation(
                    **base,
                    failure_kind=HttpFailureKind.ACCESS_CONTROL,
                    error_type="AccessControlStatus",
                )
            if response.status_code == 429:
                return _observation(
                    **base,
                    failure_kind=HttpFailureKind.RATE_LIMIT,
                    error_type="RateLimitStatus",
                )
            if response.status_code >= 400:
                return _observation(
                    **base,
                    failure_kind=HttpFailureKind.TERMINAL_STATUS,
                    error_type="TerminalHttpStatus",
                )
            if canonical_method == "HEAD" or response.status_code in {204, 205, 304}:
                return _observation(**base, failure_kind=HttpFailureKind.NONE)
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError:
                    return _observation(
                        **base,
                        failure_kind=HttpFailureKind.MALFORMED_RESPONSE,
                        error_type="InvalidContentLength",
                    )
                if declared_length > policy.max_response_bytes:
                    return _observation(
                        **base,
                        response_size=declared_length,
                        body_truncated=True,
                        failure_kind=HttpFailureKind.OVERSIZED_RESPONSE,
                        error_type="DeclaredResponseTooLarge",
                    )
            body, observed_size, truncated = _read_bounded(
                response.iter_bytes(),
                policy.max_response_bytes,
            )
            if truncated:
                return _observation(
                    **base,
                    response_body=body,
                    response_size=observed_size,
                    body_truncated=True,
                    failure_kind=HttpFailureKind.OVERSIZED_RESPONSE,
                    error_type="StreamedResponseTooLarge",
                )
            if content_type not in {value.casefold() for value in policy.accepted_media_types}:
                return _observation(
                    **base,
                    response_body=body,
                    response_size=observed_size,
                    failure_kind=HttpFailureKind.MEDIA_TYPE,
                    error_type="UnexpectedMediaType",
                )
            observation = _observation(
                **base,
                response_body=body,
                response_size=observed_size,
                failure_kind=HttpFailureKind.NONE,
            )
            try:
                observation.decode_text(policy.accepted_encodings)
            except UnicodeError:
                return _observation(
                    **base,
                    response_body=body,
                    response_size=observed_size,
                    failure_kind=HttpFailureKind.ENCODING,
                    error_type="UnsupportedCharacterEncoding",
                )
            return observation
    except httpx.TimeoutException as exc:
        return _observation(
            policy=policy,
            method=canonical_method,
            request_url=canonical_url,
            failure_kind=HttpFailureKind.TIMEOUT,
            error_type=exc.__class__.__name__,
        )
    except httpx.TransportError as exc:
        return _observation(
            policy=policy,
            method=canonical_method,
            request_url=canonical_url,
            failure_kind=HttpFailureKind.TRANSPORT,
            error_type=exc.__class__.__name__,
        )
