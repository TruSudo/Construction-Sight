"""Read-only bridge from SMARTS observations into ConstructionSight's existing intake/site spine.

This prepares reviewable records; it never writes the graph, certifies a site,
infers physical construction, or triggers commercial outreach.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from constructionsight.intake_models import (
    DigitalFormatFamily,
    ExtractedMaterialFact,
    FactConfidence,
    FormatDetection,
    IntakeEvidenceRef,
    IntakeRouting,
    IntakeUnderstandingStatus,
    MaterialFactKind,
    UniversalIntakeRecord,
    UnmappedEvidenceFragment,
)
from constructionsight.site_resolution_models import (
    GeometryHint,
    GeometryHintKind,
    SiteResolutionInput,
    SiteResolutionResult,
)
from constructionsight.site_resolution_service import (
    build_site_resolution_input_from_intake,
    resolve_site,
)
from constructionsight.smarts_api import COUNTIES, SmartsApiError, SmartsPage

SOURCE_NAME = "California SMARTS construction stormwater"
SOURCE_FAMILY = "smarts_stormwater_facilities"
_EMPTY = frozenset({"", "NA", "N/A", "NONE", "NULL", "UNKNOWN", "NOT AVAILABLE", "0"})
_ROW_IDENTITY_FIELDS = ("WDID", "APP_ID")
_FACT_FIELDS: tuple[tuple[str, MaterialFactKind], ...] = (
    ("SITE_NAME", MaterialFactKind.PROJECT_TITLE),
    ("SITE_ADDRESS", MaterialFactKind.ADDRESS),
    ("DEVELOPER_NAME", MaterialFactKind.PERSON_OR_ORGANIZATION),
)


class SmartsIntakePreview(BaseModel):
    """Non-authoritative integration preview; source identity is not a project match."""

    source_record_key: str | None = None
    identity_status: Literal["source_scoped_candidate", "missing_source_identity"]
    record_sha256: str = Field(min_length=64, max_length=64)
    source_response_sha256: str = Field(min_length=64, max_length=64)
    intake: UniversalIntakeRecord
    site_resolution: SiteResolutionResult
    construction_activity: Literal["unverified"] = "unverified"
    external_project_match: Literal["unreviewed"] = "unreviewed"
    commercial_readiness: Literal["blocked_pending_verification"] = (
        "blocked_pending_verification"
    )
    read_only: Literal[True] = True
    limitations: list[str] = Field(default_factory=list)


def _source_text(record: Mapping[str, Any], field: str) -> str | None:
    raw = record.get(field)
    if raw is None or type(raw) not in (str, int, float):
        return None
    value = str(raw).strip()
    return None if value.upper() in _EMPTY else value


def _wgs84_point(record: Mapping[str, Any]) -> tuple[float, float] | None:
    """Coordinates are merely source-claimed and not independently geocoded."""
    lat_text = _source_text(record, "SITE_LATITUDE")
    lon_text = _source_text(record, "SITE_LONGITUDE")
    if lat_text is None or lon_text is None:
        return None
    try:
        lat, lon = float(lat_text), float(lon_text)
    except ValueError:
        return None
    # A rough California envelope avoids accepting zeros or impossible positions.
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    if not (32.0 <= lat <= 42.2 and -124.6 <= lon <= -114.0):
        return None
    return lat, lon


def build_smarts_intake_preview(
    page: SmartsPage, record: Mapping[str, Any]
) -> SmartsIntakePreview:
    """Prepare one actual page member for the shared intake and site-resolution models."""
    if page.resource != "facilities":
        raise SmartsApiError("Only the SMARTS facility resource supports project intake")
    if record not in page.records:
        raise SmartsApiError("Unbound SMARTS record: not in the supplied source page")
    county = _source_text(record, "SITE_COUNTY")
    if county is None or county not in COUNTIES or (page.county is not None and county != page.county):
        raise SmartsApiError("SMARTS facility county must match the approved source scope")
    if "APP_ID" not in record or "WDID" not in record:
        raise SmartsApiError("SMARTS facility identity columns are missing")

    # CKAN's _id is a transport-row number, not a stable project/source identity.
    # Excluding it means republication with different row order is not new work.
    semantic_record = {str(key): value for key, value in record.items() if key != "_id"}
    try:
        row_bytes = json.dumps(
            semantic_record, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SmartsApiError("SMARTS record cannot be canonically represented") from exc
    row_digest = hashlib.sha256(row_bytes).hexdigest()
    evidence_id = "evidence:smarts:" + row_digest
    app_id = _source_text(record, "APP_ID")
    wdid = _source_text(record, "WDID")
    source_identity = (
        "smarts:facility:" + county + ":wdid:" + wdid if wdid is not None
        else "smarts:facility:" + county + ":app_id:" + app_id
        if app_id is not None else None
    )

    evidence = IntakeEvidenceRef(
        evidence_id=evidence_id,
        source_name=SOURCE_NAME,
        source_family=SOURCE_FAMILY,
        source_url=page.request_url,
        byte_count=len(row_bytes),
        sha256=row_digest,
        access_method="official_public_ckan_read_only",
        lawful_basis="published_public_government_data",
        limitations=[
            "Row digest covers a canonical JSON projection without CKAN _id; "
            "the independent response digest is held by the SMARTS preview.",
        ],
    )
    facts: list[ExtractedMaterialFact] = []
    for field, kind in _FACT_FIELDS:
        value = _source_text(record, field)
        if value:
            facts.append(ExtractedMaterialFact(
                fact_id="fact:smarts:" + row_digest[:16] + ":" + field.lower(),
                fact_kind=kind,
                value=value,
                evidence_id=evidence_id,
                confidence=FactConfidence.SOURCE_CLAIMED,
                source_field=field,
                extractor_name="smarts_facility_mapping.v1",
                context="Regulatory filing source claim; not independently verified",
            ))

    record_hints = {"regulatory_status": _source_text(record, "STATUS") or "unknown"}
    if app_id is not None:
        record_hints["smarts_app_id"] = app_id
    if wdid is not None:
        record_hints["smarts_wdid"] = wdid
    for field, hint in (
        ("NOI_PROCESSED_DATE", "noi_processed_date"),
        ("CONSTRUCTION_COMMENCEMENT_DATE", "reported_construction_commencement"),
        ("COMPLETE_GRADING_DATE", "reported_grading_completion"),
        ("COMPLETE_PROJECT_DATE", "reported_project_completion"),
        ("TYPE_OF_CONSTRUCTION", "source_construction_type"),
    ):
        value = _source_text(record, field)
        if value is not None:
            record_hints[hint] = value
    source_hints = {"county": county, "source_type": "stormwater_regulatory"}
    city = _source_text(record, "SITE_CITY")
    if city is not None:
        source_hints["jurisdiction"] = city
    unmapped = (
        [] if facts else [UnmappedEvidenceFragment(
            fragment_id="fragment:smarts:" + row_digest[:16],
            evidence_id=evidence_id,
            reason="SMARTS record lacks independently mappable title/address facts",
            suggested_adapter_family=SOURCE_FAMILY,
        )]
    )
    intake = UniversalIntakeRecord(
        intake_id="intake:smarts:" + row_digest,
        evidence=evidence,
        format_detection=FormatDetection(
            format_family=DigitalFormatFamily.JSON,
            media_type="application/json",
            detector_name="smarts_facility_mapping.v1",
            matched_signals=["official_ckan_datastore", SOURCE_FAMILY],
        ),
        understanding_status=(
            IntakeUnderstandingStatus.PARTIALLY_UNDERSTOOD
            if facts else IntakeUnderstandingStatus.FORMAT_DETECTED
        ),
        routing=IntakeRouting.HUMAN_REVIEW,
        extracted_facts=facts,
        unmapped_fragments=unmapped,
        source_hints=source_hints,
        record_hints=record_hints,
        adapter_candidate=SOURCE_FAMILY,
        next_action=(
            "Independently verify site identity, scope, commencement, "
            "planning and inspection evidence before project-graph or opportunity changes."
        ),
    )
    base_site_input = build_site_resolution_input_from_intake(intake)
    point = _wgs84_point(record)
    hints: list[GeometryHint] = []
    limitations = [
        "SMARTS Active denotes stormwater regulatory coverage, not active construction.",
        "Reported commencement is not confirmed groundbreaking.",
        "No physical project linkage, phase promotion, or buyer readiness is asserted.",
        "Source-scoped WDID/APP_ID uniqueness must be verified before persistence.",
    ]
    if point is not None:
        hints.append(GeometryHint(
            geometry_kind=GeometryHintKind.POINT,
            latitude=point[0],
            longitude=point[1],
            evidence_id=evidence_id,
            source_name=SOURCE_NAME,
            confidence_score=60,
        ))
    elif record.get("SITE_LATITUDE") is not None or record.get("SITE_LONGITUDE") is not None:
        limitations.append("Source coordinates are incomplete or outside a valid CA envelope")
    if source_identity is None:
        limitations.append("No usable WDID or APP_ID; prohibit automatic stable identity assignment")
    site_input = SiteResolutionInput(
        source_name=base_site_input.source_name,
        evidence_id=evidence_id,
        identifiers=base_site_input.identifiers,
        geometry_hints=hints,
        source_hints=base_site_input.source_hints,
    )
    resolution = resolve_site(site_input)
    return SmartsIntakePreview(
        source_record_key=source_identity,
        identity_status=(
            "source_scoped_candidate" if source_identity is not None
            else "missing_source_identity"
        ),
        record_sha256=row_digest,
        source_response_sha256=page.response_sha256,
        intake=intake,
        site_resolution=resolution,
        limitations=limitations,
    )
