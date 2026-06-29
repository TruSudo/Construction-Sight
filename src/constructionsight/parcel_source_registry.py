"""Provider-neutral parcel source registry."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.parcel_source_models import (
    ParcelAccessBoundary,
    ParcelCoverageStatus,
    ParcelFieldMapping,
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelProviderKind,
    ParcelSource,
    ParcelSourceCoverage,
    ParcelSourceFormat,
    ParcelSourceGap,
    ParcelSourceRegistryReport,
)


def get_parcel_sources(
    *,
    county: str | None = None,
    provider_kind: ParcelProviderKind | None = None,
) -> list[ParcelSource]:
    """Return parcel source targets, optionally filtered."""

    sources = _default_parcel_sources()
    if county is not None:
        normalized_county = _normalize_county(county)
        sources = [
            source
            for source in sources
            if _normalize_county(source.coverage.county) == normalized_county
        ]
    if provider_kind is not None:
        sources = [source for source in sources if source.provider_kind == provider_kind]
    return sources


def parcel_source_matrix_rows(
    sources: Iterable[ParcelSource] | None = None,
) -> list[dict[str, str]]:
    """Return compact registry rows for CLI and UI tables."""

    reviewed = list(sources if sources is not None else get_parcel_sources())
    return [
        {
            "source_key": source.source_key,
            "source_name": source.source_name,
            "county": source.coverage.county,
            "provider_kind": source.provider_kind.value,
            "access_boundary": source.access_boundary.value,
            "coverage_status": source.coverage_status.value,
            "source_format": source.source_format.value,
            "geometry_support": source.coverage.geometry_support.value,
            "priority": str(source.priority),
            "next_action": source.next_action,
        }
        for source in reviewed
    ]


def build_parcel_source_report(
    sources: Iterable[ParcelSource] | None = None,
) -> ParcelSourceRegistryReport:
    """Build a source readiness report from parcel source targets."""

    reviewed = list(sources if sources is not None else get_parcel_sources())
    gaps = [_gap_for(source) for source in reviewed]
    counties = sorted({_normalize_county(gap.county) for gap in gaps})
    return ParcelSourceRegistryReport(
        report_id="parcel-source-registry-report:v1",
        sources_reviewed=len(reviewed),
        counties=counties,
        ready_sources=[
            gap
            for gap in gaps
            if gap.coverage_status
            in {
                ParcelCoverageStatus.READY_FOR_PREVIEW,
                ParcelCoverageStatus.READY_FOR_IMPORT,
            }
        ],
        target_sources=[
            gap
            for gap in gaps
            if gap.coverage_status in {ParcelCoverageStatus.TARGET, ParcelCoverageStatus.DESIGNED}
        ],
        blocked_sources=[
            gap for gap in gaps if gap.coverage_status == ParcelCoverageStatus.BLOCKED_BY_LICENSE
        ],
    )


def _gap_for(source: ParcelSource) -> ParcelSourceGap:
    """Convert a parcel source into a report row."""

    return ParcelSourceGap(
        source_key=source.source_key,
        source_name=source.source_name,
        county=source.coverage.county,
        provider_kind=source.provider_kind,
        access_boundary=source.access_boundary,
        coverage_status=source.coverage_status,
        priority=source.priority,
        next_action=source.next_action,
    )


def _default_parcel_sources() -> list[ParcelSource]:
    """Return first-phase parcel source targets."""

    return [
        ParcelSource(
            source_key="san-bernardino:county-gis-parcels",
            source_name="San Bernardino County parcel GIS target",
            provider_kind=ParcelProviderKind.COUNTY_GIS,
            access_boundary=ParcelAccessBoundary.PUBLIC_METADATA_ONLY,
            coverage_status=ParcelCoverageStatus.TARGET,
            source_format=ParcelSourceFormat.ARCGIS_FEATURE_SERVICE,
            coverage=ParcelSourceCoverage(
                county="San Bernardino",
                geometry_support=ParcelGeometrySupport.POLYGON,
                coverage_notes=[
                    "target county for Phase 1 parcel-first project anchoring",
                    "source URL must be verified before live import is implemented",
                ],
            ),
            field_mappings=_standard_parcel_field_targets(),
            priority=95,
            limitations=[
                "source endpoint not yet verified in this registry layer",
                "schema must be inspected before import preview",
            ],
            next_action="verify lawful public endpoint and capture schema preview",
        ),
        ParcelSource(
            source_key="riverside:county-gis-parcels",
            source_name="Riverside County parcel GIS target",
            provider_kind=ParcelProviderKind.COUNTY_GIS,
            access_boundary=ParcelAccessBoundary.PUBLIC_METADATA_ONLY,
            coverage_status=ParcelCoverageStatus.TARGET,
            source_format=ParcelSourceFormat.ARCGIS_FEATURE_SERVICE,
            coverage=ParcelSourceCoverage(
                county="Riverside",
                geometry_support=ParcelGeometrySupport.POLYGON,
                coverage_notes=[
                    "target county for Phase 1 parcel-first project anchoring",
                    "source URL must be verified before live import is implemented",
                ],
            ),
            field_mappings=_standard_parcel_field_targets(),
            priority=95,
            limitations=[
                "source endpoint not yet verified in this registry layer",
                "schema must be inspected before import preview",
            ],
            next_action="verify lawful public endpoint and capture schema preview",
        ),
        ParcelSource(
            source_key="regrid:licensed-parcel-provider",
            source_name="Regrid licensed parcel provider target",
            provider_kind=ParcelProviderKind.LICENSED_PROVIDER,
            access_boundary=ParcelAccessBoundary.LAWFUL_API_OR_LICENSE,
            coverage_status=ParcelCoverageStatus.BLOCKED_BY_LICENSE,
            source_format=ParcelSourceFormat.API_JSON,
            coverage=ParcelSourceCoverage(
                county="Multi-county",
                geometry_support=ParcelGeometrySupport.MIXED,
                coverage_notes=[
                    "licensed provider target for parcel geometry and enrichment parity",
                    "must remain optional so open county sources are first-class",
                ],
            ),
            documentation_url="https://regrid.com/api",
            field_mappings=_standard_parcel_field_targets(),
            priority=70,
            limitations=["requires lawful license or user-provided authorization"],
            next_action="support pluggable licensed provider once credentials/license exist",
        ),
        ParcelSource(
            source_key="user-provided:parcel-export",
            source_name="User-provided parcel export",
            provider_kind=ParcelProviderKind.USER_PROVIDED_FILE,
            access_boundary=ParcelAccessBoundary.USER_PROVIDED_FILE,
            coverage_status=ParcelCoverageStatus.DESIGNED,
            source_format=ParcelSourceFormat.UNKNOWN,
            coverage=ParcelSourceCoverage(
                county="User supplied",
                geometry_support=ParcelGeometrySupport.UNKNOWN,
                coverage_notes=[
                    "supports CSV, GeoJSON, shapefile, or other lawful user-provided exports",
                ],
            ),
            field_mappings=_standard_parcel_field_targets(),
            priority=85,
            limitations=["file schema must be mapped before import"],
            next_action="build import-preview path for user-provided parcel files",
        ),
    ]


def _standard_parcel_field_targets() -> list[ParcelFieldMapping]:
    """Return canonical field targets expected from parcel sources."""

    return [
        ParcelFieldMapping(source_field="apn", field_role=ParcelFieldRole.APN, required=True),
        ParcelFieldMapping(source_field="situs_address", field_role=ParcelFieldRole.ADDRESS),
        ParcelFieldMapping(source_field="owner_name", field_role=ParcelFieldRole.OWNER),
        ParcelFieldMapping(source_field="county", field_role=ParcelFieldRole.COUNTY, required=True),
        ParcelFieldMapping(source_field="jurisdiction", field_role=ParcelFieldRole.JURISDICTION),
        ParcelFieldMapping(source_field="zoning", field_role=ParcelFieldRole.ZONING),
        ParcelFieldMapping(source_field="land_use", field_role=ParcelFieldRole.LAND_USE),
        ParcelFieldMapping(source_field="acreage", field_role=ParcelFieldRole.ACREAGE),
        ParcelFieldMapping(source_field="geometry", field_role=ParcelFieldRole.GEOMETRY),
        ParcelFieldMapping(source_field="updated_at", field_role=ParcelFieldRole.UPDATED_AT),
    ]


def _normalize_county(value: str) -> str:
    """Normalize county names for filtering and reporting."""

    normalized = " ".join(value.strip().split()).title()
    return normalized.removesuffix(" County")
