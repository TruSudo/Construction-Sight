from constructionsight.adapters.coverage import audit_source_adapter_coverage
from constructionsight.adapters.registry import AdapterRegistry, default_adapter_registry
from constructionsight.adapters.specs import default_adapter_family_specs
from constructionsight.models import PlatformFamily, PublicSource


def _source(platform_family: str = "accela_aca") -> PublicSource:
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
            "platform_family": platform_family,
            "public_url": "https://example.gov/records",
            "record_categories": ["permit"],
        }
    )


def test_source_adapter_coverage_passes_for_supported_source() -> None:
    result = audit_source_adapter_coverage(
        [_source("accela_aca")],
        default_adapter_registry(),
        default_adapter_family_specs(),
    )

    assert result.passed is True
    assert result.source_count == 1
    assert result.issues == ()


def test_source_adapter_coverage_detects_missing_registration() -> None:
    result = audit_source_adapter_coverage(
        [_source("accela_aca")],
        AdapterRegistry(),
        default_adapter_family_specs(),
    )

    assert result.passed is False
    assert result.issues[0].source_name == "Synthetic Source"
    assert result.issues[0].platform_family is PlatformFamily.ACCELA_ACA
    assert result.issues[0].issue == "missing adapter registration"


def test_source_adapter_coverage_detects_missing_specification() -> None:
    result = audit_source_adapter_coverage(
        [_source("accela_aca")],
        default_adapter_registry(),
        {},
    )

    assert result.passed is False
    assert result.issues[0].source_name == "Synthetic Source"
    assert result.issues[0].platform_family is PlatformFamily.ACCELA_ACA
    assert result.issues[0].issue == "missing adapter family specification"
