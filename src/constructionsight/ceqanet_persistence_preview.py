"""CEQAnet persistence preview service.

This module converts CEQAnet chain reports into normalized domain-model previews.
It is intentionally non-mutating: it does not open a database, write records,
execute network requests, or download documents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from pydantic import HttpUrl

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance, ProvenanceConfidenceBasis
from constructionsight.site_models import Site


@dataclass(frozen=True)
class CeqanetPersistencePreview:
    """Non-mutating persistence preview for one CEQAnet chain report."""

    ceqa_records: tuple[CeqaRecord, ...]
    sites: tuple[Site, ...]
    entities: tuple[Entity, ...]
    skipped_records: tuple[dict[str, object], ...]

    @property
    def planned_write_count(self) -> int:
        """Return total records that would be written by a later persistence step."""

        return len(self.ceqa_records) + len(self.sites) + len(self.entities)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe preview payload."""

        return {
            "metadata": {
                "schema_version": "ceqanet_persistence_preview.v1",
                "ceqa_record_count": len(self.ceqa_records),
                "site_count": len(self.sites),
                "entity_count": len(self.entities),
                "skipped_record_count": len(self.skipped_records),
                "planned_write_count": self.planned_write_count,
                "network_executed": False,
                "persistence_mutated": False,
            },
            "ceqa_records": [record.model_dump(mode="json") for record in self.ceqa_records],
            "sites": [site.model_dump(mode="json") for site in self.sites],
            "entities": [entity.model_dump(mode="json") for entity in self.entities],
            "skipped_records": list(self.skipped_records),
        }


def build_ceqanet_persistence_preview(chain_report: dict[str, Any]) -> CeqanetPersistencePreview:
    """Build normalized CEQA/site/entity previews from a CEQAnet chain report."""

    enrichment = chain_report.get("enrichment")
    if not isinstance(enrichment, dict):
        raise ValueError("Chain report must contain an enrichment object.")
    records = enrichment.get("records")
    if not isinstance(records, list):
        raise ValueError("Chain report enrichment must contain a records list.")

    ceqa_records: list[CeqaRecord] = []
    sites_by_key: dict[str, Site] = {}
    entities_by_key: dict[str, Entity] = {}
    skipped_records: list[dict[str, object]] = []

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            skipped_records.append({"index": index, "reason": "record is not an object"})
            continue
        typed_record = cast(dict[str, Any], record)
        sch_number = _string_or_none(typed_record.get("sch_number"))
        title = _string_or_none(typed_record.get("title"))
        if sch_number is None or title is None:
            skipped_records.append(
                {
                    "index": index,
                    "reason": "missing SCH number or title",
                    "sch_number": sch_number,
                    "title": title,
                }
            )
            continue

        provenance = _provenance_for_record(typed_record)
        site = _site_for_record(typed_record, sch_number=sch_number, provenance=provenance)
        if site is not None:
            sites_by_key.setdefault(site.site_key, site)

        entity = _lead_agency_entity_for_record(typed_record, provenance=provenance)
        entities: list[Entity] = []
        if entity is not None:
            entities_by_key.setdefault(entity.entity_key, entity)
            entities.append(entity)

        ceqa_records.append(
            CeqaRecord(
                ceqa_key=f"ceqa:ceqanet:{sch_number}",
                title=title,
                county=_string_or_none(typed_record.get("county")),
                lead_agency=_string_or_none(typed_record.get("lead_agency")),
                document_type=_string_or_none(typed_record.get("document_type")),
                state_clearinghouse_number=sch_number,
                project_location=_string_or_none(typed_record.get("project_location")),
                description=_string_or_none(typed_record.get("project_description")),
                site=site,
                entities=entities,
                provenance=[provenance],
            )
        )

    return CeqanetPersistencePreview(
        ceqa_records=tuple(ceqa_records),
        sites=tuple(sites_by_key.values()),
        entities=tuple(entities_by_key.values()),
        skipped_records=tuple(skipped_records),
    )


def _provenance_for_record(record: dict[str, Any]) -> Provenance:
    """Build provenance for one CEQAnet enriched record."""

    detail_url = _string_or_none(record.get("detail_url"))
    source_url = _string_or_none(record.get("source_url"))
    evidence_text = _string_or_none(record.get("raw_detail_text")) or _string_or_none(
        record.get("raw_result_text")
    )
    confidence_basis = ProvenanceConfidenceBasis.UNASSESSED
    if evidence_text is not None:
        confidence_basis = ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION

    return Provenance(
        source_name="CEQAnet",
        source_url=_http_url_or_none(detail_url or source_url),
        adapter_family="ceqanet",
        raw_reference=_string_or_none(record.get("sch_number")),
        evidence_text=evidence_text,
        confidence_basis=confidence_basis,
        notes="Generated by CEQAnet persistence preview; no persistence mutation performed.",
    )


def _site_for_record(
    record: dict[str, Any],
    *,
    sch_number: str,
    provenance: Provenance,
) -> Site | None:
    """Build a site preview when location evidence exists."""

    county = _string_or_none(record.get("county"))
    city = _string_or_none(record.get("city"))
    location = _string_or_none(record.get("project_location"))
    if county is None:
        return None

    return Site(
        site_key=f"site:ceqanet:{sch_number}",
        county=county,
        jurisdiction=city,
        address=location,
        city=city,
        provenance=[provenance],
    )


def _lead_agency_entity_for_record(
    record: dict[str, Any],
    *,
    provenance: Provenance,
) -> Entity | None:
    """Build a lead-agency entity preview when lead agency evidence exists."""

    lead_agency = _string_or_none(record.get("lead_agency"))
    if lead_agency is None:
        return None

    return Entity(
        entity_key=f"entity:ceqanet:lead-agency:{_slug(lead_agency)}",
        name=lead_agency,
        role=PartyRole.AGENCY,
        county=_string_or_none(record.get("county")),
        jurisdiction=_string_or_none(record.get("city")),
        provenance=[provenance],
    )


def _http_url_or_none(value: str | None) -> HttpUrl | None:
    """Return a validated HTTP URL for Pydantic domain models."""

    if value is None:
        return None
    return HttpUrl(value)


def _slug(value: str) -> str:
    """Return a stable lowercase key fragment."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _string_or_none(value: object) -> str | None:
    """Return a non-empty string value or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
