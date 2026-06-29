"""Provider-neutral parcel row preview service."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from constructionsight.parcel_row_preview_models import (
    ParcelRowPreview,
    ParcelRowPreviewInput,
    ParcelRowPreviewReport,
    ParcelRowPreviewStatus,
)
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
)
from constructionsight.site_resolution_service import normalize_address, normalize_apn

_REQUIRED_ROLES = {ParcelFieldRole.APN, ParcelFieldRole.COUNTY}


def load_row_preview_input(input_path: Path) -> ParcelRowPreviewInput:
    """Load a parcel row preview input from JSON."""

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return ParcelRowPreviewInput.model_validate(payload)


def preview_rows(preview_input: ParcelRowPreviewInput) -> ParcelRowPreviewReport:
    """Preview candidate parcel rows without persistence."""

    role_to_field = {
        match.field_role: match.source_field for match in preview_input.field_role_matches
    }
    mapped_roles = sorted(role_to_field, key=lambda role: role.value)
    missing_required_roles = sorted(
        _REQUIRED_ROLES - set(mapped_roles),
        key=lambda role: role.value,
    )
    rows = [
        _preview_row(row_number=index + 1, row=row, role_to_field=role_to_field)
        for index, row in enumerate(preview_input.rows)
    ]
    usable_count = sum(1 for row in rows if row.usable)
    skipped_count = len(rows) - usable_count
    status = _status_for_preview(rows, missing_required_roles)
    limitations = _limitations_for_preview(
        preview_input,
        missing_required_roles,
        skipped_count,
    )
    return ParcelRowPreviewReport(
        preview_id=_preview_id(preview_input),
        source_key=preview_input.source_key,
        source_name=preview_input.source_name,
        source_format=preview_input.source_format,
        status=status,
        row_count=len(rows),
        usable_row_count=usable_count,
        skipped_row_count=skipped_count,
        mapped_roles=mapped_roles,
        rows=rows,
        geometry_support=preview_input.geometry_support,
        spatial_reference=preview_input.spatial_reference,
        limitations=limitations,
        next_action=_next_action_for_status(status),
    )


def _preview_row(
    *,
    row_number: int,
    row: dict[str, str],
    role_to_field: dict[ParcelFieldRole, str],
) -> ParcelRowPreview:
    """Preview one candidate parcel row."""

    apn_value = _value_for_role(row, role_to_field, ParcelFieldRole.APN)
    address_value = _value_for_role(row, role_to_field, ParcelFieldRole.ADDRESS)
    county_value = _value_for_role(row, role_to_field, ParcelFieldRole.COUNTY)
    source_record_id = _value_for_role(row, role_to_field, ParcelFieldRole.SOURCE_RECORD_ID)
    geometry_value = _value_for_role(row, role_to_field, ParcelFieldRole.GEOMETRY)
    limitations: list[str] = []
    normalized_apn = normalize_apn(apn_value) if apn_value else None
    normalized_address = normalize_address(address_value) if address_value else None

    if not normalized_apn:
        limitations.append("missing APN value")
    if not county_value:
        limitations.append("missing county value")

    return ParcelRowPreview(
        row_number=row_number,
        usable=not limitations,
        normalized_apn=normalized_apn,
        normalized_address=normalized_address,
        county=county_value,
        source_record_id=source_record_id,
        geometry_present=bool(geometry_value),
        limitations=limitations,
    )


def _value_for_role(
    row: dict[str, str],
    role_to_field: dict[ParcelFieldRole, str],
    role: ParcelFieldRole,
) -> str | None:
    """Return trimmed row value for a canonical role."""

    source_field = role_to_field.get(role)
    if source_field is None:
        return None
    value = row.get(source_field)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _status_for_preview(
    rows: list[ParcelRowPreview],
    missing_required_roles: list[ParcelFieldRole],
) -> ParcelRowPreviewStatus:
    """Return row preview status."""

    if not rows:
        return ParcelRowPreviewStatus.EMPTY_SOURCE
    if missing_required_roles:
        return ParcelRowPreviewStatus.NEEDS_SCHEMA_MAPPING
    if any(not row.usable for row in rows):
        return ParcelRowPreviewStatus.ROW_ISSUES
    return ParcelRowPreviewStatus.READY_FOR_PARCEL_RECORD_MODEL


def _limitations_for_preview(
    preview_input: ParcelRowPreviewInput,
    missing_required_roles: list[ParcelFieldRole],
    skipped_count: int,
) -> list[str]:
    """Return deterministic preview limitations."""

    limitations = list(preview_input.limitations)
    if preview_input.spatial_reference is None:
        limitations.append("spatial reference has not been verified")
    if preview_input.geometry_support == ParcelGeometrySupport.UNKNOWN:
        limitations.append("geometry support has not been verified")
    if missing_required_roles:
        missing = ", ".join(role.value for role in missing_required_roles)
        limitations.append(f"missing required mapped roles: {missing}")
    if skipped_count:
        limitations.append("one or more rows need source review before persistence")
    return _unique(limitations)


def _next_action_for_status(status: ParcelRowPreviewStatus) -> str:
    """Return next action for row preview status."""

    if status == ParcelRowPreviewStatus.READY_FOR_PARCEL_RECORD_MODEL:
        return "proceed to ParcelRecord and geometry normalization"
    if status == ParcelRowPreviewStatus.NEEDS_SCHEMA_MAPPING:
        return "return to schema preview and add required field mappings"
    if status == ParcelRowPreviewStatus.ROW_ISSUES:
        return "review skipped rows before building ParcelRecord objects"
    return "provide sample rows before building ParcelRecord objects"


def _preview_id(preview_input: ParcelRowPreviewInput) -> str:
    """Build a deterministic row preview id."""

    basis = "|".join(
        [
            preview_input.source_key,
            preview_input.source_format.value,
            str(len(preview_input.rows)),
        ]
    )
    return f"parcel-row-preview:{_short_hash(basis)}"


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
