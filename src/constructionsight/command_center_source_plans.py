"""Read-only native projections of original source planning services."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_registry_update_plan_service import build_source_registry_update_plan
from constructionsight.source_verification_checklist_models import SourceVerificationObservation


def original_offline_source_plans(
    sources: list[PublicSource],
    *,
    observations: Iterable[SourceVerificationObservation] | None = None,
) -> dict[str, object]:
    """Build original dry-run plans without HTTP, registry mutation or approval."""
    adapters = default_adapter_family_specs()
    reviewed = tuple(observations) if observations is not None else None
    return {
        "original_promotion_plan": build_source_promotion_plan(
            sources, adapters, check_http=False, observations=reviewed,
        ).to_dict(),
        "original_registry_update_plan": build_source_registry_update_plan(
            sources, adapters, check_http=False, observations=reviewed,
        ).to_dict(),
        "network_executed": False,
        "registry_mutated": False,
        "source_promotion_authorized": False,
    }
