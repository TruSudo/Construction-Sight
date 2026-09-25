import pytest

from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access


def _reviewed_public_profile(**overrides: object) -> SourceAccessProfile:
    values: dict[str, object] = {
        "public_url": "https://example.gov/public-records",
        "requires_login": False,
        "has_captcha": False,
        "robots_disallows_collection": False,
        "terms_disallow_collection": False,
        "paywalled": False,
        "access_fact_basis": "review:test-access-policy",
    }
    values.update(overrides)
    return SourceAccessProfile(**values)


def test_reviewed_public_source_without_restrictions_is_allowed() -> None:
    result = evaluate_access(_reviewed_public_profile())

    assert result.decision is AccessDecision.ALLOWED
    assert result.allowed is True


def test_all_clear_profile_without_fact_basis_requires_review() -> None:
    profile = _reviewed_public_profile(access_fact_basis=None)

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False
    assert "fact basis" in result.reason


@pytest.mark.parametrize(
    "field_name",
    [
        "requires_login",
        "has_captcha",
        "robots_disallows_collection",
        "terms_disallow_collection",
        "paywalled",
    ],
)
def test_unknown_restriction_fact_requires_review(field_name: str) -> None:
    profile = _reviewed_public_profile(**{field_name: None})

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False
    assert field_name in result.reason


def test_captcha_source_is_blocked_even_when_other_facts_are_unknown() -> None:
    profile = SourceAccessProfile(
        public_url="https://example.gov/search",
        has_captcha=True,
    )

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.BLOCKED
    assert result.allowed is False


def test_login_source_requires_review_even_when_other_facts_are_unknown() -> None:
    profile = SourceAccessProfile(
        public_url="https://example.gov/login",
        requires_login=True,
    )

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False
