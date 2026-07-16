"""Provider-neutral parcel source schema preview service."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from constructionsight.parcel_schema_models import (
    ParcelFieldRoleMatch,
    ParcelObservedFieldType,
    ParcelSchemaField,
    ParcelSchemaPreviewInput,
    ParcelSchemaPreviewReport,
    ParcelSchemaPreviewStatus,
)
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSource,
    ParcelSourceFormat,
)
from constructionsight.parcel_source_registry import get_parcel_sources

_FIELD_SPLIT_RE = re.compile(r"[^a-z0-9]+")

_ROLE_ALIASES: dict[ParcelFieldRole, tuple[str, ...]] = {
    ParcelFieldRole.APN: (
        "apn",
        "parcelnumb",
        "parcel_number",
        "parcel_no",
        "parcelid",
        "pin",
        "ain",
        "assessor_parcel_number",
    ),
    ParcelFieldRole.ADDRESS: (
        "address",
        "situs_address",
        "site_address",
        "property_address",
        "full_address",
    ),
    ParcelFieldRole.OWNER: (
        "owner",
        "owner_name",
        "own_name",
        "taxpayer",
        "mail_name",
    ),
    ParcelFieldRole.SITUS_CITY: ("situs_city", "site_city", "property_city"),
    ParcelFieldRole.COUNTY: ("county", "county_name"),
    ParcelFieldRole.STATE: ("state", "state_abbr"),
    ParcelFieldRole.JURISDICTION: (
        "jurisdiction",
        "city",
        "municipality",
        "agency",
    ),
    ParcelFieldRole.ZONING: ("zoning", "zone", "zoning_code", "zoning_description"),
    ParcelFieldRole.LAND_USE: ("land_use", "usecode", "usedesc", "use_desc"),
    ParcelFieldRole.ACREAGE: ("acreage", "acres", "area_acres", "gisacre"),
    ParcelFieldRole.CENTROID_LATITUDE: (
        "lat",
        "latitude",
        "centroid_latitude",
        "centroid_y",
    ),
    ParcelFieldRole.CENTROID_LONGITUDE: (
        "lon",
        "lng",
        "longitude",
        "centroid_longitude",
        "centroid_x",
    ),
    ParcelFieldRole.GEOMETRY: ("geometry", "geom", "shape", "wkt", "geojson"),
    ParcelFieldRole.SOURCE_RECORD_ID: (
        "objectid",
        "object_id",
        "fid",
        "id",
        "source_record_id",
    ),
    ParcelFieldRole.UPDATED_AT: (
        "updated_at",
        "last_updated",
        "ll_updated_at",
        "editdate",
    ),
}
_REQUIRED_ROLES = {ParcelFieldRole.APN, ParcelFieldRole.COUNTY}


def load_schema_preview_input(input_path: Path) -> ParcelSchemaPreviewInput:
    """Load a schema preview input from JSON."""

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return ParcelSchemaPreviewInput.model_validate(payload)


def build_preview_input_from_source(source: ParcelSource) -> ParcelSchemaPreviewInput:
    """Build a schema preview input from registry field mappings."""

    fields = [
        ParcelSchemaField(
            source_field=mapping.source_field,
            observed_type=ParcelObservedFieldType.UNKNOWN,
            description=mapping.notes,
        )
        for mapping in source.field_mappings
    ]
    return ParcelSchemaPreviewInput(
        source_key=source.source_key,
        source_name=source.source_name,
        source_format=source.source_format,
        observed_fields=fields,
        constant_fields=list(source.constant_fields),
        geometry_support=source.coverage.geometry_support,
        source_url=source.source_url,
        limitations=list(source.limitations),
    )


def preview_schema_for_source_key(source_key: str) -> ParcelSchemaPreviewReport:
    """Preview a registered source using its expected field mappings."""

    for source in get_parcel_sources():
        if source.source_key == source_key:
            return preview_schema(build_preview_input_from_source(source))
    raise ValueError(f"unknown parcel source key: {source_key}")


def preview_schema(preview_input: ParcelSchemaPreviewInput) -> ParcelSchemaPreviewReport:
    """Build a provider-neutral schema preview report."""

    matches = _infer_role_matches(preview_input.observed_fields)
    mapped_field_names = {match.source_field for match in matches}
    unmapped_fields = [
        field.source_field
        for field in preview_input.observed_fields
        if field.source_field not in mapped_field_names
    ]
    matched_roles = {match.field_role for match in matches}
    matched_roles.update(constant.field_role for constant in preview_input.constant_fields)
    missing_required_roles = sorted(
        _REQUIRED_ROLES - matched_roles,
        key=lambda role: role.value,
    )
    status = _status_for_preview(preview_input, matches, missing_required_roles)
    limitations = _limitations_for_preview(
        preview_input,
        unmapped_fields,
        missing_required_roles,
    )
    return ParcelSchemaPreviewReport(
        preview_id=_preview_id(preview_input),
        source_key=preview_input.source_key,
        source_name=preview_input.source_name,
        source_format=preview_input.source_format,
        status=status,
        observed_field_count=len(preview_input.observed_fields),
        mapped_fields=matches,
        constant_fields=preview_input.constant_fields,
        unmapped_fields=unmapped_fields,
        missing_required_roles=missing_required_roles,
        geometry_support=preview_input.geometry_support,
        spatial_reference=preview_input.spatial_reference,
        sample_record_count=preview_input.sample_record_count,
        limitations=limitations,
        next_action=_next_action_for_status(status),
    )


def _infer_role_matches(fields: list[ParcelSchemaField]) -> list[ParcelFieldRoleMatch]:
    """Infer canonical parcel roles from observed source field names."""

    matches: list[ParcelFieldRoleMatch] = []
    used_roles: set[ParcelFieldRole] = set()
    for field in fields:
        role, score, reason = _best_role_for_field(field.source_field)
        if role == ParcelFieldRole.UNKNOWN or role in used_roles:
            continue
        used_roles.add(role)
        matches.append(
            ParcelFieldRoleMatch(
                source_field=field.source_field,
                field_role=role,
                match_reason=reason,
                confidence_score=score,
                required_role=role in _REQUIRED_ROLES,
            )
        )
    return matches


def _best_role_for_field(source_field: str) -> tuple[ParcelFieldRole, int, str]:
    """Infer one canonical role for an observed field name."""

    normalized = _normalize_field_name(source_field)
    for role, aliases in _ROLE_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_field_name(alias)
            if normalized == normalized_alias:
                return role, 95, f"exact field-name match: {alias}"
    for role, aliases in _ROLE_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_field_name(alias)
            if normalized_alias in normalized or normalized in normalized_alias:
                return role, 75, f"partial field-name match: {alias}"
    return ParcelFieldRole.UNKNOWN, 0, "no canonical parcel role inferred"


def _normalize_field_name(value: str) -> str:
    """Normalize field names for alias matching."""

    return "_".join(part for part in _FIELD_SPLIT_RE.split(value.lower()) if part)


def _status_for_preview(
    preview_input: ParcelSchemaPreviewInput,
    matches: list[ParcelFieldRoleMatch],
    missing_required_roles: list[ParcelFieldRole],
) -> ParcelSchemaPreviewStatus:
    """Return schema preview readiness status."""

    if preview_input.source_format == ParcelSourceFormat.UNKNOWN and not matches:
        return ParcelSchemaPreviewStatus.UNSUPPORTED
    if missing_required_roles:
        return ParcelSchemaPreviewStatus.MISSING_REQUIRED_FIELDS
    if len(matches) < 3:
        return ParcelSchemaPreviewStatus.NEEDS_MAPPING
    return ParcelSchemaPreviewStatus.READY_FOR_IMPORT_PREVIEW


def _limitations_for_preview(
    preview_input: ParcelSchemaPreviewInput,
    unmapped_fields: list[str],
    missing_required_roles: list[ParcelFieldRole],
) -> list[str]:
    """Return deterministic schema preview limitations."""

    limitations = list(preview_input.limitations)
    if preview_input.spatial_reference is None:
        limitations.append("spatial reference has not been verified")
    if preview_input.geometry_support == ParcelGeometrySupport.UNKNOWN:
        limitations.append("geometry support has not been verified")
    if unmapped_fields:
        limitations.append("some observed fields were not mapped to canonical roles")
    if missing_required_roles:
        missing = ", ".join(role.value for role in missing_required_roles)
        limitations.append(f"missing required parcel roles: {missing}")
    return _unique(limitations)


def _next_action_for_status(status: ParcelSchemaPreviewStatus) -> str:
    """Return next action for preview status."""

    if status == ParcelSchemaPreviewStatus.READY_FOR_IMPORT_PREVIEW:
        return "proceed to parcel import preview using this schema mapping"
    if status == ParcelSchemaPreviewStatus.MISSING_REQUIRED_FIELDS:
        return "verify source schema or provide manual field mappings for required roles"
    if status == ParcelSchemaPreviewStatus.NEEDS_MAPPING:
        return "add manual field mappings before import preview"
    return "replace or inspect the source before import preview"


def _preview_id(preview_input: ParcelSchemaPreviewInput) -> str:
    """Build a deterministic preview id."""

    field_basis = ",".join(
        sorted(field.source_field.lower() for field in preview_input.observed_fields)
    )
    constant_basis = ",".join(
        sorted(
            f"{constant.field_role.value}={constant.value}"
            for constant in preview_input.constant_fields
        )
    )
    basis = "|".join(
        [
            preview_input.source_key,
            preview_input.source_format.value,
            field_basis,
            constant_basis,
        ]
    )
    return f"parcel-schema-preview:{_short_hash(basis)}"


def _short_hash(value: str) -> str:
    """Return a short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _unique(values: list[str]) -> list[str]:
    """Return values with duplicates removed in first-seen order."""

    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
