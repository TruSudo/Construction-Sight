"""Policy-bound public source reachability transport."""

from __future__ import annotations

from urllib.parse import urlsplit

from constructionsight.http_transport import (
    execute_bounded_http as _execute_bounded_http,
)
from constructionsight.http_transport_models import (
    BoundedHttpPolicy,
    canonicalize_http_url,
)
from constructionsight.models import PublicSource
from constructionsight.source_readiness_models import HttpReachabilityResult


def _policy_for_source(url: str) -> BoundedHttpPolicy:
    canonical_url = canonicalize_http_url(url)
    parsed = urlsplit(canonical_url)
    if parsed.hostname is None:
        raise ValueError("source URL requires a hostname")
    return BoundedHttpPolicy(
        policy_id="CS-NET-007",
        allowed_methods=("HEAD", "GET"),
        allowed_hosts=(parsed.hostname,),
        allowed_path_prefixes=("/",),
        connect_timeout_seconds=5.0,
        read_timeout_seconds=10.0,
        write_timeout_seconds=5.0,
        pool_timeout_seconds=5.0,
        max_response_bytes=4096,
        accepted_media_types=(
            "text/html",
            "text/plain",
            "application/json",
            "application/pdf",
            "application/octet-stream",
        ),
        accepted_encodings=("utf-8", "windows-1252"),
        allow_http=parsed.scheme.casefold() == "http",
        allowed_request_urls=(canonical_url,),
    )


def check_source_http_reachability(source: PublicSource) -> HttpReachabilityResult:
    """Run HEAD and only a 405-authorized GET fallback under one exact host policy."""

    url = canonicalize_http_url(str(source.public_url))
    policy = _policy_for_source(url)
    observation = _execute_bounded_http(url, "HEAD", policy)
    if observation.status_code == 405:
        observation = _execute_bounded_http(url, "GET", policy)
    return HttpReachabilityResult(
        checked=True,
        reachable=observation.succeeded,
        status_code=observation.status_code,
        method=observation.method,
        final_url=observation.final_url,
        error=(
            None
            if observation.succeeded
            else ":".join(
                value
                for value in (
                    observation.failure_kind.value,
                    observation.error_type,
                )
                if value
            )
        ),
    )
