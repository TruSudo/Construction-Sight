"""Adapter contract audit utilities."""

from __future__ import annotations

from dataclasses import dataclass

from constructionsight.adapters.registry import AdapterRegistry
from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.models import PlatformFamily


@dataclass(frozen=True)
class AdapterContractAuditResult:
    """Result of comparing adapter registry coverage with adapter specs."""

    registry_platforms: tuple[PlatformFamily, ...]
    spec_platforms: tuple[PlatformFamily, ...]
    missing_specs: tuple[PlatformFamily, ...]
    missing_registrations: tuple[PlatformFamily, ...]

    @property
    def passed(self) -> bool:
        """Return true when registry and spec platform coverage match."""

        return not self.missing_specs and not self.missing_registrations


def audit_adapter_contracts(
    registry: AdapterRegistry,
    specs: dict[PlatformFamily, AdapterFamilySpec],
) -> AdapterContractAuditResult:
    """Compare registered adapter families against declared adapter specs."""

    registry_platforms = registry.supported_platforms()
    spec_platforms = tuple(sorted(specs, key=lambda family: family.value))
    registry_set = set(registry_platforms)
    spec_set = set(spec_platforms)

    return AdapterContractAuditResult(
        registry_platforms=registry_platforms,
        spec_platforms=spec_platforms,
        missing_specs=tuple(sorted(registry_set - spec_set, key=lambda family: family.value)),
        missing_registrations=tuple(
            sorted(spec_set - registry_set, key=lambda family: family.value)
        ),
    )
