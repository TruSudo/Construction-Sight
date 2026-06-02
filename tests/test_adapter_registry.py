import pytest

from constructionsight.adapters.registry import (
    AdapterLookupError,
    AdapterRegistry,
    default_adapter_registry,
)
from constructionsight.adapters.stub import AccelaAcaAdapter, TylerEnergovAdapter
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


def test_default_registry_supports_expected_platforms() -> None:
    registry = default_adapter_registry()

    platforms = registry.supported_platforms()

    assert PlatformFamily.ACCELA_ACA in platforms
    assert PlatformFamily.TYLER_ENERGOV in platforms
    assert PlatformFamily.CEQANET in platforms
    assert PlatformFamily.CSLB in platforms


def test_registry_creates_adapter_for_source_platform() -> None:
    registry = default_adapter_registry()

    adapter = registry.create(_source("tyler_energov"))

    assert isinstance(adapter, TylerEnergovAdapter)
    assert adapter.source_name == "Synthetic Source"


def test_registry_rejects_duplicate_registration() -> None:
    registry = AdapterRegistry()
    registry.add(PlatformFamily.ACCELA_ACA, AccelaAcaAdapter)

    with pytest.raises(AdapterLookupError):
        registry.add(PlatformFamily.ACCELA_ACA, AccelaAcaAdapter)


def test_registry_rejects_missing_platform_lookup() -> None:
    registry = AdapterRegistry()

    with pytest.raises(AdapterLookupError):
        registry.get(PlatformFamily.UNKNOWN)


def test_placeholder_adapter_discovers_search_descriptor() -> None:
    registry = default_adapter_registry()
    adapter = registry.create(_source("accela_aca"))

    descriptors = adapter.discover_search()

    assert len(descriptors) == 1
    assert descriptors[0].source_name == "Synthetic Source"
    assert descriptors[0].record_types == ["permit"]
