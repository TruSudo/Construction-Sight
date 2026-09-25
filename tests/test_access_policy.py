from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access


def test_unreviewed_all_clear_source_requires_review() -> None:
    profile = SourceAccessProfile(public_url="https://example.gov/public-records")

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False
    assert "not affirmatively reviewed" in result.reason


def test_reviewed_public_source_without_restrictions_is_allowed() -> None:
    profile = SourceAccessProfile(
        public_url="https://example.gov/public-records",
        access_facts_reviewed=True,
        review_basis="Reviewed public portal and source terms on 2026-09-25.",
    )

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.ALLOWED
    assert result.allowed is True
    assert "Review basis:" in result.reason


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
