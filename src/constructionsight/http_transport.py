"""Single low-level HTTP engine for policy-bound public reads."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import nullcontext
from typing import TypedDict
from urllib.parse import urlparse

import httpx

from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
)

_ACCESS_CONTROL_STATUSES = frozenset({401, 403, 407, 451})


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


def _validate_scope(url: str, method: str, policy: BoundedHttpPolicy) -> None:
    parsed = urlparse(url)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("HTTP policy prohibits URL-embedded credentials")
    allowed_schemes = {"https"}
    if policy.allow_http:
        allowed_schemes.add("http")
    if parsed.scheme.casefold() not in allowed_schemes:
        raise ValueError("HTTP request scheme is outside policy")
    if not parsed.hostname or not _host_allowed(parsed.hostname, policy.allowed_hosts):
        raise ValueError("HTTP request host is outside policy")
    if not any(parsed.path.startswith(prefix) for prefix in policy.allowed_path_prefixes):
        raise ValueError("HTTP request path is outside policy")
    if method not in policy.allowed_methods:
        raise ValueError("HTTP request method is outside policy")


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


def execute_bounded_http(
    url: str,
    method: str,
    policy: BoundedHttpPolicy,
    *,
    client: httpx.Client | None = None,
) -> BoundedHttpObservation:
    """Execute one attempt under a validated complete policy and classify the outcome."""

    canonical_method = method.upper()
    _validate_scope(url, canonical_method, policy)
    timeout = httpx.Timeout(
        connect=policy.connect_timeout_seconds,
        read=policy.read_timeout_seconds,
        write=policy.write_timeout_seconds,
        pool=policy.pool_timeout_seconds,
    )
    owned_client = client is None
    active_client = client or httpx.Client(follow_redirects=False)
    context = active_client if owned_client else nullcontext(active_client)
    try:
        with (
            context as session,
            session.stream(
                canonical_method,
                url,
                follow_redirects=False,
                timeout=timeout,
                headers={
                    "Accept": ", ".join(policy.accepted_media_types),
                    "Accept-Encoding": "identity",
                    "User-Agent": policy.user_agent,
                },
            ) as response,
        ):
            final_url = str(response.url)
            raw_content_type = response.headers.get("content-type")
            content_type = _media_type(raw_content_type)
            charset = _charset(raw_content_type)
            transfer_encoding = response.headers.get("content-encoding")
            base: _ObservationBase = {
                "policy": policy,
                "method": canonical_method,
                "request_url": url,
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
            request_url=url,
            failure_kind=HttpFailureKind.TIMEOUT,
            error_type=exc.__class__.__name__,
        )
    except httpx.TransportError as exc:
        return _observation(
            policy=policy,
            method=canonical_method,
            request_url=url,
            failure_kind=HttpFailureKind.TRANSPORT,
            error_type=exc.__class__.__name__,
        )
