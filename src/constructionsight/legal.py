"""Lawful-access policy primitives for ConstructionSight."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccessDecision(StrEnum):
    """Result of a lawful-access policy check."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class AccessPolicyResult:
    """Structured result returned before a source adapter performs collection."""

    decision: AccessDecision
    reason: str

    @property
    def allowed(self) -> bool:
        """Return true only when collection is affirmatively allowed."""

        return self.decision is AccessDecision.ALLOWED


@dataclass(frozen=True)
class SourceAccessProfile:
    """Public access facts known about a source before collection."""

    public_url: str
    requires_login: bool = False
    has_captcha: bool = False
    robots_disallows_collection: bool = False
    terms_disallow_collection: bool = False
    paywalled: bool = False
    rate_limit_known: bool = False
    rate_limit_notes: str | None = None


def evaluate_access(profile: SourceAccessProfile) -> AccessPolicyResult:
    """Evaluate whether a source may be collected by ConstructionSight.

    This function is intentionally conservative. Ambiguous access conditions return
    REVIEW_REQUIRED rather than silently proceeding.
    """

    if profile.requires_login:
        return AccessPolicyResult(
            decision=AccessDecision.REVIEW_REQUIRED,
            reason=(
                "Source requires login (requires_login=true); verify lawful credentials "
                "and source terms before access."
            ),
        )
    if profile.has_captcha:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason="Source presents captcha; ConstructionSight does not bypass captchas.",
        )
    if profile.robots_disallows_collection:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason="Robots policy disallows collection for the intended path.",
        )
    if profile.terms_disallow_collection:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason="Source terms disallow the intended automated collection.",
        )
    if profile.paywalled:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason=(
                "Source is paywalled; ConstructionSight only collects lawfully "
                "accessible public data."
            ),
        )

    return AccessPolicyResult(
        decision=AccessDecision.ALLOWED,
        reason="No known access restriction blocks lawful public collection.",
    )
