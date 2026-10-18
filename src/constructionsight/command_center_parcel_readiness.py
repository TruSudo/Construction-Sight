"""Read-only native projection of established original parcel source operator reports.

No network collection, source status promotion or parcel/site identity is inferred.
The original registry, schema preview, assurance evidence, coverage and bounded
ArcGIS assessment services remain the single sources of these observations.
"""

from __future__ import annotations

from typing import Any

from constructionsight.parcel_row_preview import preview_rows
from constructionsight.parcel_row_preview_models import ParcelRowPreviewInput
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


def preview_retained_parcel_sample(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the original parcel row-preview service on bounded operator sample rows.

    Never accepts client-chosen field mappings, provider URLs or authority flags.
    The output is an unretained preview, not an investigated site or parcel proof.
    """
    if set(payload) != {"source_key", "rows"}:
        raise ValueError("exact parcel source and sample rows required")
    source_key, rows = payload["source_key"], payload["rows"]
    if not isinstance(source_key, str):
        raise ValueError("registered parcel source key required")
    source = next(
        (source for source in get_parcel_sources() if source.source_key == source_key),
        None,
    )
    if source is None or source_key not in {
        item.source_key for item in get_verified_parcel_source_profiles()
    }:
        raise ValueError("existing evidence-backed county parcel source required")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
        raise ValueError("parcel row preview requires 1 to 20 sample rows")
    allowed = {field.source_field for field in source.field_mappings}
    total_bytes = 0
    for row in rows:
        if not isinstance(row, dict) or not row or len(row) > len(allowed):
            raise ValueError("sample parcel rows must contain mapped source fields")
        if (
            any(not isinstance(key, str) or key not in allowed for key in row)
            or any(not isinstance(value, str) for value in row.values())
        ):
            raise ValueError("sample rows require exact registered text fields")
        total_bytes += sum(len(key.encode()) + len(value.encode()) for key, value in row.items())
        if total_bytes > 32_000:
            raise ValueError("parcel sample exceeds bounded preview size")
    schema = preview_schema_for_source_key(source_key)
    original_input = ParcelRowPreviewInput(
        source_key=source.source_key,
        source_name=source.source_name,
        source_format=source.source_format,
        field_role_matches=schema.mapped_fields,
        constant_fields=schema.constant_fields,
        rows=rows,
        geometry_support=source.coverage.geometry_support,
        spatial_reference=schema.spatial_reference,
        source_url=source.source_url,
        limitations=schema.limitations,
    )
    return {
        "schema_version": "constructionsight.native-parcel-row-preview/v1",
        "original_operator_service_reused": True,
        "network_executed": False,
        "rows_retained": False,
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
        "manual_unverified_sample": True,
        "report": preview_rows(original_input).to_dict(),
    }
