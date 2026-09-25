from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
)
from constructionsight.legal import SourceAccessProfile
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.verification.source_verifier import SourceVerifier


def _source(url: str = "https://ezop.sbcounty.gov/citizenaccess/") -> PublicSource:
    return PublicSource.model_validate(
        {
            "jurisdiction": {
                "name": "Example City",
                "county": "San Bernardino",
                "state": "CA",
                "jurisdiction_type": "city",
            },
            "source_name": "Example ACA Portal",
            "source_type": "city_portal",
            "platform_family": "accela_aca",
            "public_url": url,
            "record_categories": ["permit"],
        }
    )


def _reviewed_access_profile(url: str) -> SourceAccessProfile:
    return SourceAccessProfile(
        public_url=url,
        requires_login=False,
        has_captcha=False,
        robots_disallows_collection=False,
        terms_disallow_collection=False,
        paywalled=False,
        access_fact_basis="review:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )


def _executor(
    *,
    body: bytes = b"",
    status_code: int | None = 200,
    failure_kind: HttpFailureKind = HttpFailureKind.NONE,
    error_type: str | None = None,
):
    def execute(
        url: str,
        method: str,
        policy: BoundedHttpPolicy,
    ) -> BoundedHttpObservation:
        assert method == "GET"
        assert policy.policy_id == "CS-NET-008"
        return BoundedHttpObservation(
            policy_id=policy.policy_id,
            method=method,
            request_url=url,
            final_url=url,
            status_code=status_code,
            content_type="text/html" if status_code is not None else None,
            content_encoding="utf-8" if status_code is not None else None,
            response_body=body,
            response_size=len(body),
            body_truncated=False,
            failure_kind=failure_kind,
            error_type=error_type,
            error_detail=None,
        )

    return execute


def test_verifier_detects_accela_public_search_hints() -> None:
    verifier = SourceVerifier(
        executor=_executor(
            body=(
                b"Citizen Access permit search record search contractor owner applicant "
                b"Cap/CapHome.aspx"
            )
        )
    )

    source = _source()
    result = verifier.verify(
        source,
        access_profile=_reviewed_access_profile(str(source.public_url)),
    )

    assert result.url_reachable is True
    assert result.portal_type_detected is PlatformFamily.ACCELA_ACA
    assert result.public_search_available is True
    assert result.permit_details_visible is True
    assert result.contractor_owner_applicant_fields_visible is True
    assert result.confidence_score >= 80


def test_verifier_flags_login_hints() -> None:
    verifier = SourceVerifier(
        executor=_executor(body=b"Login required. Please enter username and password.")
    )

    source = _source("https://www.cslb.ca.gov/")
    result = verifier.verify(
        source,
        access_profile=_reviewed_access_profile(str(source.public_url)),
    )

    assert result.url_reachable is True
    assert result.login_required is True
    assert result.confidence_score < 80


def test_verifier_preserves_transport_failure_class() -> None:
    verifier = SourceVerifier(
        executor=_executor(
            status_code=None,
            failure_kind=HttpFailureKind.TRANSPORT,
            error_type="ConnectError",
        )
    )

    source = _source()
    result = verifier.verify(
        source,
        access_profile=_reviewed_access_profile(str(source.public_url)),
    )

    assert result.url_reachable is False
    assert result.portal_type_detected is PlatformFamily.UNKNOWN
    assert result.confidence_score == 0
    assert result.notes == "HTTP verification failed closed: transport_failure"
    assert result.raw_observations["failure_kind"] == "transport_failure"


def test_verifier_does_not_touch_network_when_access_facts_are_unknown() -> None:
    calls = 0

    def forbidden_executor(
        url: str,
        method: str,
        policy: BoundedHttpPolicy,
    ) -> BoundedHttpObservation:
        nonlocal calls
        calls += 1
        raise AssertionError("network executor must not run for unknown access facts")

    source = _source()
    result = SourceVerifier(executor=forbidden_executor).verify(source)

    assert calls == 0
    assert result.url_reachable is False
    assert result.confidence_score == 0
    assert result.raw_observations["access_decision"] == "review_required"
    assert "unknown" in (result.notes or "").lower()


def test_verifier_rejects_access_facts_bound_to_different_source_url() -> None:
    source = _source()

    result = SourceVerifier(executor=_executor()).verify(
        source,
        access_profile=_reviewed_access_profile("https://example.gov/other"),
    )

    assert result.url_reachable is False
    assert result.raw_observations["access_decision"] == "review_required"
    assert "exact source URL" in (result.notes or "")
