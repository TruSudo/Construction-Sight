"""Policy-bound public source verification transport."""

from __future__ import annotations

from urllib.parse import urlsplit

from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpExecutor,
)
from constructionsight.models import PublicSource
from constructionsight.source_authority_rules import governed_source_url


def source_verification_policy(
    source: PublicSource,
    *,
    timeout_seconds: float,
) -> BoundedHttpPolicy:
    """Bind a verification request to the source's exact declared host."""

    url = governed_source_url(source)
    parsed = urlsplit(url)
    if parsed.hostname is None:
        raise ValueError("source URL requires a hostname")
    return BoundedHttpPolicy(
        policy_id="CS-NET-008",
        allowed_methods=("GET",),
        allowed_hosts=(parsed.hostname,),
        allowed_path_prefixes=("/",),
        connect_timeout_seconds=min(timeout_seconds, 5.0),
        read_timeout_seconds=timeout_seconds,
        write_timeout_seconds=min(timeout_seconds, 5.0),
        pool_timeout_seconds=min(timeout_seconds, 5.0),
        max_response_bytes=50_000,
        accepted_media_types=(
            "text/html",
            "text/plain",
            "application/json",
            "application/xhtml+xml",
        ),
        accepted_encodings=("utf-8", "windows-1252"),
        allow_http=parsed.scheme.casefold() == "http",
        allowed_request_urls=(url,),
    )


def fetch_source_verification(
    source: PublicSource,
    *,
    timeout_seconds: float,
    executor: HttpExecutor | None = None,
) -> tuple[BoundedHttpObservation, BoundedHttpPolicy]:
    """Execute one bounded source verification GET under an exact-host policy."""

    request_url = governed_source_url(source)
    policy = source_verification_policy(source, timeout_seconds=timeout_seconds)
    observation = (executor or execute_bounded_http)(
        request_url,
        "GET",
        policy,
    )
    return observation, policy
