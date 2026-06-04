"""Adapter registry for ConstructionSight."""

from __future__ import annotations

from typing import Any, TypeAlias

from constructionsight.adapters.base import AdapterRunContext, SourceAdapter
from constructionsight.adapters.ceqanet import CeqanetAdapter
from constructionsight.adapters.stub import (
    AccelaAcaAdapter,
    CivicplusPrimegovAdapter,
    CslbAdapter,
    CustomReportAdapter,
    GranicusLegistarAdapter,
    LaserficheAdapter,
    TylerEnergovAdapter,
)
from constructionsight.models import PlatformFamily, PublicSource


class AdapterLookupError(ValueError):
    """Raised when an adapter lookup cannot be completed."""


AdapterClass: TypeAlias = type[SourceAdapter[Any, Any]]
AdapterInstance: TypeAlias = SourceAdapter[Any, Any]


class AdapterRegistry:
    """Map platform families to adapter classes."""

    def __init__(self) -> None:
        self._adapters: dict[PlatformFamily, AdapterClass] = {}

    def add(self, platform_family: PlatformFamily, adapter_class: AdapterClass) -> None:
        """Add an adapter class for a platform family."""

        if platform_family in self._adapters:
            raise AdapterLookupError(f"adapter already exists for {platform_family.value}")
        self._adapters[platform_family] = adapter_class

    def get(self, platform_family: PlatformFamily) -> AdapterClass:
        """Return the adapter class for a platform family."""

        adapter_class = self._adapters.get(platform_family)
        if adapter_class is None:
            raise AdapterLookupError(f"no adapter exists for {platform_family.value}")
        return adapter_class

    def create(
        self,
        source: PublicSource,
        context: AdapterRunContext | None = None,
    ) -> AdapterInstance:
        """Create the adapter instance for a source."""

        return self.get(source.platform_family)(source, context)

    def supported_platforms(self) -> tuple[PlatformFamily, ...]:
        """Return supported platform families in deterministic order."""

        return tuple(sorted(self._adapters, key=lambda family: family.value))


def default_adapter_registry() -> AdapterRegistry:
    """Create the default adapter registry."""

    registry = AdapterRegistry()
    registry.add(PlatformFamily.CEQANET, CeqanetAdapter)
    registry.add(PlatformFamily.CSLB, CslbAdapter)
    registry.add(PlatformFamily.ACCELA_ACA, AccelaAcaAdapter)
    registry.add(PlatformFamily.TYLER_ENERGOV, TylerEnergovAdapter)
    registry.add(PlatformFamily.GRANICUS_LEGISTAR, GranicusLegistarAdapter)
    registry.add(PlatformFamily.CIVICPLUS_PRIMEGOV, CivicplusPrimegovAdapter)
    registry.add(PlatformFamily.LASERFICHE, LaserficheAdapter)
    registry.add(PlatformFamily.CUSTOM_REPORT, CustomReportAdapter)
    return registry
