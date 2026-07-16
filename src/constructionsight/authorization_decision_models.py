"""General scope-bound semantic authorization decision contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AUTHORIZATION_DECISION_SCHEMA_VERSION: Final[
    Literal["constructionsight.authorization-decision/v1"]
] = "constructionsight.authorization-decision/v1"
AUTHORIZATION_PREFLIGHT_SCHEMA_VERSION: Final[
    Literal["constructionsight.authorization-preflight/v1"]
] = "constructionsight.authorization-preflight/v1"


class AuthorizationReusePolicy(StrEnum):
    """Allowed authorization consumption semantics."""

    SINGLE_USE = "single_use"
    EXACT_REPLAY = "exact_replay"


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


def authorization_digest(prefix: str, payload: dict[str, Any]) -> str:
    """Return a deterministic content identity for authority-significant data."""

    canonical = json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(canonical).hexdigest()}"


class AuthorizationDecision(BaseModel):
    """Fail-closed authority for one exact action, resource, state, and scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["constructionsight.authorization-decision/v1"] = (
        AUTHORIZATION_DECISION_SCHEMA_VERSION
    )
    decision_id: str = Field(pattern=r"^authorization-decision:[0-9a-f]{64}$")
    actor_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    exact_scope: tuple[str, ...] = Field(min_length=1)
    current_state_identity: str = Field(min_length=1)
    expected_identity: str = Field(min_length=1)
    granted_authority: tuple[str, ...] = Field(min_length=1)
    denied_authority: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    reuse_policy: AuthorizationReusePolicy
    max_uses: Literal[1] = 1
    revocation_identity: str = Field(min_length=1)
    audit_identity: str = Field(min_length=1)
    failure_posture: Literal["fail_closed"] = "fail_closed"
    caller_confirmation: bool = False
    limitations: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "actor_id",
        "action",
        "resource_type",
        "resource_id",
        "current_state_identity",
        "expected_identity",
        "reason",
        "revocation_identity",
        "audit_identity",
    )
    @classmethod
    def require_trimmed_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("authorization text fields must be trimmed")
        return value

    @field_validator(
        "exact_scope",
        "granted_authority",
        "denied_authority",
        "limitations",
    )
    @classmethod
    def require_canonical_unique_text(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(not value.strip() or value != value.strip() for value in values):
            raise ValueError("authorization tuple values must be nonblank and trimmed")
        canonical = tuple(sorted(set(values), key=lambda value: value.casefold()))
        if values != canonical:
            raise ValueError("authorization tuple values must be unique and sorted")
        return values

    @field_validator("issued_at", "not_before", "expires_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authorization timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_bounded_consistent_authority(self) -> AuthorizationDecision:
        if self.issued_at > self.not_before:
            raise ValueError("authorization issued_at cannot follow not_before")
        if self.not_before >= self.expires_at:
            raise ValueError("authorization not_before must precede expires_at")
        if (self.expires_at - self.not_before).total_seconds() > 86_400:
            raise ValueError("authorization validity cannot exceed 24 hours")
        overlap = set(self.granted_authority) & set(self.denied_authority)
        if overlap:
            raise ValueError(
                f"authority cannot be both granted and denied: {sorted(overlap)}"
            )
        if self.current_state_identity != self.expected_identity:
            raise ValueError(
                "authorization cannot issue against a stale or unexpected current state"
            )
        if self.reuse_policy is AuthorizationReusePolicy.EXACT_REPLAY:
            replay_marker = f"exact replay of {self.action}"
            if replay_marker not in self.granted_authority:
                raise ValueError(
                    "exact-replay authorization requires an explicit replay grant"
                )
        if self.decision_id != authorization_digest(
            "authorization-decision",
            self.identity_payload(),
        ):
            raise ValueError("authorization decision ID does not match content")
        return self

    def identity_payload(self) -> dict[str, Any]:
        """Return all authority-significant content without the stored identity."""

        return self.model_dump(mode="json", exclude={"decision_id"})

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AuthorizationPreflight(BaseModel):
    """Exact, time-bound authorization usability decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["constructionsight.authorization-preflight/v1"] = (
        AUTHORIZATION_PREFLIGHT_SCHEMA_VERSION
    )
    preflight_id: str = Field(pattern=r"^authorization-preflight:[0-9a-f]{64}$")
    decision_id: str = Field(pattern=r"^authorization-decision:[0-9a-f]{64}$")
    actor_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    checked_at: datetime
    valid_until: datetime
    exact_scope_verified: Literal[True] = True
    current_state_verified: Literal[True] = True
    decision_integrity_verified: Literal[True] = True
    validity_window_verified: Literal[True] = True
    revocation_verified: Literal[True] = True
    use_available: Literal[True] = True
    audit_identity: str = Field(min_length=1)
    next_action: str = Field(min_length=1)

    @field_validator("checked_at", "valid_until")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authorization preflight timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_consistent_preflight(self) -> AuthorizationPreflight:
        if self.checked_at >= self.valid_until:
            raise ValueError("authorization preflight must precede validity expiry")
        if self.preflight_id != authorization_digest(
            "authorization-preflight",
            self.identity_payload(),
        ):
            raise ValueError("authorization preflight ID does not match content")
        return self

    def identity_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"preflight_id"})

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
