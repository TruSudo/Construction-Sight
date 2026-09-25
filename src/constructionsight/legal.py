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
    """Evidence/review-bound public access facts known before collection.

    Restriction facts are tri-state. None means the fact has not been
    established and therefore cannot authorize live collection. An all-clear
    profile also requires a nonblank access_fact_basis that identifies the
    retained evidence or reviewed artifact supporting the asserted facts.
    """

    public_url: str
    requires_login: bool | None = None
    has_captcha: bool | None = None
    robots_disallows_collection: bool | None = None
    terms_disallow_collection: bool | None = None
    paywalled: bool | None = None
    access_fact_basis: str | None = None
    rate_limit_known: bool = False
    rate_limit_notes: str | None = None


_RESTRICTION_FACTS = (
    "requires_login",
    "has_captcha",
    "robots_disallows_collection",
    "terms_disallow_collection",
    "paywalled",
)


def evaluate_access(profile: SourceAccessProfile) -> AccessPolicyResult:
    """Evaluate whether a source may be collected by ConstructionSight.

    Known restrictions fail closed. Unknown restriction facts require review.
    An all-clear profile is allowed only when the caller binds those facts to a
    retained evidence or reviewed-artifact identity.
    """

    if profile.requires_login is True:
        return AccessPolicyResult(
            decision=AccessDecision.REVIEW_REQUIRED,
            reason=(
                "Source requires login (requires_login=true); verify lawful credentials "
                "and source terms before access."
            ),
        )
    if profile.has_captcha is True:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason="Source presents captcha; ConstructionSight does not bypass captchas.",
        )
    if profile.robots_disallows_collection is True:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason="Robots policy disallows collection for the intended path.",
        )
    if profile.terms_disallow_collection is True:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason="Source terms disallow the intended automated collection.",
        )
    if profile.paywalled is True:
        return AccessPolicyResult(
            decision=AccessDecision.BLOCKED,
            reason=(
                "Source is paywalled; ConstructionSight only collects lawfully "
                "accessible public data."
            ),
        )

    unknown_facts = [
        fact_name
        for fact_name in _RESTRICTION_FACTS
        if getattr(profile, fact_name) is None
    ]
    if unknown_facts:
        return AccessPolicyResult(
            decision=AccessDecision.REVIEW_REQUIRED,
            reason=(
                "Lawful-access restriction facts are unknown: "
                + ", ".join(unknown_facts)
                + ". Establish and retain reviewed access facts before live access."
            ),
        )

    fact_basis = profile.access_fact_basis
    if fact_basis is None or not fact_basis.strip():
        return AccessPolicyResult(
            decision=AccessDecision.REVIEW_REQUIRED,
            reason=(
                "Lawful-access restriction facts have no retained evidence or reviewed "
                "fact basis; an all-clear profile cannot authorize live access."
            ),
        )

    return AccessPolicyResult(
        decision=AccessDecision.ALLOWED,
        reason="Reviewed access facts identify no restriction blocking public collection.",
    )
