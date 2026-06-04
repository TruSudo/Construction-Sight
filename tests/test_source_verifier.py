import httpx

from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.verification.source_verifier import SourceVerifier


class FakeClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    def get(self, url: str, *, follow_redirects: bool, timeout: float) -> httpx.Response:
        request = httpx.Request("GET", url)
        self.response.request = request
        return self.response


def _source(url: str = "https://example.gov/citizenaccess/") -> PublicSource:
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


def test_verifier_detects_accela_public_search_hints() -> None:
    response = httpx.Response(
        200,
        text=(
            "Citizen Access permit search record search contractor owner applicant "
            "Cap/CapHome.aspx"
        ),
        headers={"content-type": "text/html"},
    )
    verifier = SourceVerifier(client=FakeClient(response))

    result = verifier.verify(_source())

    assert result.url_reachable is True
    assert result.portal_type_detected is PlatformFamily.ACCELA_ACA
    assert result.public_search_available is True
    assert result.permit_details_visible is True
    assert result.contractor_owner_applicant_fields_visible is True
    assert result.confidence_score >= 80


def test_verifier_flags_login_hints() -> None:
    response = httpx.Response(
        200,
        text="Login required. Please enter username and password.",
        headers={"content-type": "text/html"},
    )
    verifier = SourceVerifier(client=FakeClient(response))

    result = verifier.verify(_source("https://example.gov/login"))

    assert result.url_reachable is True
    assert result.login_required is True
    assert result.confidence_score < 80


def test_verifier_handles_http_error() -> None:
    class ErrorClient:
        def get(self, url: str, *, follow_redirects: bool, timeout: float) -> httpx.Response:
            raise httpx.ConnectError("network down")

    verifier = SourceVerifier(client=ErrorClient())

    result = verifier.verify(_source())

    assert result.url_reachable is False
    assert result.portal_type_detected is PlatformFamily.UNKNOWN
    assert result.confidence_score == 0
    assert "HTTP request failed" in str(result.notes)
