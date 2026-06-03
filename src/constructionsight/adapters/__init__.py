"""Adapter package for ConstructionSight source integrations."""

from constructionsight.adapters.audit import (
    AdapterContractAuditResult,
    audit_adapter_contracts,
)
from constructionsight.adapters.registry import (
    AdapterLookupError,
    AdapterRegistry,
    default_adapter_registry,
)
from constructionsight.adapters.specs import (
    AdapterFamilySpec,
    AdapterImplementationStatus,
    default_adapter_family_specs,
)

__all__ = [
    "AdapterContractAuditResult",
    "AdapterFamilySpec",
    "AdapterImplementationStatus",
    "AdapterLookupError",
    "AdapterRegistry",
    "audit_adapter_contracts",
    "default_adapter_family_specs",
    "default_adapter_registry",
]
