"""Evidence-backed parcel source verification and county coverage reporting."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from constructionsight.parcel_assurance_models import (
    ParcelAssuranceSourceContext,
    ParcelEvidenceAuthority,
)
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelSource,
)
from constructionsight.parcel_source_registry import get_parcel_sources
from constructionsight.parcel_source_verification_models import (
    ParcelCountyCoverageGap,
    ParcelCountyCoverageGapCode,
    ParcelCountyCoverageReport,
    ParcelCountyCoverageRequirement,
    ParcelCountyCoverageStatus,
    ParcelSourceEvidence,
    ParcelSourceEvidenceKind,
    ParcelSourceVerificationProfile,
    ParcelSourceVerificationStatus,
    parcel_county_coverage_report_id,
    parcel_source_evidence_id,
    parcel_source_verification_profile_id,
)

_OBSERVED_AT = datetime(2026, 7, 14, 11, 14, 49, tzinfo=UTC)
_SAN_BERNARDINO_KEY = "san-bernardino:county-gis-parcels"
_RIVERSIDE_KEY = "riverside:county-gis-parcels"


def get_parcel_source_evidence() -> list[ParcelSourceEvidence]:
    """Return the canonical official evidence snapshot for both target counties."""

    evidence = [
        _evidence(
            source_key=_SAN_BERNARDINO_KEY,
            county="San Bernardino",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_DATASET_METADATA,
            public_url=(
                "https://open.sbcounty.gov/datasets/san-bernardino-county-parcel-dataset/about"
            ),
            facts=(
                "The county open-data catalog publishes a San Bernardino County parcel dataset.",
                "The dataset describes parcel polygons for San Bernardino County.",
            ),
            field_roles=(ParcelFieldRole.APN, ParcelFieldRole.GEOMETRY),
        ),
        _evidence(
            source_key=_SAN_BERNARDINO_KEY,
            county="San Bernardino",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_SERVICE_SCHEMA,
            public_url=(
                "https://services.arcgis.com/aA3snZwJfFkVyDuP/ArcGIS/rest/services/"
                "Parcels_for_San_Bernardino_County/FeatureServer/0"
            ),
            facts=(
                "The feature layer geometry type is esriGeometryPolygon.",
                "The layer reports a maximum record count of 1000.",
                "The layer supports JSON, GeoJSON, and PBF query formats.",
                "The observed schema exposes ParcelNumber, OwnerName, Acreage, Zoning, "
                "Jurisdiction, and OBJECTID.",
                "The service reports spatial reference 102100, with latest WKID 3857.",
            ),
            field_roles=(
                ParcelFieldRole.APN,
                ParcelFieldRole.OWNER,
                ParcelFieldRole.JURISDICTION,
                ParcelFieldRole.ZONING,
                ParcelFieldRole.ACREAGE,
                ParcelFieldRole.GEOMETRY,
                ParcelFieldRole.SOURCE_RECORD_ID,
            ),
        ),
        _evidence(
            source_key=_SAN_BERNARDINO_KEY,
            county="San Bernardino",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_DATASET_METADATA,
            public_url=(
                "https://services.arcgis.com/aA3snZwJfFkVyDuP/ArcGIS/rest/services/"
                "Parcels_for_San_Bernardino_County/FeatureServer"
            ),
            facts=(
                "The service describes parcel polygons for San Bernardino County.",
                "The service states that Land Use Services, the Surveyor, and the Assessor "
                "maintain the parcel data.",
            ),
            field_roles=(
                ParcelFieldRole.APN,
                ParcelFieldRole.JURISDICTION,
                ParcelFieldRole.ZONING,
                ParcelFieldRole.GEOMETRY,
            ),
        ),
        _evidence(
            source_key=_SAN_BERNARDINO_KEY,
            county="San Bernardino",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_LIMITATION,
            public_url="https://arcpropertyinfo.sbcounty.gov/",
            facts=("Assessor information is maintained for property assessment and taxation.",),
            field_roles=(ParcelFieldRole.OWNER, ParcelFieldRole.ZONING),
            limitations=(
                "Assessor data does not determine current legal ownership.",
                "Assessor data does not determine permitted property use.",
                "The county does not guarantee assessor-data accuracy or completeness.",
            ),
        ),
        _evidence(
            source_key=_RIVERSIDE_KEY,
            county="Riverside",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_DATASET_METADATA,
            public_url=(
                "https://gisopendata-countyofriverside.opendata.arcgis.com/"
                "datasets/CountyofRiverside%3A%3Aparcels-crest/about"
            ),
            facts=(
                "The Riverside County mapping portal publishes PARCELS_CREST.",
                "The portal describes PARCELS_CREST as parcel data with a simplified schema.",
            ),
            field_roles=(ParcelFieldRole.APN, ParcelFieldRole.GEOMETRY),
        ),
        _evidence(
            source_key=_RIVERSIDE_KEY,
            county="Riverside",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_SERVICE_SCHEMA,
            public_url=(
                "https://gis.countyofriverside.us/arcgis_mapping/rest/services/"
                "OpenData/Assessor/MapServer/50"
            ),
            facts=(
                "The feature layer geometry type is esriGeometryPolygon.",
                "The layer reports a maximum record count and selection count of 2000.",
                "The layer supports JSON, GeoJSON, and PBF query formats.",
                "The observed live schema exposes APN, situs-address components, CLASS_CODE, "
                "ACREAGE, OBJECTID, and SHAPE.",
                "The service reports spatial reference 102646, with latest WKID 2230.",
            ),
            field_roles=(
                ParcelFieldRole.APN,
                ParcelFieldRole.ADDRESS,
                ParcelFieldRole.SITUS_CITY,
                ParcelFieldRole.ACREAGE,
                ParcelFieldRole.GEOMETRY,
                ParcelFieldRole.SOURCE_RECORD_ID,
            ),
            limitations=(
                "The live field list does not expose owner-name fields described by older text.",
                "The source excludes parcel polygons representing right-of-way and river.",
            ),
        ),
        _evidence(
            source_key=_RIVERSIDE_KEY,
            county="Riverside",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_LIMITATION,
            public_url=("https://rcitgis-countyofriverside.hub.arcgis.com/pages/data-distribution"),
            facts=("Riverside County publishes GIS maps and data for reference purposes.",),
            field_roles=(ParcelFieldRole.GEOMETRY,),
            limitations=(
                "Map features are approximate.",
                "Map features are not necessarily accurate to surveying standards.",
            ),
        ),
        _evidence(
            source_key=_RIVERSIDE_KEY,
            county="Riverside",
            evidence_kind=ParcelSourceEvidenceKind.OFFICIAL_DATASET_METADATA,
            public_url="https://www.rivcoacr.org/AssessorMaps",
            facts=(
                "The Assessor maintains parcel maps used as the basis for real-property "
                "assessment.",
                "The Assessor states that its parcel maps are continuously updated for new "
                "subdivisions and parcels.",
            ),
            field_roles=(ParcelFieldRole.APN, ParcelFieldRole.GEOMETRY),
            limitations=(
                "Assessment parcel maps are not a substitute for a surveyed legal boundary.",
            ),
        ),
    ]
    return sorted(evidence, key=lambda item: item.evidence_id)


def get_verified_parcel_source_profiles() -> list[ParcelSourceVerificationProfile]:
    """Return evidence-bound preview profiles for the two official county sources."""

    sources = {source.source_key: source for source in get_parcel_sources()}
    evidence = get_parcel_source_evidence()
    profiles = [
        _profile(
            source=sources[_SAN_BERNARDINO_KEY],
            lineage_key="san-bernardino-county-parcel-administration",
            evidence=_evidence_for_urls(
                evidence,
                {
                    sources[_SAN_BERNARDINO_KEY].source_url,
                    sources[_SAN_BERNARDINO_KEY].documentation_url,
                    (
                        "https://services.arcgis.com/aA3snZwJfFkVyDuP/ArcGIS/rest/"
                        "services/Parcels_for_San_Bernardino_County/FeatureServer"
                    ),
                    "https://arcpropertyinfo.sbcounty.gov/",
                },
            ),
            schema_fields=(
                "Acreage",
                "AssessClass",
                "AssessDescription",
                "BaseYear",
                "ExemptionValue",
                "HomeOwnerExemption",
                "ImprovementValue",
                "Jurisdiction",
                "JurisdictionURL",
                "LandValue",
                "OBJECTID",
                "OwnerName",
                "PageMap",
                "ParcelNumber",
                "PersonalPropertyValue",
                "Shape__Area",
                "Shape__Length",
                "TaxRateArea",
                "TaxStatus",
                "Zoning",
                "ZoningDescription",
                "geometry",
            ),
            authoritative_fields=(ParcelFieldRole.APN,),
            max_record_count=1000,
            spatial_reference="EPSG:3857 (ArcGIS WKID 102100)",
        ),
        _profile(
            source=sources[_RIVERSIDE_KEY],
            lineage_key="riverside-county-assessor-rcit",
            evidence=_evidence_for_urls(
                evidence,
                {
                    sources[_RIVERSIDE_KEY].source_url,
                    sources[_RIVERSIDE_KEY].documentation_url,
                    ("https://rcitgis-countyofriverside.hub.arcgis.com/pages/data-distribution"),
                    "https://www.rivcoacr.org/AssessorMaps",
                },
            ),
            schema_fields=(
                "ACREAGE",
                "APN",
                "BLOCK",
                "BOOK",
                "CAME_FROM",
                "CITY",
                "CLASS_CODE",
                "COUNTY_CODE",
                "FLAG",
                "LAND",
                "LOT",
                "LOT_TYPE",
                "MAIL_CITY",
                "MAIL_STREET",
                "MAP_BOOK_PAGE",
                "MULTIPLE",
                "OBJECTID",
                "PAGE",
                "RECORDER_MAP_TYPE",
                "SHAPE",
                "SHAPE.STArea()",
                "SHAPE.STLength()",
                "SITUS_CITY",
                "SITUS_STREET",
                "STREET_NAME",
                "STREET_NUMBER",
                "STREET_PREDIRECTION",
                "STREET_SUFFIX",
                "STREET_TYPE",
                "STRUCTURES",
                "SUBDIVISION_NAME",
                "TAX_RATE_AREA",
                "UNIT_NUMBER",
                "ZIP_CODE",
                "geometry",
            ),
            authoritative_fields=(ParcelFieldRole.APN,),
            max_record_count=2000,
            spatial_reference="EPSG:2230 (ArcGIS WKID 102646)",
        ),
    ]
    _validate_evidence_references(profiles, evidence)
    return sorted(profiles, key=lambda item: item.source_key)


def assurance_contexts_from_verified_profiles(
    profiles: Iterable[ParcelSourceVerificationProfile] | None = None,
) -> list[ParcelAssuranceSourceContext]:
    """Convert verified profiles into field-specific parcel assurance contexts."""

    reviewed = list(profiles if profiles is not None else get_verified_parcel_source_profiles())
    source_keys = [profile.source_key for profile in reviewed]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("parcel source verification profiles must have unique source keys")
    contexts: list[ParcelAssuranceSourceContext] = []
    for profile in reviewed:
        if profile.status != ParcelSourceVerificationStatus.VERIFIED_PREVIEW:
            raise ValueError("parcel assurance contexts require verified-preview source profiles")
        contexts.append(
            ParcelAssuranceSourceContext(
                source_key=profile.source_key,
                lineage_key=profile.lineage_key,
                default_authority=profile.default_authority,
                authoritative_fields=list(profile.authoritative_fields),
                limitations=list(profile.limitations),
            )
        )
    return sorted(contexts, key=lambda context: context.source_key)


def default_county_coverage_requirements() -> list[ParcelCountyCoverageRequirement]:
    """Return the exhaustive parcel fact requirements for both target counties."""

    required_fields = tuple(
        sorted(
            {
                ParcelFieldRole.APN,
                ParcelFieldRole.ADDRESS,
                ParcelFieldRole.OWNER,
                ParcelFieldRole.COUNTY,
                ParcelFieldRole.STATE,
                ParcelFieldRole.JURISDICTION,
                ParcelFieldRole.ZONING,
                ParcelFieldRole.LAND_USE,
                ParcelFieldRole.ACREAGE,
                ParcelFieldRole.GEOMETRY,
            },
            key=lambda role: role.value,
        )
    )
    authoritative_fields = required_fields
    return [
        ParcelCountyCoverageRequirement(
            county=county,
            required_fields=required_fields,
            authoritative_fields=authoritative_fields,
            minimum_independent_lineages=2,
        )
        for county in ("Riverside", "San Bernardino")
    ]


def build_parcel_county_coverage_report(
    profiles: Iterable[ParcelSourceVerificationProfile] | None = None,
    requirements: Iterable[ParcelCountyCoverageRequirement] | None = None,
    *,
    generated_at: datetime | None = None,
) -> ParcelCountyCoverageReport:
    """Report every fact, authority, redundancy, and acquisition gap by county."""

    reviewed_profiles = list(
        profiles if profiles is not None else get_verified_parcel_source_profiles()
    )
    reviewed_requirements = sorted(
        list(requirements if requirements is not None else default_county_coverage_requirements()),
        key=lambda requirement: requirement.county,
    )
    _validate_unique_profiles(reviewed_profiles)
    gaps = [
        gap
        for requirement in reviewed_requirements
        for gap in _coverage_gaps(requirement, reviewed_profiles)
    ]
    gaps.sort(key=lambda gap: (gap.county, gap.code.value))
    status = _coverage_status(gaps)
    counties = tuple(requirement.county for requirement in reviewed_requirements)
    profile_ids = tuple(sorted(profile.profile_id for profile in reviewed_profiles))
    payload = {
        "status": status.value,
        "counties": list(counties),
        "profile_ids": list(profile_ids),
        "requirements": [
            requirement.model_dump(mode="json") for requirement in reviewed_requirements
        ],
        "gaps": [gap.model_dump(mode="json") for gap in gaps],
    }
    return ParcelCountyCoverageReport(
        report_id=parcel_county_coverage_report_id(payload),
        status=status,
        counties=counties,
        profile_ids=profile_ids,
        requirements=tuple(reviewed_requirements),
        gaps=tuple(gaps),
        generated_at=generated_at or datetime.now(UTC),
    )


def _evidence(
    *,
    source_key: str,
    county: str,
    evidence_kind: ParcelSourceEvidenceKind,
    public_url: str,
    facts: tuple[str, ...],
    field_roles: tuple[ParcelFieldRole, ...] = (),
    limitations: tuple[str, ...] = (),
) -> ParcelSourceEvidence:
    canonical_facts = tuple(sorted(facts))
    canonical_roles = tuple(sorted(field_roles, key=lambda role: role.value))
    canonical_limitations = tuple(sorted(limitations))
    evidence_id = parcel_source_evidence_id(
        source_key=source_key,
        county=county,
        evidence_kind=evidence_kind,
        public_url=public_url,
        observed_at=_OBSERVED_AT,
        facts=canonical_facts,
        field_roles=canonical_roles,
        limitations=canonical_limitations,
    )
    return ParcelSourceEvidence(
        evidence_id=evidence_id,
        source_key=source_key,
        county=county,
        evidence_kind=evidence_kind,
        public_url=public_url,
        observed_at=_OBSERVED_AT,
        facts=canonical_facts,
        field_roles=canonical_roles,
        limitations=canonical_limitations,
    )


def _profile(
    *,
    source: ParcelSource,
    lineage_key: str,
    evidence: list[ParcelSourceEvidence],
    schema_fields: tuple[str, ...],
    authoritative_fields: tuple[ParcelFieldRole, ...],
    max_record_count: int,
    spatial_reference: str,
) -> ParcelSourceVerificationProfile:
    limitations = tuple(
        sorted(
            {
                *source.limitations,
                *(limitation for item in evidence for limitation in item.limitations),
                (
                    "APN authority identifies the assessment parcel only; it does not prove "
                    "legal title or a surveyed boundary."
                ),
                "Countywide record completeness has not been independently verified.",
                "No bulk acquisition run has yet proven pagination or drift handling.",
            }
        )
    )
    candidate = ParcelSourceVerificationProfile.model_construct(
        profile_id="parcel-source-verification:" + ("0" * 64),
        source_key=source.source_key,
        county=source.coverage.county,
        lineage_key=lineage_key,
        status=ParcelSourceVerificationStatus.VERIFIED_PREVIEW,
        access_boundary=source.access_boundary,
        coverage_status=source.coverage_status,
        source_format=source.source_format,
        source_url=source.source_url or "",
        documentation_url=source.documentation_url,
        evidence_ids=tuple(sorted(item.evidence_id for item in evidence)),
        schema_fields=tuple(sorted(schema_fields)),
        field_mappings=tuple(
            sorted(
                source.field_mappings,
                key=lambda mapping: (
                    mapping.field_role.value,
                    mapping.source_field.casefold(),
                ),
            )
        ),
        constant_fields=tuple(
            sorted(source.constant_fields, key=lambda constant: constant.field_role.value)
        ),
        default_authority=ParcelEvidenceAuthority.OFFICIAL,
        authoritative_fields=authoritative_fields,
        public_access_verified=True,
        schema_verified=True,
        county_extent_declared=True,
        countywide_record_coverage_verified=False,
        bulk_acquisition_verified=False,
        max_record_count=max_record_count,
        spatial_reference=spatial_reference,
        limitations=limitations,
        next_action=source.next_action,
        observed_at=_OBSERVED_AT,
    )
    payload = candidate.model_dump(mode="json", exclude={"profile_id"})
    return ParcelSourceVerificationProfile.model_validate(
        {
            **payload,
            "profile_id": parcel_source_verification_profile_id(payload),
        }
    )


def _evidence_for_urls(
    evidence: list[ParcelSourceEvidence],
    urls: set[str | None],
) -> list[ParcelSourceEvidence]:
    selected = [item for item in evidence if item.public_url in urls]
    if len(selected) != len({url for url in urls if url is not None}):
        raise ValueError("parcel source profile is missing a requested evidence URL")
    return selected


def _validate_evidence_references(
    profiles: list[ParcelSourceVerificationProfile],
    evidence: list[ParcelSourceEvidence],
) -> None:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    for profile in profiles:
        if not set(profile.evidence_ids) <= set(evidence_by_id):
            raise ValueError(
                f"parcel source profile references missing evidence: {profile.source_key}"
            )
        profile_evidence = [evidence_by_id[item_id] for item_id in profile.evidence_ids]
        if any(
            item.source_key != profile.source_key
            or _normalize_county(item.county) != _normalize_county(profile.county)
            for item in profile_evidence
        ):
            raise ValueError(
                f"parcel source profile references cross-source evidence: {profile.source_key}"
            )
        supported_roles = {
            field_role for item in profile_evidence for field_role in item.field_roles
        }
        if not set(profile.authoritative_fields) <= supported_roles:
            raise ValueError(
                f"parcel source profile authority lacks evidence: {profile.source_key}"
            )
        if profile.source_url not in {item.public_url for item in profile_evidence}:
            raise ValueError(
                f"parcel source profile URL lacks direct evidence: {profile.source_key}"
            )


def _validate_unique_profiles(profiles: list[ParcelSourceVerificationProfile]) -> None:
    profile_ids = [profile.profile_id for profile in profiles]
    source_keys = [profile.source_key for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("county coverage profiles must have unique profile IDs")
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("county coverage profiles must have unique source keys")


def _coverage_gaps(
    requirement: ParcelCountyCoverageRequirement,
    profiles: list[ParcelSourceVerificationProfile],
) -> list[ParcelCountyCoverageGap]:
    county_profiles = [
        profile
        for profile in profiles
        if _normalize_county(profile.county) == _normalize_county(requirement.county)
    ]
    source_keys = tuple(sorted(profile.source_key for profile in county_profiles))
    gaps: list[ParcelCountyCoverageGap] = []
    verified_profiles = [
        profile
        for profile in county_profiles
        if profile.status == ParcelSourceVerificationStatus.VERIFIED_PREVIEW
    ]
    if not county_profiles or len(verified_profiles) != len(county_profiles):
        gaps.append(
            ParcelCountyCoverageGap(
                code=ParcelCountyCoverageGapCode.SOURCE_REVIEW_REQUIRED,
                county=requirement.county,
                source_keys=source_keys,
                explanation="Every county source must have a verified-preview profile.",
                next_action="verify or replace every unverified county source profile",
            )
        )
    available_fields = {
        field_role for profile in verified_profiles for field_role in profile.available_fields
    }
    missing_fields = tuple(
        sorted(
            set(requirement.required_fields) - available_fields,
            key=lambda role: role.value,
        )
    )
    if missing_fields:
        gaps.append(
            ParcelCountyCoverageGap(
                code=ParcelCountyCoverageGapCode.MISSING_REQUIRED_FIELD,
                county=requirement.county,
                source_keys=source_keys,
                field_roles=missing_fields,
                explanation="No verified county profile supplies every required parcel fact.",
                next_action="add proposition-appropriate official sources for missing facts",
            )
        )
    authoritative_fields = {
        field_role for profile in verified_profiles for field_role in profile.authoritative_fields
    }
    missing_authority = tuple(
        sorted(
            set(requirement.authoritative_fields) - authoritative_fields,
            key=lambda role: role.value,
        )
    )
    if missing_authority:
        gaps.append(
            ParcelCountyCoverageGap(
                code=ParcelCountyCoverageGapCode.MISSING_AUTHORITATIVE_FIELD,
                county=requirement.county,
                source_keys=source_keys,
                field_roles=missing_authority,
                explanation=("Required fields lack proposition-specific authoritative support."),
                next_action=(
                    "verify assessor, recorder, surveyor, planning, zoning, and tax sources "
                    "by proposition"
                ),
            )
        )
    if requirement.require_countywide_record_coverage and not any(
        profile.countywide_record_coverage_verified for profile in verified_profiles
    ):
        gaps.append(
            ParcelCountyCoverageGap(
                code=(ParcelCountyCoverageGapCode.COUNTYWIDE_RECORD_COVERAGE_UNVERIFIED),
                county=requirement.county,
                source_keys=source_keys,
                explanation="No source has proven complete countywide record coverage.",
                next_action="reconcile bounded source counts and coverage exclusions",
            )
        )
    if requirement.require_bulk_acquisition and not any(
        profile.bulk_acquisition_verified for profile in verified_profiles
    ):
        gaps.append(
            ParcelCountyCoverageGap(
                code=ParcelCountyCoverageGapCode.BULK_ACQUISITION_UNVERIFIED,
                county=requirement.county,
                source_keys=source_keys,
                explanation="No source has a verified complete paginated acquisition run.",
                next_action="prove count, pagination, retry, resume, and schema-drift controls",
            )
        )
    under_corroborated = tuple(
        field_role
        for field_role in requirement.required_fields
        if len(
            {
                profile.lineage_key
                for profile in verified_profiles
                if field_role in profile.available_fields
            }
        )
        < requirement.minimum_independent_lineages
    )
    if under_corroborated:
        gaps.append(
            ParcelCountyCoverageGap(
                code=ParcelCountyCoverageGapCode.INSUFFICIENT_INDEPENDENT_LINEAGES,
                county=requirement.county,
                source_keys=source_keys,
                field_roles=under_corroborated,
                explanation=(
                    "Required facts do not yet have the requested independent-lineage depth."
                ),
                next_action="add independent official or licensed corroborating sources",
            )
        )
    return gaps


def _coverage_status(
    gaps: list[ParcelCountyCoverageGap],
) -> ParcelCountyCoverageStatus:
    if not gaps:
        return ParcelCountyCoverageStatus.READY_FOR_BOUNDED_IMPORT
    if any(gap.code == ParcelCountyCoverageGapCode.SOURCE_REVIEW_REQUIRED for gap in gaps):
        return ParcelCountyCoverageStatus.REVIEW_REQUIRED
    return ParcelCountyCoverageStatus.INCOMPLETE


def _normalize_county(value: str) -> str:
    return " ".join(value.strip().casefold().split()).removesuffix(" county")
