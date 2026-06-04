from collections.abc import Iterable

from constructionsight.adapters.base import (
    AdapterRunContext,
    AdapterSearchDescriptor,
    SourceAdapter,
)
from constructionsight.adapters.runner import AdapterRunner
from constructionsight.legal import SourceAccessProfile
from constructionsight.models import PlatformFamily, PublicSource, SourceVerificationResult
from constructionsight.site_models import Site


class RunnerSyntheticAdapter(SourceAdapter[dict[str, str], Site]):
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
        return (
            {"site_key": "site:test:001", "county": "Test County"},
            {"site_key": "site:test:002", "county": "Test County"},
        )

    def extract_record_detail(self, record: dict[str, str]) -> dict[str, str]:
        return record

    def normalize(self, record: dict[str, str]) -> Site:
        return Site.model_validate(record)


class BlockingSyntheticAdapter(RunnerSyntheticAdapter):
    def preflight(self, profile: SourceAccessProfile | None = None):
        return super().preflight(
            SourceAccessProfile(public_url=str(self.source.public_url), has_captcha=True)
        )


class FailingSyntheticAdapter(RunnerSyntheticAdapter):
    def list_records(self) -> Iterable[dict[str, str]]:
        raise RuntimeError("synthetic adapter failure")


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


def test_adapter_runner_successfully_normalizes_records() -> None:
    adapter = RunnerSyntheticAdapter(_source())
    result = AdapterRunner().run_adapter(adapter)

    assert result.succeeded is True
    assert len(result.records) == 2
    assert result.records[0].site_key == "site:test:001"


def test_adapter_runner_respects_max_records() -> None:
    adapter = RunnerSyntheticAdapter(_source(), AdapterRunContext(max_records=1))
    result = AdapterRunner().run_adapter(adapter)

    assert result.succeeded is True
    assert len(result.records) == 1


def test_adapter_runner_returns_blocked_result_on_preflight_block() -> None:
    adapter = BlockingSyntheticAdapter(_source())
    result = AdapterRunner().run_adapter(adapter)

    assert result.succeeded is False
    assert result.outcome.value == "blocked"
    assert result.errors[0].recoverable is False


def test_adapter_runner_returns_failure_result_on_adapter_exception() -> None:
    adapter = FailingSyntheticAdapter(_source())
    result = AdapterRunner().run_adapter(adapter)

    assert result.succeeded is False
    assert result.outcome.value == "failed"
    assert result.errors[0].details == {"exception_type": "RuntimeError"}
