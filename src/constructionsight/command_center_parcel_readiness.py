"""Read-only native projection of established original parcel source operator reports.

No network collection, source status promotion or parcel/site identity is inferred.
The original registry, schema preview, assurance evidence, coverage and bounded
ArcGIS assessment services remain the single sources of these observations.
"""

from __future__ import annotations

from typing import Any

from constructionsight.parcel_schema_preview import preview_schema_for_source_key
from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_acquisition_assessments,
)
from constructionsight.parcel_source_registry import (
    build_parcel_source_report,
    get_parcel_sources,
    parcel_source_matrix_rows,
)
from constructionsight.parcel_source_verification import (
    build_parcel_county_coverage_report,
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)


def parcel_source_readiness_snapshot() -> dict[str, Any]:
    """Return exact original CLI-backed parcel source reports without side effects."""
    sources = get_parcel_sources()
    return {
        "schema_version": "constructionsight.native-parcel-source-readiness/v1",
        "read_only": True,
        "original_operator_services_reused": True,
        "network_executed": False,
        "parcel_source_persisted": False,
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
        "source_observations_are_historical": True,
        "sources": parcel_source_matrix_rows(sources),
        "registry_report": build_parcel_source_report(sources).model_dump(mode="json"),
        "county_coverage": build_parcel_county_coverage_report().to_dict(),
        "profiles": [
            item.to_dict() for item in get_verified_parcel_source_profiles()
        ],
        "evidence": [item.to_dict() for item in get_parcel_source_evidence()],
        "acquisition_assessments": [
            item.to_dict() for item in get_official_arcgis_acquisition_assessments()
        ],
        "schemas": {
            source.source_key: preview_schema_for_source_key(source.source_key).model_dump(
                mode="json"
            )
            for source in sources
        },
        "limitations": [
            "Observed parcel/GIS metadata and expected fields are not a current source probe.",
            "Registry readiness does not establish complete coverage or parcel persistence.",
            "No licensed provider access, remote requests or manual source verification granted.",
            "An APN or shared location alone never proves common construction project identity.",
        ],
    }
