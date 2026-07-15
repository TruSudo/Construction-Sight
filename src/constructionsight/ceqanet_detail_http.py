"""Policy-bound CEQAnet detail-page transport."""

from __future__ import annotations

from dataclasses import replace

from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import BoundedHttpPolicy, HttpExecutor

CEQANET_DETAIL_POLICY = BoundedHttpPolicy(
    policy_id="CS-NET-006",
    allowed_methods=("GET",),
    allowed_hosts=("ceqanet.lci.ca.gov",),
    allowed_path_prefixes=("/",),
    connect_timeout_seconds=5.0,
    read_timeout_seconds=20.0,
    write_timeout_seconds=5.0,
    pool_timeout_seconds=5.0,
    max_response_bytes=50_000,
    accepted_media_types=("text/html",),
    accepted_encodings=("utf-8", "windows-1252"),
)


def execute_ceqanet_detail_request(
    url: str,
    *,
    timeout_seconds: float,
    max_body_bytes: int,
    executor: HttpExecutor | None = None,
) -> dict[str, object]:
    """Execute one exact bounded CEQAnet detail read and preserve failure class."""

    if timeout_seconds <= 0 or timeout_seconds > CEQANET_DETAIL_POLICY.read_timeout_seconds:
        raise ValueError(
            "CEQAnet detail timeout cannot exceed the declared CS-NET-006 ceiling"
        )
    if max_body_bytes < 1 or max_body_bytes > CEQANET_DETAIL_POLICY.max_response_bytes:
        raise ValueError(
            "CEQAnet detail response limit cannot exceed the declared CS-NET-006 ceiling"
        )
    policy = replace(
        CEQANET_DETAIL_POLICY,
        read_timeout_seconds=timeout_seconds,
        max_response_bytes=max_body_bytes,
    )
    observation = (executor or execute_bounded_http)(url, "GET", policy)
    body_text = ""
    if observation.response_body:
        try:
            body_text = observation.decode_text(policy.accepted_encodings)
        except UnicodeError:
            body_text = ""
    return {
        "policy_id": observation.policy_id,
        "method": observation.method,
        "request_url": observation.request_url,
        "final_url": observation.final_url,
        "status_code": observation.status_code,
        "content_type": observation.content_type,
        "content_encoding": observation.content_encoding,
        "body_text": body_text,
        "body_length": observation.response_size,
        "body_truncated": observation.body_truncated,
        "executed": True,
        "failure_kind": observation.failure_kind.value,
        "error": observation.error_type,
        "reachable": observation.succeeded,
        "attempt_count": observation.attempt_count,
    }
