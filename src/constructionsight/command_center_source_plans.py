"""Read-only native projections of original source planning services."""

from __future__ import annotations

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_registry_update_plan_service import build_source_registry_update_plan


def original_offline_source_plans(sources: list[PublicSource]) -> dict[str, object]:
    """Build original dry-run plans without HTTP, registry mutation or approval."""
    adapters = default_adapter_family_specs()
    return {
        "original_promotion_plan": build_source_promotion_plan(
            sources, adapters, check_http=False,
        ).to_dict(),
        "original_registry_update_plan": build_source_registry_update_plan(
            sources, adapters, check_http=False,
        ).to_dict(),
        "network_executed": False,
        "registry_mutated": False,
        "source_promotion_authorized": False,
    }
