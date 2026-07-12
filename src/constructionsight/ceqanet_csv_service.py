"""Offline-first contract for source-provided CEQAnet CSV exports."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

from constructionsight.ceqanet_csv_models import (
    CeqanetCsvCanonicalRole,
    CeqanetCsvColumn,
    CeqanetCsvExportKind,
    CeqanetCsvExportRequest,
    CeqanetCsvInspection,
    canonical_digest,
)

_CSV_HOST = "ceqanet.lci.ca.gov"
_CSV_PATH = "/Search"
_MAX_CSV_BYTES = 10_000_000
_ALLOWED_MEDIA_TYPES = {
    "application/csv",
    "application/octet-stream",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
}
_ROLE_ALIASES: dict[CeqanetCsvCanonicalRole, set[str]] = {
    CeqanetCsvCanonicalRole.SCH_NUMBER: {
        "sch",
        "sch_no",
        "sch_num",
        "sch_number",
        "schnumber",
        "state_clearinghouse_number",
    },
    CeqanetCsvCanonicalRole.DOCUMENT_ID: {"document_id", "documentid"},
    CeqanetCsvCanonicalRole.DOCUMENT_TYPE: {"document_type", "documenttype", "type"},
    CeqanetCsvCanonicalRole.LEAD_AGENCY: {
        "lead_agency",
        "lead_public_agency",
        "leadagency",
    },
    CeqanetCsvCanonicalRole.RECEIVED_DATE: {
        "date_received",
        "received",
        "received_date",
    },
    CeqanetCsvCanonicalRole.TITLE: {
        "document_title",
        "project_title",
        "title",
    },
    CeqanetCsvCanonicalRole.COUNTY: {"county", "county_name"},
    CeqanetCsvCanonicalRole.LOCATION: {
        "location",
        "project_location",
        "project_location_city",
    },
    CeqanetCsvCanonicalRole.DESCRIPTION: {
        "description",
        "project_description",
    },
    CeqanetCsvCanonicalRole.CONTACT_NAME: {
        "contact",
        "contact_name",
        "contact_person",
    },
    CeqanetCsvCanonicalRole.CONTACT_EMAIL: {"contact_email", "email"},
    CeqanetCsvCanonicalRole.CONTACT_PHONE: {"contact_phone", "phone"},
    CeqanetCsvCanonicalRole.PARCEL_NUMBER: {
        "apn",
        "parcel",
        "parcel_number",
        "parcel_numbers",
    },
}


def build_ceqanet_csv_export_request(
    *,
    sch_number: str,
    document_id: int | None = None,
) -> CeqanetCsvExportRequest:
    """Build one deterministic source-provided CEQAnet CSV request identity."""

    _validate_sch_number(sch_number)
    if document_id is None:
        query = [("OutputFormat", "CSV"), ("Sch", sch_number)]
        export_kind = CeqanetCsvExportKind.PROJECT
    else:
        if document_id < 1:
            raise ValueError("document_id must be greater than 0")
        query = [
            ("DocumentId", str(document_id)),
            ("OutputFormat", "CSV"),
            ("Sch", sch_number),
        ]
        export_kind = CeqanetCsvExportKind.DOCUMENT
    source_url = f"https://{_CSV_HOST}{_CSV_PATH}?{urlencode(query)}"
    return CeqanetCsvExportRequest(
        export_kind=export_kind,
        sch_number=sch_number,
        document_id=document_id,
        source_url=source_url,
    )


def parse_ceqanet_csv_export_url(url: str) -> CeqanetCsvExportRequest:
    """Parse and strictly validate one observed CEQAnet CSV export URL."""

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != _CSV_HOST:
        raise ValueError("CEQAnet CSV URL must use the approved official HTTPS host")
    if parsed.path != _CSV_PATH:
        raise ValueError("CEQAnet CSV URL must use the official /Search path")
    if parsed.params or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ValueError("CEQAnet CSV URL contains unsupported authority or URL components")
    try:
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ValueError("CEQAnet CSV URL query is malformed") from exc
    counts = Counter(name for name, _ in pairs)
    duplicate_names = sorted(name for name, count in counts.items() if count != 1)
    if duplicate_names:
        raise ValueError(f"CEQAnet CSV URL contains duplicate query keys: {duplicate_names}")
    values = dict(pairs)
    if values.get("OutputFormat") != "CSV":
        raise ValueError("CEQAnet CSV URL must request OutputFormat=CSV")
    allowed_keys = {"OutputFormat", "Sch", "DocumentId"}
    extra_keys = sorted(set(values) - allowed_keys)
    if extra_keys:
        raise ValueError(f"CEQAnet CSV URL contains unsupported query keys: {extra_keys}")
    if set(values) not in (
        {"OutputFormat", "Sch"},
        {"DocumentId", "OutputFormat", "Sch"},
    ):
        raise ValueError("CEQAnet CSV URL does not match a supported export query shape")
    sch_number = values.get("Sch", "")
    _validate_sch_number(sch_number)
    document_text = values.get("DocumentId")
    if document_text is None:
        return build_ceqanet_csv_export_request(sch_number=sch_number)
    if not document_text.isdigit() or int(document_text) < 1:
        raise ValueError("CEQAnet CSV DocumentId must be a positive integer")
    return build_ceqanet_csv_export_request(
        sch_number=sch_number,
        document_id=int(document_text),
    )


def inspect_ceqanet_csv_bytes(
    request: CeqanetCsvExportRequest,
    content: bytes,
    *,
    content_type: str | None = None,
    max_retained_rows: int = 1_000,
) -> CeqanetCsvInspection:
    """Inspect one already-obtained CSV body without network or persistence access."""

    canonical_request = parse_ceqanet_csv_export_url(request.source_url)
    if canonical_request != request:
        raise ValueError("CEQAnet CSV request fields do not agree with source_url")
    if not content:
        raise ValueError("CEQAnet CSV body must not be empty")
    if len(content) > _MAX_CSV_BYTES:
        raise ValueError(f"CEQAnet CSV body exceeds {_MAX_CSV_BYTES} bytes")
    if max_retained_rows < 0:
        raise ValueError("max_retained_rows cannot be negative")
    normalized_content_type = _validate_content_type(content_type)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CEQAnet CSV body must use UTF-8 or UTF-8 with BOM") from exc
    if "\x00" in text:
        raise ValueError("CEQAnet CSV body contains a NUL character")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        raw_rows = list(reader)
    except csv.Error as exc:
        raise ValueError(f"CEQAnet CSV syntax is invalid: {exc}") from exc
    nonblank_rows = [row for row in raw_rows if any(cell.strip() for cell in row)]
    if len(nonblank_rows) < 2:
        raise ValueError("CEQAnet CSV must contain a header and at least one data row")

    header = [cell.strip() for cell in nonblank_rows[0]]
    columns = _build_columns(header)
    canonical_role_columns = {
        column.canonical_role: column.ordinal
        for column in columns
        if column.canonical_role is not None
    }
    sch_ordinal = canonical_role_columns.get(CeqanetCsvCanonicalRole.SCH_NUMBER)
    if sch_ordinal is None:
        raise ValueError("CEQAnet CSV must expose an identifiable SCH number column")

    parsed_rows: list[dict[str, str]] = []
    row_count = 0
    for row_number, row in enumerate(nonblank_rows[1:], start=2):
        if len(row) != len(columns):
            raise ValueError(
                f"CEQAnet CSV row {row_number} has {len(row)} values; expected {len(columns)}"
            )
        values = [cell.strip() for cell in row]
        observed_sch = values[sch_ordinal]
        if not re.fullmatch(r"\d{10}", observed_sch):
            raise ValueError(f"CEQAnet CSV row {row_number} contains an invalid SCH number")
        if observed_sch != request.sch_number:
            raise ValueError(
                f"CEQAnet CSV row {row_number} SCH number does not match the request"
            )
        row_count += 1
        if len(parsed_rows) < max_retained_rows:
            parsed_rows.append(
                {
                    column.normalized_name: value
                    for column, value in zip(columns, values, strict=True)
                }
            )

    unknown_columns = [
        column.normalized_name for column in columns if column.canonical_role is None
    ]
    warnings: list[str] = []
    if normalized_content_type is None:
        warnings.append("content type was not supplied; body validation is CSV-only")
    if unknown_columns:
        warnings.append("unknown columns are preserved without inferred meaning")
    payload: dict[str, Any] = {
        "request": request,
        "content_type": normalized_content_type,
        "byte_length": len(content),
        "body_sha256": hashlib.sha256(content).hexdigest(),
        "column_count": len(columns),
        "columns": columns,
        "row_count": row_count,
        "retained_row_count": len(parsed_rows),
        "rows": parsed_rows,
        "rows_truncated": len(parsed_rows) < row_count,
        "unknown_columns": unknown_columns,
        "warnings": warnings,
    }
    digest_payload = _jsonable_inspection_payload(payload)
    inspection = CeqanetCsvInspection(
        **payload,
        inspection_digest=canonical_digest(digest_payload),
    )
    inspection.assert_integrity()
    return inspection


def _validate_sch_number(value: str) -> None:
    if not re.fullmatch(r"\d{10}", value):
        raise ValueError("sch_number must contain exactly 10 digits")


def _validate_content_type(value: str | None) -> str | None:
    if value is None:
        return None
    media_type = value.split(";", maxsplit=1)[0].strip().lower()
    if media_type not in _ALLOWED_MEDIA_TYPES:
        raise ValueError(f"unsupported CEQAnet CSV content type: {media_type}")
    return media_type


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _role_for_normalized_header(value: str) -> CeqanetCsvCanonicalRole | None:
    matches = [role for role, aliases in _ROLE_ALIASES.items() if value in aliases]
    if len(matches) > 1:
        raise ValueError(f"CSV header {value!r} maps to multiple canonical roles")
    return matches[0] if matches else None


def _build_columns(header: Iterable[str]) -> list[CeqanetCsvColumn]:
    columns: list[CeqanetCsvColumn] = []
    for ordinal, original_name in enumerate(header):
        if not original_name:
            raise ValueError(f"CEQAnet CSV column {ordinal + 1} has a blank header")
        normalized_name = _normalize_header(original_name)
        if not normalized_name:
            raise ValueError(f"CEQAnet CSV column {ordinal + 1} has no usable header text")
        columns.append(
            CeqanetCsvColumn(
                ordinal=ordinal,
                original_name=original_name,
                normalized_name=normalized_name,
                canonical_role=_role_for_normalized_header(normalized_name),
            )
        )
    normalized_names = [column.normalized_name for column in columns]
    duplicates = sorted(
        name for name, count in Counter(normalized_names).items() if count > 1
    )
    if duplicates:
        raise ValueError(f"CEQAnet CSV contains duplicate normalized headers: {duplicates}")
    roles = [column.canonical_role for column in columns if column.canonical_role is not None]
    duplicate_roles = sorted(role.value for role, count in Counter(roles).items() if count > 1)
    if duplicate_roles:
        raise ValueError(f"CEQAnet CSV contains ambiguous canonical roles: {duplicate_roles}")
    return columns


def _jsonable_inspection_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return CeqanetCsvInspection.model_construct(
        **payload,
        inspection_digest="0" * 64,
    ).evidence_payload()
