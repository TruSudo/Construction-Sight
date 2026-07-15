"""Immutable contracts for bounded public HTTP execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class HttpFailureKind(StrEnum):
    """Stable distinctions for terminal and nonterminal HTTP outcomes."""

    NONE = "none"
    TIMEOUT = "timeout"
    TRANSPORT = "transport_failure"
    REDIRECT = "redirect_denied"
    ACCESS_CONTROL = "access_control"
    RATE_LIMIT = "rate_limit"
    TERMINAL_STATUS = "terminal_status"
    OVERSIZED_RESPONSE = "oversized_response"
    MEDIA_TYPE = "unexpected_media_type"
    ENCODING = "unsupported_encoding"
    MALFORMED_RESPONSE = "malformed_response"
    CANCELLED = "cancelled"
    RETENTION = "retention_failure"


@dataclass(frozen=True)
class BoundedHttpPolicy:
    """Complete operation policy required before any public HTTP request."""

    policy_id: str
    allowed_methods: tuple[str, ...]
    allowed_hosts: tuple[str, ...]
    allowed_path_prefixes: tuple[str, ...]
    connect_timeout_seconds: float
    read_timeout_seconds: float
    write_timeout_seconds: float
    pool_timeout_seconds: float
    max_response_bytes: int
    accepted_media_types: tuple[str, ...]
    accepted_encodings: tuple[str, ...] = ("utf-8",)
    allow_http: bool = False
    user_agent: str = "ConstructionSight/0.1"

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("HTTP policy ID cannot be blank")
        methods = tuple(method.upper() for method in self.allowed_methods)
        if not methods or any(method not in {"GET", "HEAD"} for method in methods):
            raise ValueError("HTTP policy methods must be a nonempty GET/HEAD subset")
        if methods != self.allowed_methods:
            raise ValueError("HTTP policy methods must be canonical uppercase values")
        if not self.allowed_hosts or any(not host.strip() for host in self.allowed_hosts):
            raise ValueError("HTTP policy requires explicit allowed hosts")
        if not self.allowed_path_prefixes or any(
            not path.startswith("/") for path in self.allowed_path_prefixes
        ):
            raise ValueError("HTTP policy path prefixes must be absolute")
        timeout_values = (
            self.connect_timeout_seconds,
            self.read_timeout_seconds,
            self.write_timeout_seconds,
            self.pool_timeout_seconds,
        )
        if any(value <= 0 for value in timeout_values):
            raise ValueError("HTTP policy timeouts must be positive")
        if self.max_response_bytes < 1:
            raise ValueError("HTTP policy response limit must be positive")
        if not self.accepted_media_types or any(
            not value.strip() for value in self.accepted_media_types
        ):
            raise ValueError("HTTP policy requires accepted media types")
        if not self.accepted_encodings or any(
            not value.strip() for value in self.accepted_encodings
        ):
            raise ValueError("HTTP policy requires accepted encodings")


@dataclass(frozen=True)
class BoundedHttpObservation:
    """One classified response or failure from a policy-bound HTTP attempt."""

    policy_id: str
    method: str
    request_url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    content_encoding: str | None
    response_body: bytes
    response_size: int
    body_truncated: bool
    failure_kind: HttpFailureKind
    error_type: str | None
    error_detail: str | None
    attempt_count: int = 1

    @property
    def succeeded(self) -> bool:
        return self.failure_kind is HttpFailureKind.NONE

    @property
    def reachable(self) -> bool:
        return self.status_code is not None

    def decode_text(self, encodings: tuple[str, ...]) -> str:
        """Decode exact retained bytes using only policy-approved encodings."""

        candidates: list[str] = []
        if self.content_encoding:
            candidates.append(self.content_encoding)
        candidates.extend(encodings)
        for encoding in dict.fromkeys(candidates):
            try:
                return self.response_body.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        raise UnicodeError("retained HTTP response does not match an approved encoding")


HttpExecutor = Callable[[str, str, BoundedHttpPolicy], BoundedHttpObservation]
