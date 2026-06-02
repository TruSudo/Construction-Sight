from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access


def test_public_source_without_known_restrictions_is_allowed() -> None:
    profile = SourceAccessProfile(public_url="https://example.gov/public-records")

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.ALLOWED
    assert result.allowed is True


def test_captcha_source_is_blocked() -> None:
    profile = SourceAccessProfile(public_url="https://example.gov/search", has_captcha=True)

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.BLOCKED
    assert result.allowed is False


def test_login_source_requires_review() -> None:
    profile = SourceAccessProfile(public_url="https://example.gov/login", requires_login=True)

    result = evaluate_access(profile)

    assert result.decision is AccessDecision.REVIEW_REQUIRED
    assert result.allowed is False
