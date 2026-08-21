"""Immutable contracts for bounded public HTTP execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from string import ascii_letters, digits
from urllib.parse import urlsplit, urlunsplit

_UPPER_HEX_DIGITS = frozenset("0123456789ABCDEF")
_UNRESERVED_URL_CHARACTERS = frozenset(ascii_letters + digits + "-._~")
_AMBIGUOUS_ENCODED_PATH_CHARACTERS = frozenset("./\\?#@:")


def _validate_percent_encoding(component: str, *, path_component: bool) -> None:
    """Reject percent encodings that are malformed, noncanonical, or ambiguous."""

    index = 0
    while index < len(component):
        if component[index] != "%":
            index += 1
            continue
        if index + 2 >= len(component):
            raise ValueError("HTTP URL contains a malformed percent encoding")
        encoded = component[index + 1 : index + 3]
        if any(character not in _UPPER_HEX_DIGITS for character in encoded):
            raise ValueError("HTTP URL percent encodings must use uppercase hexadecimal")
        decoded_byte = int(encoded, 16)
        decoded_character = chr(decoded_byte)
        if decoded_byte < 0x20 or decoded_byte == 0x7F:
            raise ValueError("HTTP URL cannot percent-encode control characters")
        if decoded_character in _UNRESERVED_URL_CHARACTERS:
            raise ValueError("HTTP URL cannot percent-encode an unreserved character")
        if path_component and decoded_character in _AMBIGUOUS_ENCODED_PATH_CHARACTERS:
            raise ValueError("HTTP URL path contains an ambiguous encoded separator")
        index += 3


def canonicalize_http_url(value: str) -> str:
    """Return one strict outbound URL representation or reject ambiguous input.

    Accepted values are already canonical. The function deliberately does not
    repair caller input because authorizing a repaired value would obscure which
    representation the caller supplied and which representation is transmitted.
    """

    if not isinstance(value, str) or not value:
        raise ValueError("HTTP URL must be a nonempty string")
    if not value.isascii():
        raise ValueError("HTTP URL must use an ASCII wire representation")
    if any(ord(character) <= 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError("HTTP URL cannot contain whitespace or control characters")
    if "\\" in value:
        raise ValueError("HTTP URL cannot contain backslashes")
    if "#" in value:
        raise ValueError("HTTP URL fragments are prohibited")

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("HTTP URL authority is malformed") from exc
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("HTTP URL scheme must be canonical lowercase HTTP or HTTPS")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise ValueError("HTTP URL user information is prohibited")
    if hostname is None:
        raise ValueError("HTTP URL requires a hostname")
    if not hostname.isascii() or hostname != hostname.casefold() or hostname.endswith("."):
        raise ValueError("HTTP URL hostname must be canonical lowercase ASCII")
    if ":" in hostname:
        raise ValueError("HTTP URL IPv6 literals are outside the supported authority scope")
    if port is not None:
        raise ValueError("HTTP URL explicit ports are outside the supported authority scope")
    if parsed.netloc != hostname:
        raise ValueError("HTTP URL authority is not canonical")

    path = parsed.path
    if not path.startswith("/"):
        raise ValueError("HTTP URL path must be absolute and explicit")
    if "//" in path:
        raise ValueError("HTTP URL path cannot contain empty interior segments")
    if any(segment in {".", ".."} for segment in path.split("/")):
        raise ValueError("HTTP URL dot segments are prohibited")
    _validate_percent_encoding(path, path_component=True)

    if "?" in parsed.query:
        raise ValueError("HTTP URL query delimiters inside values must be percent-encoded")
    _validate_percent_encoding(parsed.query, path_component=False)

    canonical = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))
    if canonical != value:
        raise ValueError("HTTP URL is not in canonical wire form")
    return canonical


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
    allowed_request_urls: tuple[str, ...] = ()

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
        if len(set(self.allowed_request_urls)) != len(self.allowed_request_urls):
            raise ValueError("HTTP policy exact request identities must be unique")
        for request_url in self.allowed_request_urls:
            canonicalize_http_url(request_url)


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
