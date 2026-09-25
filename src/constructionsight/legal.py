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
    """Reviewed public-access facts known about a source before collection.

    Restriction flags default to false because they represent observed facts, but
    false flags are not themselves evidence that restrictions were checked.
    access_facts_reviewed plus a nonblank review_basis is therefore required
    before an otherwise clear profile may authorize collection.
    """

    public_url: str
    requires_login: bool = False
    has_captcha: bool = False
    robots_disallows_collection: bool = False
    terms_disallow_collection: bool = False
    paywalled: bool = False
    rate_limit_known: bool = False
    rate_limit_notes: str | None = None
    access_facts_reviewed: bool = False
    review_basis: str | None = None


def evaluate_access(profile: SourceAccessProfile) -> AccessPolicyResult:
    """Evaluate whether a source may be collected by ConstructionSight.

    Explicit restrictions fail closed immediately. An all-clear profile is
    allowed only when its restriction facts were affirmatively reviewed and the
    review basis is retained. Unknown restriction facts require review.
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

    review_basis = (profile.review_basis or "").strip()
    if not profile.access_facts_reviewed or not review_basis:
        return AccessPolicyResult(
            decision=AccessDecision.REVIEW_REQUIRED,
            reason=(
                "Source restriction facts are not affirmatively reviewed with a retained "
                "basis; unknown access conditions cannot authorize collection."
            ),
        )

    return AccessPolicyResult(
        decision=AccessDecision.ALLOWED,
        reason=(
            "Reviewed access facts identify no restriction blocking lawful public "
            f"collection. Review basis: {review_basis}"
        ),
    )
