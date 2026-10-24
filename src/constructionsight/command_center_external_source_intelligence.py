"""Native read-only equivalence for original external capability and gap registries.

These are historical capability/research records, never a current subscription,
source acquisition, vendor entitlement, verified coverage or commercial authority.
"""

from __future__ import annotations

from typing import Any

from constructionsight.external_gap_registry import (
    build_gap_alignment_report,
    gap_matrix_rows,
    get_implementation_steps,
    get_knowledge_gaps,
    roadmap_rows,
)
from constructionsight.external_intelligence_registry import (
    build_capability_gap_report,
    capability_matrix_rows,
    get_external_capabilities,
)


def original_external_source_intelligence() -> dict[str, Any]:
    """Project original static Shovels/Regrid research services without network."""
    capabilities = get_external_capabilities()
    gaps = get_knowledge_gaps()
    steps = get_implementation_steps()
    return {
        "schema_version": "constructionsight.native-original-source-intelligence/v1",
        "original_capability_matrix": capability_matrix_rows(capabilities),
        "original_capability_gap_report": build_capability_gap_report(
            capabilities
        ).model_dump(mode="json"),
        "original_research_gap_matrix": gap_matrix_rows(gaps),
        "original_alignment_report": build_gap_alignment_report().model_dump(mode="json"),
        "original_implementation_roadmap": roadmap_rows(steps),
        "read_only": True,
        "network_executed": False,
        "vendor_subscription_configured": False,
        "current_external_coverage_verified": False,
        "source_database_mutated": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Original historic reference capabilities and implementation-gap research. "
            "The report does not establish current Shovels/Regrid coverage, entitlement, "
            "vendor API access, contractual permission or completion of those targets."
        ),
    }
