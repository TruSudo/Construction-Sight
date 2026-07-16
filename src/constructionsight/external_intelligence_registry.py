"""Lawful Shovels/Regrid capability registry for ConstructionSight planning."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.external_intelligence_models import (
    CapabilityDomain,
    CapabilityEvidenceKind,
    CapabilityGap,
    CapabilityGapReport,
    CapabilityReference,
    DeliveryMode,
    ExternalCapability,
    ImplementationStatus,
    LawfulAccessBoundary,
    ReferencePlatform,
)

SHOVELS_API_URL = "https://www.shovels.ai/api"
SHOVELS_DATA_FEED_URL = "https://www.shovels.ai/data-feed"
SHOVELS_DATA_DICTIONARY_URL = "https://www.shovels.ai/data-dictionary"
REGRID_API_URL = "https://regrid.com/api"
REGRID_SCHEMA_URL = "https://support.regrid.com/docs/regrid-parcel-schemas"


def get_external_capabilities(
    *,
    platform: ReferencePlatform | None = None,
    domain: CapabilityDomain | None = None,
) -> list[ExternalCapability]:
    """Return lawful Shovels/Regrid capability targets, optionally filtered."""

    capabilities = [*_shovels_capabilities(), *_regrid_capabilities()]
    if platform is not None:
        capabilities = [
            capability for capability in capabilities if capability.platform == platform
        ]
    if domain is not None:
        capabilities = [capability for capability in capabilities if capability.domain == domain]
    return capabilities


def build_capability_gap_report(
    capabilities: Iterable[ExternalCapability] | None = None,
) -> CapabilityGapReport:
    """Build a deterministic ConstructionSight gap report from capability targets."""

    reviewed = list(capabilities if capabilities is not None else get_external_capabilities())
    gaps = [_gap_for(capability) for capability in reviewed]
    platforms = sorted({gap.platform for gap in gaps}, key=lambda value: value.value)
    return CapabilityGapReport(
        report_id="external-capability-gap-report:v1",
        capabilities_reviewed=len(reviewed),
        platforms=platforms,
        gaps=[gap for gap in gaps if _is_gap(gap.status)],
        outperform_targets=[
            gap for gap in gaps if gap.status == ImplementationStatus.OUTPERFORM_TARGET
        ],
        blocked_by_license=[
            gap for gap in gaps if gap.status == ImplementationStatus.BLOCKED_BY_LICENSE
        ],
    )


def capability_matrix_rows(
    capabilities: Iterable[ExternalCapability] | None = None,
) -> list[dict[str, str]]:
    """Return compact matrix rows for CLIs, reports, and future UI tables."""

    reviewed = list(capabilities if capabilities is not None else get_external_capabilities())
    return [
        {
            "platform": capability.platform.value,
            "domain": capability.domain.value,
            "capability_key": capability.capability_key,
            "label": capability.label,
            "status": capability.implementation_status.value,
            "lawful_boundary": capability.lawful_boundary.value,
            "target": capability.construction_sight_target,
        }
        for capability in reviewed
    ]


def _is_gap(status: ImplementationStatus) -> bool:
    """Return whether a status is an implementation gap."""

    return status not in {
        ImplementationStatus.OUTPERFORM_TARGET,
        ImplementationStatus.BLOCKED_BY_LICENSE,
    }


def _gap_for(capability: ExternalCapability) -> CapabilityGap:
    """Convert a capability target into a gap row."""

    return CapabilityGap(
        capability_key=capability.capability_key,
        platform=capability.platform,
        domain=capability.domain,
        label=capability.label,
        status=capability.implementation_status,
        lawful_boundary=capability.lawful_boundary,
        target=capability.construction_sight_target,
        improvement_strategy=capability.improvement_strategy,
        priority=_priority_for(capability),
    )


def _priority_for(capability: ExternalCapability) -> int:
    """Return product priority for parity or advantage work."""

    if capability.implementation_status == ImplementationStatus.OUTPERFORM_TARGET:
        return 95
    if capability.domain in {
        CapabilityDomain.PERMIT_DATA,
        CapabilityDomain.PARCEL_DATA,
        CapabilityDomain.PARCEL_GEOMETRY,
        CapabilityDomain.GOVERNMENT_DECISIONS,
        CapabilityDomain.UPDATE_MONITORING,
    }:
        return 90
    if capability.domain in {
        CapabilityDomain.CONTRACTOR_INTELLIGENCE,
        CapabilityDomain.GEO_SEARCH,
        CapabilityDomain.ADDRESS_RESOLUTION,
        CapabilityDomain.PROPERTY_ENRICHMENT,
    }:
        return 80
    if capability.implementation_status == ImplementationStatus.BLOCKED_BY_LICENSE:
        return 40
    return 65


def _public_reference(source_name: str, source_url: str, claim: str) -> CapabilityReference:
    """Create a public documentation reference."""

    return CapabilityReference(
        evidence_kind=CapabilityEvidenceKind.PUBLIC_DOCUMENTATION,
        source_name=source_name,
        source_url=source_url,
        claim=claim,
    )


def _user_research(source_name: str, claim: str) -> CapabilityReference:
    """Create a user-research reference from prior direct prompting and analysis."""

    return CapabilityReference(
        evidence_kind=CapabilityEvidenceKind.USER_RESEARCH,
        source_name=source_name,
        claim=claim,
    )


def _capability(
    *,
    capability_key: str,
    platform: ReferencePlatform,
    domain: CapabilityDomain,
    label: str,
    description: str,
    delivery_modes: list[DeliveryMode],
    lawful_boundary: LawfulAccessBoundary,
    references: list[CapabilityReference],
    construction_sight_target: str,
    improvement_strategy: str,
    normalized_output_contracts: list[str],
    implementation_status: ImplementationStatus = ImplementationStatus.DESIGNED,
    update_frequency: str | None = None,
    notes: list[str] | None = None,
) -> ExternalCapability:
    """Create one deterministic capability target."""

    return ExternalCapability(
        capability_key=capability_key,
        platform=platform,
        domain=domain,
        label=label,
        description=description,
        delivery_modes=delivery_modes,
        update_frequency=update_frequency,
        lawful_boundary=lawful_boundary,
        references=references,
        construction_sight_target=construction_sight_target,
        implementation_status=implementation_status,
        improvement_strategy=improvement_strategy,
        normalized_output_contracts=normalized_output_contracts,
        notes=notes or [],
    )


def _shovels_capabilities() -> list[ExternalCapability]:
    """Return Shovels-inspired lawful capability targets."""

    return [
        _capability(
            capability_key="shovels:permit-data-feed",
            platform=ReferencePlatform.SHOVELS,
            domain=CapabilityDomain.PERMIT_DATA,
            label="Standardized permit data feed",
            description=(
                "Permit records with lifecycle dates, status, value, type, scope, "
                "geography, property attributes, owner/applicant fields, contractor "
                "joins, and first-seen timing."
            ),
            delivery_modes=[
                DeliveryMode.API,
                DeliveryMode.DATA_WAREHOUSE,
                DeliveryMode.BULK_FILE,
            ],
            update_frequency="twice monthly public target; source monitoring can be faster",
            lawful_boundary=LawfulAccessBoundary.OPEN_PUBLIC_RECORDS,
            references=[
                _public_reference(
                    "Shovels API",
                    SHOVELS_API_URL,
                    "Advertises permit, contractor, property, geo-search, filtering, "
                    "metrics, and decision data.",
                ),
                _public_reference(
                    "Shovels Data Feed",
                    SHOVELS_DATA_FEED_URL,
                    "Advertises warehouse/file delivery for permits, contractors, "
                    "decisions, residents, employees, licenses, and Regrid-linked "
                    "parcels.",
                ),
                _user_research(
                    "Shovels direct schema research",
                    "PERMITS fields include ID, PERMIT_NUMBER, ADDRESS_ID, APN, "
                    "contractor IDs, lifecycle dates, job value, derived work flags, "
                    "and FIRST_SEEN_DATE.",
                ),
            ],
            construction_sight_target=(
                "Normalize public permit evidence into PermitRecord, "
                "UniversalIntakeRecord, OpportunityCandidate, and future "
                "transition-diff records."
            ),
            improvement_strategy=(
                "Outperform static permit aggregation by preserving source snapshots, "
                "detecting field changes, and turning first-seen/status/value/"
                "contractor movement into lead triggers."
            ),
            normalized_output_contracts=[
                "PermitRecord",
                "UniversalIntakeRecord",
                "OpportunityCandidate",
            ],
            implementation_status=ImplementationStatus.IN_PROGRESS,
        ),
        _capability(
            capability_key="shovels:contractor-graph",
            platform=ReferencePlatform.SHOVELS,
            domain=CapabilityDomain.CONTRACTOR_INTELLIGENCE,
            label="Contractor graph and firm grouping",
            description=(
                "Contractor records are grouped, enriched, linked to permits and "
                "employees, and represented through canonical firm/person "
                "relationships."
            ),
            delivery_modes=[DeliveryMode.API, DeliveryMode.DATA_WAREHOUSE],
            update_frequency="monthly or twice monthly depending on table",
            lawful_boundary=LawfulAccessBoundary.OPEN_PUBLIC_RECORDS,
            references=[
                _public_reference(
                    "Shovels API",
                    SHOVELS_API_URL,
                    "Advertises contractor search by specialties, license types, "
                    "work history, active permits, and historical performance.",
                ),
                _user_research(
                    "Shovels direct schema research",
                    "CONTRACTORS includes GROUP_ID and IS_REPRESENTATIVE; EMPLOYEES "
                    "links via CONTRACTOR_ID and PERSON_ID; UNIVERSAL_PERSON "
                    "represents deduped people.",
                ),
            ],
            construction_sight_target=(
                "Resolve contractors, contractor groups, employees, principals, "
                "license numbers, and reachable contacts from lawful public and "
                "user-provided sources."
            ),
            improvement_strategy=(
                "Pair contractor grouping with project/parcel transition timing so "
                "outreach targets the correct firm at the correct moment, not "
                "merely the largest contractor list."
            ),
            normalized_output_contracts=[
                "Entity",
                "Relationship",
                "OpportunityCandidate",
            ],
        ),
        _capability(
            capability_key="shovels:decisions-pre-permit-signal",
            platform=ReferencePlatform.SHOVELS,
            domain=CapabilityDomain.GOVERNMENT_DECISIONS,
            label="Government decisions before permits",
            description=(
                "Decision records capture council, planning-board, zoning, and "
                "approval intelligence before many building permits are filed."
            ),
            delivery_modes=[DeliveryMode.API, DeliveryMode.DATA_WAREHOUSE],
            update_frequency="real time public target for decisions",
            lawful_boundary=LawfulAccessBoundary.OPEN_PUBLIC_RECORDS,
            references=[
                _public_reference(
                    "Shovels API",
                    SHOVELS_API_URL,
                    "Advertises city council decisions, planning board approvals, "
                    "zoning changes, and months-earlier visibility before permits.",
                ),
                _public_reference(
                    "Shovels Data Feed",
                    SHOVELS_DATA_FEED_URL,
                    "Advertises Decisions as a real-time data-feed table.",
                ),
                _user_research(
                    "ConstructionSight locked doctrine",
                    "Planning, capital, legislative, procurement, and "
                    "environmental-review data are earlier signals; permits are "
                    "often later confirmation.",
                ),
            ],
            construction_sight_target=(
                "Ingest agendas, staff reports, CEQA records, planning decisions, "
                "and zoning actions as pre-permit project signals."
            ),
            improvement_strategy=(
                "Beat permit-only products by treating decisions and CEQA as "
                "first-class transition events in the lead score."
            ),
            normalized_output_contracts=[
                "UniversalIntakeRecord",
                "OpportunityCandidate",
                "Relationship",
            ],
            implementation_status=ImplementationStatus.OUTPERFORM_TARGET,
        ),
        _capability(
            capability_key="shovels:warehouse-delivery",
            platform=ReferencePlatform.SHOVELS,
            domain=CapabilityDomain.DATA_WAREHOUSE_FEED,
            label="Enterprise warehouse and file delivery",
            description=(
                "Enterprise customers can receive data in warehouses or cloud "
                "storage using preformatted tables and recurring refreshes."
            ),
            delivery_modes=[DeliveryMode.DATA_WAREHOUSE, DeliveryMode.BULK_FILE],
            update_frequency="automatic recurring updates",
            lawful_boundary=LawfulAccessBoundary.LAWFUL_API_OR_LICENSE,
            references=[
                _public_reference(
                    "Shovels Data Feed",
                    SHOVELS_DATA_FEED_URL,
                    "Advertises Snowflake, BigQuery, Databricks, S3, GCS, Azure, "
                    "Parquet, CSV, SFTP, HTTPS, and automatic updates.",
                )
            ],
            construction_sight_target=(
                "Export normalized ConstructionSight records as JSONL/CSV/"
                "Parquet-ready contracts and future warehouse tables."
            ),
            improvement_strategy=(
                "Add evidence snapshots, source limitations, transition diffs, "
                "and confidence bands to every exported table so downstream users "
                "see why a lead exists."
            ),
            normalized_output_contracts=[
                "UniversalIntakeRecord",
                "OpportunityCandidate",
                "CapabilityGapReport",
            ],
            implementation_status=ImplementationStatus.DESIGNED,
        ),
        _capability(
            capability_key="shovels:audience-targeting",
            platform=ReferencePlatform.SHOVELS,
            domain=CapabilityDomain.AUDIENCE_TARGETING,
            label="Audience and contact targeting",
            description=(
                "Resident, employee, owner, and contractor contact datasets support "
                "audience targeting and B2B/B2C outreach workflows."
            ),
            delivery_modes=[DeliveryMode.API, DeliveryMode.DATA_WAREHOUSE],
            update_frequency="monthly public target for residents and employees",
            lawful_boundary=LawfulAccessBoundary.LAWFUL_API_OR_LICENSE,
            references=[
                _public_reference(
                    "Shovels Data Feed",
                    SHOVELS_DATA_FEED_URL,
                    "Advertises residents linked through address_id and employees "
                    "linked through contractor_id.",
                ),
                _user_research(
                    "Shovels direct schema research",
                    "RESIDENTS, EMPLOYEES, and UNIVERSAL_PERSON expose person/"
                    "contact resolution concepts that must be tracked separately "
                    "from public-record facts.",
                ),
            ],
            construction_sight_target=(
                "Support outreach only after lawful enrichment, deduplication, "
                "preview, suppression, and evidence-backed role identification."
            ),
            improvement_strategy=(
                "Avoid black-box people-data dependence by separating public-record "
                "parties, user-provided contacts, licensed enrichment, and outreach "
                "suppression state."
            ),
            normalized_output_contracts=["Entity", "Relationship", "OpportunityCandidate"],
            implementation_status=ImplementationStatus.BLOCKED_BY_LICENSE,
        ),
        _capability(
            capability_key="shovels:cli-api-gis",
            platform=ReferencePlatform.SHOVELS,
            domain=CapabilityDomain.WORKFLOW_INTEGRATION,
            label="API, CLI, GIS, and app access",
            description=(
                "Multiple access modes let users query, download, automate, map, "
                "and integrate construction intelligence."
            ),
            delivery_modes=[
                DeliveryMode.API,
                DeliveryMode.CLI,
                DeliveryMode.GIS,
                DeliveryMode.WEB_APP,
            ],
            lawful_boundary=LawfulAccessBoundary.PUBLIC_DOCS_ONLY,
            references=[
                _public_reference(
                    "Shovels API",
                    SHOVELS_API_URL,
                    "Advertises API access, GIS, CLI, Shovels Online, Charlie AI, "
                    "and audience workflows.",
                )
            ],
            construction_sight_target=(
                "Expose every durable capability through deterministic services "
                "first, then CLI, API, desktop/mobile UI, exports, and GIS layers."
            ),
            improvement_strategy=(
                "Keep all access modes explainable and audit-backed instead of presentation-only."
            ),
            normalized_output_contracts=["UniversalIntakeRecord", "OpportunityCandidate"],
            implementation_status=ImplementationStatus.IN_PROGRESS,
        ),
    ]


def _regrid_capabilities() -> list[ExternalCapability]:
    """Return Regrid-inspired lawful capability targets."""

    return [
        _capability(
            capability_key="regrid:parcel-api-geometry",
            platform=ReferencePlatform.REGRID,
            domain=CapabilityDomain.PARCEL_GEOMETRY,
            label="Parcel API, boundaries, and geometry",
            description=(
                "Parcel APIs and tiles expose parcel boundaries, property details, "
                "labels, and polygon search for nationwide parcel workflows."
            ),
            delivery_modes=[
                DeliveryMode.API,
                DeliveryMode.TILE_SERVICE,
                DeliveryMode.FEATURE_SERVICE,
            ],
            lawful_boundary=LawfulAccessBoundary.LAWFUL_API_OR_LICENSE,
            references=[
                _public_reference(
                    "Regrid API",
                    REGRID_API_URL,
                    "Advertises nationwide parcel data, property boundaries, "
                    "parcel details, API sandbox, Tile API, OpenAPI specification, "
                    "and polygon search.",
                ),
                _user_research(
                    "Regrid direct research",
                    "Parcel geometry is the universal anchor: geometry -> "
                    "canonical parcel -> owner -> portfolio -> assembly -> "
                    "development activity.",
                ),
            ],
            construction_sight_target=(
                "Use APN, address, centroid, geometry, jurisdiction, and county "
                "parcels as the stable site anchor for projects, permits, CEQA, "
                "agendas, and outreach territories."
            ),
            improvement_strategy=(
                "Build a parcel-first project graph and make parcel geometry drive "
                "deduplication, nearby influence, map overlays, and opportunity "
                "territories."
            ),
            normalized_output_contracts=["Site", "Relationship", "OpportunityCandidate"],
            implementation_status=ImplementationStatus.IN_PROGRESS,
        ),
        _capability(
            capability_key="regrid:bulk-feature-service",
            platform=ReferencePlatform.REGRID,
            domain=CapabilityDomain.BULK_DELIVERY,
            label="Bulk files and feature service delivery",
            description=(
                "Regrid publicly advertises bulk files, feature service, parcel "
                "API/tiles, and an interactive API sandbox as delivery methods."
            ),
            delivery_modes=[
                DeliveryMode.BULK_FILE,
                DeliveryMode.FEATURE_SERVICE,
                DeliveryMode.API,
            ],
            lawful_boundary=LawfulAccessBoundary.LAWFUL_API_OR_LICENSE,
            references=[
                _public_reference(
                    "Regrid API",
                    REGRID_API_URL,
                    "Lists bulk files, feature service, parcel API and tiles, and "
                    "interactive API sandbox as delivery methods.",
                )
            ],
            construction_sight_target=(
                "Support county parcel imports from open data, user-provided "
                "licensed exports, and future feature-service layers without "
                "coupling the core graph to one vendor."
            ),
            improvement_strategy=(
                "Make Regrid a pluggable provider while preserving open county "
                "parcel sources as first-class fallbacks and comparison sources."
            ),
            normalized_output_contracts=["Site", "UniversalIntakeRecord"],
        ),
        _capability(
            capability_key="regrid:spatial-add-ons",
            platform=ReferencePlatform.REGRID,
            domain=CapabilityDomain.PROPERTY_ENRICHMENT,
            label="Spatial add-ons: addresses, buildings, zoning, ownership",
            description=(
                "Regrid advertises matched secondary addresses, matched building "
                "footprints, standardized zoning, daily ownership updates, and "
                "roadway polygons."
            ),
            delivery_modes=[
                DeliveryMode.API,
                DeliveryMode.FEATURE_SERVICE,
                DeliveryMode.BULK_FILE,
            ],
            update_frequency=(
                "daily for ownership add-on; monthly for standardized zoning public claim"
            ),
            lawful_boundary=LawfulAccessBoundary.LAWFUL_API_OR_LICENSE,
            references=[
                _public_reference(
                    "Regrid API",
                    REGRID_API_URL,
                    "Advertises matched secondary addresses, building footprints, "
                    "zoning, daily ownership updates, and roadway polygons.",
                )
            ],
            construction_sight_target=(
                "Represent buildings, secondary addresses, zoning, ownership, and "
                "road adjacency as optional parcel enrichments with provenance and "
                "license boundaries."
            ),
            improvement_strategy=(
                "Use enrichments to explain lead quality: access, buildable land, "
                "zoning fit, owner portfolio, and nearby project influence."
            ),
            normalized_output_contracts=["Site", "Entity", "Relationship"],
            implementation_status=ImplementationStatus.DESIGNED,
        ),
        _capability(
            capability_key="regrid:address-resolution",
            platform=ReferencePlatform.REGRID,
            domain=CapabilityDomain.ADDRESS_RESOLUTION,
            label="Address-to-parcel and point-to-parcel resolution",
            description=(
                "Address and point queries can locate parcel records and associated "
                "geometry for site matching."
            ),
            delivery_modes=[DeliveryMode.API, DeliveryMode.INTERNAL_ENGINE],
            lawful_boundary=LawfulAccessBoundary.LAWFUL_API_OR_LICENSE,
            references=[
                _public_reference(
                    "Regrid API",
                    REGRID_API_URL,
                    "Advertises search for nationwide properties, full attribute "
                    "sets, labels, parcel APIs, and map layers.",
                ),
                _user_research(
                    "Regrid direct research",
                    "Search pathways include lat/lon, APN, address, polygon, and "
                    "attributes; point-to-parcel is central to parcel anchoring.",
                ),
            ],
            construction_sight_target=(
                "Normalize address, APN, coordinate, and polygon pivots into one "
                "site-resolution contract."
            ),
            improvement_strategy=(
                "Compare multiple lawful sources for the same parcel and preserve "
                "conflicts instead of silently accepting one vendor geometry."
            ),
            normalized_output_contracts=["Site", "UniversalIntakeRecord"],
        ),
        _capability(
            capability_key="regrid:coverage-schema",
            platform=ReferencePlatform.REGRID,
            domain=CapabilityDomain.COVERAGE_METRICS,
            label="Coverage and parcel schema tracking",
            description=(
                "Coverage maps and parcel schema documentation guide where parcel "
                "data exists, what fields are available, and where source quality "
                "varies."
            ),
            delivery_modes=[DeliveryMode.INTERNAL_ENGINE, DeliveryMode.WEB_APP],
            lawful_boundary=LawfulAccessBoundary.PUBLIC_DOCS_ONLY,
            references=[
                _public_reference(
                    "Regrid API",
                    REGRID_API_URL,
                    "Links to coverage map, support center, and parcel schema resources.",
                ),
                _public_reference(
                    "Regrid parcel schema",
                    REGRID_SCHEMA_URL,
                    "Parcel schema documentation is the public schema target for field mapping.",
                ),
            ],
            construction_sight_target=(
                "Maintain source coverage, schema coverage, stale-field warnings, "
                "and county-by-county parcel confidence."
            ),
            improvement_strategy=(
                "Make coverage a visible lead-quality input so missing parcel "
                "geometry or stale assessor fields reduce confidence rather than "
                "corrupting the graph."
            ),
            normalized_output_contracts=["Site", "CapabilityGapReport"],
            implementation_status=ImplementationStatus.DESIGNED,
        ),
    ]
