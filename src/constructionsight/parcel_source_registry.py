"""Provider-neutral parcel source registry."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.parcel_source_models import (
    ParcelAccessBoundary,
    ParcelConstantFieldValue,
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
            if gap.coverage_status
            in {ParcelCoverageStatus.TARGET, ParcelCoverageStatus.DESIGNED}
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
            source_name="San Bernardino County parcel polygons",
            provider_kind=ParcelProviderKind.COUNTY_GIS,
            access_boundary=ParcelAccessBoundary.OPEN_PUBLIC_DATA,
            coverage_status=ParcelCoverageStatus.READY_FOR_PREVIEW,
            source_format=ParcelSourceFormat.ARCGIS_FEATURE_SERVICE,
            coverage=ParcelSourceCoverage(
                county="San Bernardino",
                geometry_support=ParcelGeometrySupport.POLYGON,
                coverage_notes=[
                    "target county for Phase 1 parcel-first project anchoring",
                    "official service describes County of San Bernardino parcel polygons",
                    "countywide record completeness has not been independently verified",
                ],
            ),
            source_url=(
                "https://services.arcgis.com/aA3snZwJfFkVyDuP/ArcGIS/rest/services/"
                "Parcels_for_San_Bernardino_County/FeatureServer/0"
            ),
            documentation_url=(
                "https://open.sbcounty.gov/datasets/"
                "san-bernardino-county-parcel-dataset/about"
            ),
            field_mappings=_san_bernardino_verified_field_mappings(),
            constant_fields=_county_constants(
                "San Bernardino",
                (
                    "https://services.arcgis.com/aA3snZwJfFkVyDuP/ArcGIS/rest/services/"
                    "Parcels_for_San_Bernardino_County/FeatureServer"
                ),
            ),
            priority=95,
            limitations=[
                "public service schema was observed on 2026-07-14 and may drift",
                "maximum service record count is 1000 and bulk pagination is unverified",
                "the observed schema does not expose a situs-address field",
                "owner data is assessment evidence, not proof of current legal title",
                "parcel geometry is not a surveyed legal boundary",
            ],
            next_action=(
                "run bounded schema, count, pagination, and completeness verification "
                "before import"
            ),
        ),
        ParcelSource(
            source_key="riverside:county-gis-parcels",
            source_name="Riverside County PARCELS_CREST",
            provider_kind=ParcelProviderKind.COUNTY_GIS,
            access_boundary=ParcelAccessBoundary.OPEN_PUBLIC_DATA,
            coverage_status=ParcelCoverageStatus.READY_FOR_PREVIEW,
            source_format=ParcelSourceFormat.ARCGIS_MAP_SERVICE,
            coverage=ParcelSourceCoverage(
                county="Riverside",
                geometry_support=ParcelGeometrySupport.POLYGON,
                coverage_notes=[
                    "target county for Phase 1 parcel-first project anchoring",
                    "official service describes parcel polygons within Riverside County",
                    "right-of-way and river polygons are excluded by the source",
                    "countywide record completeness has not been independently verified",
                ],
            ),
            source_url=(
                "https://gis.countyofriverside.us/arcgis_mapping/rest/services/"
                "OpenData/Assessor/MapServer/50"
            ),
            documentation_url=(
                "https://gisopendata-countyofriverside.opendata.arcgis.com/"
                "datasets/CountyofRiverside%3A%3Aparcels-crest/about"
            ),
            field_mappings=_riverside_verified_field_mappings(),
            constant_fields=_county_constants(
                "Riverside",
                (
                    "https://gis.countyofriverside.us/arcgis_mapping/rest/services/"
                    "OpenData/Assessor/MapServer/50"
                ),
            ),
            priority=95,
            limitations=[
                "public service schema was observed on 2026-07-14 and may drift",
                "maximum service record count is 2000 and bulk pagination is unverified",
                "the current live field list does not expose owner-name fields",
                "SITUS_STREET completeness must be tested before canonical address import",
                "CLASS_CODE is an assessment class, not a planning land-use designation",
                "map features are approximate and are not surveyed legal boundaries",
            ],
            next_action=(
                "run bounded schema, count, pagination, and completeness verification "
                "before import"
            ),
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
            next_action=(
                "support pluggable licensed provider once credentials/license exist"
            ),
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
                    (
                        "supports CSV, GeoJSON, shapefile, or other lawful "
                        "user-provided exports"
                    ),
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
        ParcelFieldMapping(
            source_field="apn",
            field_role=ParcelFieldRole.APN,
            required=True,
        ),
        ParcelFieldMapping(source_field="situs_address", field_role=ParcelFieldRole.ADDRESS),
        ParcelFieldMapping(source_field="owner_name", field_role=ParcelFieldRole.OWNER),
        ParcelFieldMapping(
            source_field="county",
            field_role=ParcelFieldRole.COUNTY,
            required=True,
        ),
        ParcelFieldMapping(
            source_field="jurisdiction",
            field_role=ParcelFieldRole.JURISDICTION,
        ),
        ParcelFieldMapping(source_field="zoning", field_role=ParcelFieldRole.ZONING),
        ParcelFieldMapping(source_field="land_use", field_role=ParcelFieldRole.LAND_USE),
        ParcelFieldMapping(source_field="acreage", field_role=ParcelFieldRole.ACREAGE),
        ParcelFieldMapping(source_field="geometry", field_role=ParcelFieldRole.GEOMETRY),
        ParcelFieldMapping(source_field="updated_at", field_role=ParcelFieldRole.UPDATED_AT),
    ]


def _san_bernardino_verified_field_mappings() -> list[ParcelFieldMapping]:
    """Return fields observed in the official San Bernardino parcel layer."""

    return [
        ParcelFieldMapping(
            source_field="ParcelNumber",
            field_role=ParcelFieldRole.APN,
            required=True,
        ),
        ParcelFieldMapping(
            source_field="OwnerName",
            field_role=ParcelFieldRole.OWNER,
            notes="assessment owner field; not proof of current legal title",
        ),
        ParcelFieldMapping(
            source_field="Jurisdiction",
            field_role=ParcelFieldRole.JURISDICTION,
        ),
        ParcelFieldMapping(source_field="Zoning", field_role=ParcelFieldRole.ZONING),
        ParcelFieldMapping(source_field="Acreage", field_role=ParcelFieldRole.ACREAGE),
        ParcelFieldMapping(
            source_field="geometry",
            field_role=ParcelFieldRole.GEOMETRY,
            notes="ArcGIS/GeoJSON feature geometry member, not an attribute column",
        ),
        ParcelFieldMapping(
            source_field="OBJECTID",
            field_role=ParcelFieldRole.SOURCE_RECORD_ID,
        ),
    ]


def _riverside_verified_field_mappings() -> list[ParcelFieldMapping]:
    """Return fields observed in the official Riverside PARCELS_CREST layer."""

    return [
        ParcelFieldMapping(
            source_field="APN",
            field_role=ParcelFieldRole.APN,
            required=True,
        ),
        ParcelFieldMapping(
            source_field="SITUS_STREET",
            field_role=ParcelFieldRole.ADDRESS,
            notes="site street address; completeness requires row sampling",
        ),
        ParcelFieldMapping(
            source_field="SITUS_CITY",
            field_role=ParcelFieldRole.SITUS_CITY,
        ),
        ParcelFieldMapping(source_field="ACREAGE", field_role=ParcelFieldRole.ACREAGE),
        ParcelFieldMapping(
            source_field="geometry",
            field_role=ParcelFieldRole.GEOMETRY,
            notes="ArcGIS/GeoJSON feature geometry member, not an attribute column",
        ),
        ParcelFieldMapping(
            source_field="OBJECTID",
            field_role=ParcelFieldRole.SOURCE_RECORD_ID,
        ),
    ]


def _county_constants(
    county: str,
    evidence_reference: str,
) -> list[ParcelConstantFieldValue]:
    """Return verified county/state constants for a county-scoped official layer."""

    return [
        ParcelConstantFieldValue(
            field_role=ParcelFieldRole.COUNTY,
            value=county,
            required=True,
            evidence_reference=evidence_reference,
        ),
        ParcelConstantFieldValue(
            field_role=ParcelFieldRole.STATE,
            value="CA",
            required=True,
            evidence_reference=evidence_reference,
        ),
    ]


def _normalize_county(value: str) -> str:
    """Normalize county names for filtering and reporting."""

    normalized = " ".join(value.strip().split()).title()
    return normalized.removesuffix(" County")
