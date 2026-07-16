"""CEQAnet result-to-detail enrichment.

This module combines parsed CEQAnet search-result records with parsed CEQAnet
detail-page metadata. It is intentionally offline and deterministic: it does
not execute network requests, download documents, or mutate persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

EnrichmentStatus = Literal[
    "enriched",
    "unchanged",
    "sch_mismatch",
    "missing_detail",
]
FieldSource = Literal[
    "result_page",
    "detail_page",
    "unavailable",
]

_DETAIL_FIELD_NAMES = (
    "title",
    "sch_number",
    "document_type",
    "lead_agency",
    "county",
    "city",
    "project_location",
    "project_description",
    "contact",
)


@dataclass(frozen=True)
class CeqanetEnrichedRecord:
    """A CEQAnet result record enriched with detail-page metadata when available."""

    title: str | None
    detail_url: str | None
    sch_number: str | None
    document_type: str | None = None
    lead_agency: str | None = None
    county: str | None = None
    city: str | None = None
    project_location: str | None = None
    project_description: str | None = None
    contact: str | None = None
    source_url: str | None = None
    raw_result_text: str = ""
    raw_detail_text: str = ""
    title_source: str = "unavailable"
    has_human_title: bool = False
    requires_detail_enrichment: bool = False
    enrichment_status: EnrichmentStatus = "unchanged"
    field_sources: dict[str, FieldSource] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation of the enriched record."""

        return {
            "title": self.title,
            "detail_url": self.detail_url,
            "sch_number": self.sch_number,
            "document_type": self.document_type,
            "lead_agency": self.lead_agency,
            "county": self.county,
            "city": self.city,
            "project_location": self.project_location,
            "project_description": self.project_description,
            "contact": self.contact,
            "source_url": self.source_url,
            "raw_result_text": self.raw_result_text,
            "raw_detail_text": self.raw_detail_text,
            "title_source": self.title_source,
            "has_human_title": self.has_human_title,
            "requires_detail_enrichment": self.requires_detail_enrichment,
            "enrichment_status": self.enrichment_status,
            "field_sources": self.field_sources,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class CeqanetDetailEnrichmentReport:
    """A deterministic CEQAnet enrichment report."""

    records: tuple[CeqanetEnrichedRecord, ...]

    @property
    def record_count(self) -> int:
        """Return count of enriched records."""

        return len(self.records)

    @property
    def enriched_count(self) -> int:
        """Return count of records enriched from detail-page metadata."""

        return sum(record.enrichment_status == "enriched" for record in self.records)

    @property
    def missing_detail_count(self) -> int:
        """Return count of records without matching detail metadata."""

        return sum(record.enrichment_status == "missing_detail" for record in self.records)

    @property
    def sch_mismatch_count(self) -> int:
        """Return count of records with mismatched SCH identities."""

        return sum(record.enrichment_status == "sch_mismatch" for record in self.records)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation of the enrichment report."""

        return {
            "metadata": {
                "schema_version": "ceqanet_detail_enrichment.v1",
                "record_count": self.record_count,
                "enriched_count": self.enriched_count,
                "missing_detail_count": self.missing_detail_count,
                "sch_mismatch_count": self.sch_mismatch_count,
            },
            "records": [record.to_dict() for record in self.records],
        }


def enrich_ceqanet_result_record(
    result_record: dict[str, Any],
    detail_parse: dict[str, Any] | None,
) -> CeqanetEnrichedRecord:
    """Combine one parsed search-result record with optional detail metadata."""

    if detail_parse is None:
        return _record_from_result_only(result_record, status="missing_detail")

    detail = _detail_payload(detail_parse)
    detail_metadata = _metadata_payload(detail_parse)
    result_sch = _string_or_none(result_record.get("sch_number"))
    detail_sch = _string_or_none(detail.get("sch_number"))
    if result_sch is not None and detail_sch is not None and result_sch != detail_sch:
        return _record_from_result_only(
            result_record,
            status="sch_mismatch",
            warnings=(f"SCH mismatch: result={result_sch} detail={detail_sch}",),
        )

    field_sources: dict[str, FieldSource] = {}
    values: dict[str, str | None] = {}
    for field_name in _DETAIL_FIELD_NAMES:
        detail_value = _string_or_none(detail.get(field_name))
        result_value = _string_or_none(result_record.get(field_name))
        if detail_value is not None:
            values[field_name] = detail_value
            field_sources[field_name] = "detail_page"
        elif result_value is not None:
            values[field_name] = result_value
            field_sources[field_name] = "result_page"
        else:
            values[field_name] = None
            field_sources[field_name] = "unavailable"

    has_human_title = bool(detail_metadata.get("has_human_title"))
    title_source = _string_or_none(detail.get("title_source")) or _string_or_none(
        result_record.get("title_source")
    ) or "unavailable"
    requires_detail_enrichment = bool(result_record.get("requires_detail_enrichment"))
    if has_human_title:
        requires_detail_enrichment = False

    return CeqanetEnrichedRecord(
        title=values["title"],
        detail_url=_string_or_none(result_record.get("detail_url")),
        sch_number=values["sch_number"],
        document_type=values["document_type"],
        lead_agency=values["lead_agency"],
        county=values["county"],
        city=values["city"],
        project_location=values["project_location"],
        project_description=values["project_description"],
        contact=values["contact"],
        source_url=_string_or_none(result_record.get("source_url")),
        raw_result_text=_string_or_none(result_record.get("raw_text")) or "",
        raw_detail_text=_string_or_none(detail.get("raw_text")) or "",
        title_source=title_source,
        has_human_title=has_human_title,
        requires_detail_enrichment=requires_detail_enrichment,
        enrichment_status="enriched",
        field_sources=field_sources,
    )


def enrich_ceqanet_result_records(
    result_records: list[dict[str, Any]],
    detail_parses: list[dict[str, Any]],
) -> CeqanetDetailEnrichmentReport:
    """Combine parsed result records with parsed detail records by SCH number."""

    details_by_sch = _details_by_sch(detail_parses)
    enriched_records: list[CeqanetEnrichedRecord] = []
    for result_record in result_records:
        result_sch = _string_or_none(result_record.get("sch_number"))
        detail_parse = None if result_sch is None else details_by_sch.get(result_sch)
        enriched_records.append(enrich_ceqanet_result_record(result_record, detail_parse))
    return CeqanetDetailEnrichmentReport(records=tuple(enriched_records))


def _details_by_sch(detail_parses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index detail parse payloads by SCH number."""

    indexed: dict[str, dict[str, Any]] = {}
    for detail_parse in detail_parses:
        detail = _detail_payload(detail_parse)
        sch_number = _string_or_none(detail.get("sch_number"))
        if sch_number is None:
            continue
        indexed.setdefault(sch_number, detail_parse)
    return indexed


def _record_from_result_only(
    result_record: dict[str, Any],
    *,
    status: EnrichmentStatus,
    warnings: tuple[str, ...] = (),
) -> CeqanetEnrichedRecord:
    """Return a result-only enriched record for missing or unusable detail metadata."""

    field_sources: dict[str, FieldSource] = {}
    for field_name in _DETAIL_FIELD_NAMES:
        result_value = _string_or_none(result_record.get(field_name))
        if result_value is not None:
            field_sources[field_name] = "result_page"
        else:
            field_sources[field_name] = "unavailable"

    return CeqanetEnrichedRecord(
        title=_string_or_none(result_record.get("title")),
        detail_url=_string_or_none(result_record.get("detail_url")),
        sch_number=_string_or_none(result_record.get("sch_number")),
        document_type=_string_or_none(result_record.get("document_type")),
        lead_agency=_string_or_none(result_record.get("lead_agency")),
        county=_string_or_none(result_record.get("county")),
        city=_string_or_none(result_record.get("city")),
        project_location=_string_or_none(result_record.get("project_location")),
        project_description=_string_or_none(result_record.get("project_description")),
        contact=_string_or_none(result_record.get("contact")),
        source_url=_string_or_none(result_record.get("source_url")),
        raw_result_text=_string_or_none(result_record.get("raw_text")) or "",
        title_source=_string_or_none(result_record.get("title_source")) or "unavailable",
        has_human_title=False,
        requires_detail_enrichment=bool(result_record.get("requires_detail_enrichment")),
        enrichment_status=status,
        field_sources=field_sources,
        warnings=warnings,
    )


def _metadata_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return metadata payload from a detail parse JSON object."""

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        return cast(dict[str, Any], metadata)
    return {}


def _detail_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return detail payload from a detail parse JSON object."""

    detail = payload.get("detail")
    if isinstance(detail, dict):
        return cast(dict[str, Any], detail)
    return {}


def _string_or_none(value: object) -> str | None:
    """Return a non-empty string or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
