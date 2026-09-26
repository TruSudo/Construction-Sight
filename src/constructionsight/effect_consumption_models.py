"""Immutable identities and terminal state for protected effect consumption."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EffectReplayPolicy(StrEnum):
    """Whether an exact committed duplicate may reuse the retained result."""

    DENY = "deny"
    EXACT = "exact"


class EffectConsumptionStatus(StrEnum):
    """Durable lifecycle of one exact protected operation."""

    RESERVED = "reserved"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class EffectOperation:
    """Content-bound authority and allowance identity reserved before an effect."""

    reservation_key: str
    operation_digest: str
    decision_id: str
    authority_digest: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    exact_scope_digest: str
    current_state_identity: str
    allowance_identity: str
    content_identity: str
    implementation_id: str
    replay_policy: EffectReplayPolicy


@dataclass(frozen=True)
class EffectConsumptionRecord:
    """One durable reservation and any terminal result or failure evidence."""

    operation: EffectOperation
    status: EffectConsumptionStatus
    reserved_at: datetime
    effect_started_at: datetime | None
    completed_at: datetime | None
    result_json: str | None
    result_digest: str | None
    failure_phase: str | None
    failure_type: str | None
    failure_digest: str | None


@dataclass(frozen=True)
class EffectReservation:
    """Atomic reservation result returned to the owned execution boundary."""

    record: EffectConsumptionRecord
    exact_replay: bool
