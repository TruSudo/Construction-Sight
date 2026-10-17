from dataclasses import replace

import pytest

from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access


def test_unreviewed_all_clear_source_requires_review() -> None:
    profile = SourceAccessProfile(public_url="https://example.gov/public-records")

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False
    assert "unknown" in result.reason


def test_reviewed_public_source_without_restrictions_is_allowed() -> None:
    profile = SourceAccessProfile(
        public_url="https://example.gov/public-records",
        access_facts_reviewed=True,
        review_basis="Reviewed public portal and source terms on 2026-09-25.",
        requires_login=False,
        has_captcha=False,
        robots_disallows_collection=False,
        terms_disallow_collection=False,
        paywalled=False,
        access_fact_basis="review:" + "a" * 64,
    )

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.ALLOWED
    assert result.allowed is True
    assert "review:" + "a" * 64 in result.reason


def test_review_flag_without_basis_still_requires_review() -> None:
    profile = SourceAccessProfile(
        public_url="https://example.gov/public-records",
        access_facts_reviewed=True,
    )

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False


def test_captcha_source_is_blocked_even_without_review_basis() -> None:
    profile = SourceAccessProfile(public_url="https://example.gov/search", has_captcha=True)

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.BLOCKED
    assert result.allowed is False


def test_login_source_requires_review() -> None:
    profile = SourceAccessProfile(public_url="https://example.gov/login", requires_login=True)

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False


RESTRICTIONS = (
    "requires_login", "has_captcha", "robots_disallows_collection",
    "terms_disallow_collection", "paywalled",
)


def _known_profile() -> SourceAccessProfile:
    return SourceAccessProfile(
        public_url="https://example.test/", requires_login=False, has_captcha=False,
        robots_disallows_collection=False, terms_disallow_collection=False, paywalled=False,
        access_fact_basis="evidence:" + "a" * 64,
    )


@pytest.mark.parametrize("fact", RESTRICTIONS)
@pytest.mark.parametrize("unknown", [None, 0, "false"])
def test_unknown_or_nonboolean_fact_cannot_be_overridden_by_review(fact, unknown):
    profile = replace(_known_profile(), **{fact: unknown}, access_facts_reviewed=True,
                      review_basis="Legacy all-clear text")
    result = evaluate_access(profile)
    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert fact in result.reason


@pytest.mark.parametrize("basis", [None, "", "Reviewed today", "review:abc", "review:" + "A" * 64])
def test_all_clear_facts_need_immutable_review_or_evidence_identity(basis):
    profile = replace(_known_profile(), access_fact_basis=basis,
                      access_facts_reviewed=True, review_basis="Legacy reviewed text")
    assert evaluate_access(profile).decision is AccessDecision.REVIEW_REQUIRED


def test_omitted_facts_remain_unknown_even_with_immutable_basis():
    result = evaluate_access(SourceAccessProfile(
        public_url="https://example.test/", access_fact_basis="review:" + "a" * 64,
    ))
    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert all(fact in result.reason for fact in RESTRICTIONS)
