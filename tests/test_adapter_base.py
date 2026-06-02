from collections.abc import Iterable

from constructionsight.adapters.base import (
    AdapterOutcome,
    AdapterSearchDescriptor,
    SourceAdapter,
)
from constructionsight.legal import SourceAccessProfile
from constructionsight.models import PlatformFamily, PublicSource, SourceVerificationResult
from constructionsight.site_models import Site


class SyntheticAdapter(SourceAdapter[dict[str, str], Site]):
    def verify_source(self) -> SourceVerificationResult:
        return SourceVerificationResult(
            source_name=self.source_name,
            public_url=self.source.public_url,
            url_reachable=True,
            portal_type_detected=PlatformFamily.UNKNOWN,
            confidence_score=50,
        )

    def discover_search(self) -> list[AdapterSearchDescriptor]:
        return [
            AdapterSearchDescriptor(
                source_name=self.source_name,
                search_name="Synthetic Search",
                public_url=str(self.source.public_url),
            )
        ]

    def list_records(self) -> Iterable[dict[str, str]]:
        return ({"site_key": "site:test:001", "county": "Test County"},)

    def extract_record_detail(self, record: dict[str, str]) -> dict[str, str]:
        return record

    def normalize(self, record: dict[str, str]) -> Site:
        return Site.model_validate(record)


def _source() -> PublicSource:
    return PublicSource.model_validate(
        {
            "jurisdiction": {
                "name": "Test Jurisdiction",
                "county": "Test County",
                "state": "CA",
                "jurisdiction_type": "city",
            },
            "source_name": "Synthetic Source",
            "source_type": "city_portal",
            "platform_family": "unknown",
            "public_url": "https://example.gov/records",
            "record_categories": ["permit"],
        }
    )


def test_adapter_preflight_allows_plain_public_source() -> None:
    adapter = SyntheticAdapter(_source())

    result = adapter.preflight()

    assert result.allowed is True


def test_adapter_blocked_result_for_captcha_source() -> None:
    adapter = SyntheticAdapter(_source())
    access_result = adapter.preflight(
        SourceAccessProfile(public_url="https://example.gov/records", has_captcha=True)
    )

    result = adapter.blocked_result("list_records", access_result)

    assert result.outcome is AdapterOutcome.BLOCKED
    assert result.succeeded is False
    assert result.errors[0].recoverable is False


def test_adapter_skipped_result_for_login_review_source() -> None:
    adapter = SyntheticAdapter(_source())
    access_result = adapter.preflight(
        SourceAccessProfile(public_url="https://example.gov/records", requires_login=True)
    )

    result = adapter.blocked_result("list_records", access_result)

    assert result.outcome is AdapterOutcome.SKIPPED
    assert result.succeeded is False
    assert result.errors[0].recoverable is True


def test_adapter_search_descriptor_validation() -> None:
    descriptor = AdapterSearchDescriptor(
        source_name="Synthetic Source",
        search_name="Synthetic Search",
        public_url="https://example.gov/records",
        method="GET",
        record_types=["permit"],
    )

    assert descriptor.search_name == "Synthetic Search"
    assert descriptor.record_types == ["permit"]
