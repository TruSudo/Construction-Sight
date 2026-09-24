"""Rehydrate genuine retained CEQAnet CSV into a reviewed, non-mutating write plan.

The bridge does not fetch URLs, invent geography, qualify leads or bypass the
existing exact-write-plan authorization/effect-consumption boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import HttpUrl

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import CeqanetCsvExportKind
from constructionsight.ceqanet_csv_replay_service import (
    build_ceqanet_csv_encoding_replay,
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_persistence_preview import CeqanetPersistencePreview
from constructionsight.ceqanet_write_plan import CeqanetWritePlan, build_ceqanet_write_plan
from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site

_MAX_ROWS = 100
_EXACT_APN = re.compile(r"^[0-9A-Za-z]{2,8}(?:[- ][0-9A-Za-z]{1,8}){1,4}$")
_SOURCE_PORTAL = re.compile(r"^https://ceqanet[.]lci[.]ca[.]gov/([0-9]{10})(?:/([0-9]+))?/?$")


@dataclass(frozen=True)
class ReviewedCeqanetCsvBridge:
    """Detached, immutable result of replaying verified retained source bytes."""

    preview: CeqanetPersistencePreview
    write_plan: CeqanetWritePlan
    source_sha256: str
    source_execution_digest: str
    source_inspection_digest: str
    source_record_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "source_execution_digest": self.source_execution_digest,
            "source_inspection_digest": self.source_inspection_digest,
            "source_record_keys": list(self.source_record_keys),
            "preview": self.preview.to_dict(),
            "write_plan": self.write_plan.to_dict(),
            "network_executed": False,
            "persistence_mutated": False,
            "lead_created": False,
            "source_claims_verified": False,
        }


def _value(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        raw = row.get(key, "").strip()
        if raw:
            return raw
    return None


def _source_date(raw: str | None) -> datetime.date | None:
    if raw is None:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError("retained CEQAnet date does not match a supported exact format")


def _portal_url(raw: str | None, *, sch: str) -> HttpUrl | None:
    if raw is None:
        return None
    match = _SOURCE_PORTAL.fullmatch(raw)
    if match is None or match[1] != sch:
        raise ValueError("retained document portal URL is not the exact official SCH scope")
    return HttpUrl(raw)


def _exact_apn(raw: str | None) -> str | None:
    if raw is None or raw.lower().startswith(("multiple", "various", "see ")):
        return None
    if len(raw) > 48 or not _EXACT_APN.fullmatch(raw):
        return None
    return raw


def build_reviewed_ceqanet_csv_bridge(
    execution: CeqanetCsvLiveExecution,
) -> ReviewedCeqanetCsvBridge:
    """Build a bounded write plan from independently replayed, exact retained bytes."""

    if execution.request.export_kind is not CeqanetCsvExportKind.PROJECT:
        raise ValueError("reviewed CSV project bridge requires project-scope export evidence")
    if execution.inspection is not None and execution.inspection_error is not None:
        raise ValueError("retained CSV inspection state is contradictory")
    replay = build_ceqanet_csv_encoding_replay(execution, max_retained_rows=_MAX_ROWS)
    verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    if not verification.passed:
        raise ValueError("retained CEQAnet CSV replay verification failed")
    inspection = replay.inspection
    if (
        inspection.rows_truncated
        or inspection.row_count != inspection.retained_row_count
        or not 1 <= inspection.row_count <= _MAX_ROWS
    ):
        raise ValueError("reviewed CSV project bridge requires all rows, up to 100")
    if execution.inspection is not None and execution.inspection != inspection:
        # Compare the invariant complete column/data projection, not an inspection
        # digest that may have been generated under a different retained-row cap.
        if (
            execution.inspection.rows_truncated
            or execution.inspection.rows != inspection.rows
            or execution.inspection.columns != inspection.columns
        ):
            raise ValueError("source inspection and replay disagree")
    ceqa_records: list[CeqaRecord] = []
    sites: list[Site] = []
    entities: list[Entity] = []
    keys: set[str] = set()
    for row_index, row in enumerate(inspection.rows):
        sch = _value(row, "sch_number")
        if sch != execution.request.sch_number:
            raise ValueError("retained CSV SCH does not match the captured request")
        title = _value(row, "project_title", "title")
        county = _value(row, "counties", "county")
        if title is None or county is None:
            raise ValueError("retained CSV project row lacks title or county")
        if county not in {"San Bernardino", "Riverside"}:
            raise ValueError("reviewed CSV project bridge is limited to the two target counties")
        portal = _portal_url(_value(row, "document_portal_url"), sch=sch)
        row_payload = json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        row_digest = hashlib.sha256(row_payload.encode("utf-8")).hexdigest()
        # Distinct captured documents/revisions remain distinct source observations,
        # rather than overwriting an earlier source assertion about the same SCH.
        key = f"ceqa:ceqanet:csv:{sch}:{row_digest[:24]}"
        if key in keys:
            raise ValueError("duplicate exact CSV row in the retained export")
        keys.add(key)
        raw_reference = f"SCH:{sch};CSV-row:{row_index + 1};sha256:{row_digest}"
        provenance = Provenance(
            source_name="Retained CEQAnet CSV source observation",
            source_url=portal or HttpUrl(execution.request.source_url),
            captured_at=execution.executed_at,
            adapter_family="ceqanet_csv_reviewed",
            raw_reference=raw_reference,
            evidence_text=row_payload,
            confidence_score=0,
            verified=False,
            notes=(
                "Source-claimed public CSV row only; no independent fact verification. "
                f"Parent retained body sha256:{inspection.body_sha256}; "
                f"execution digest:{execution.execution_digest}; "
                "raw response preserved in the referenced evidence execution artifact."
            ),
        )
        apn = _exact_apn(_value(row, "location_parcel_number", "apn", "parcel_number"))
        site = (
            Site(
                site_key=f"site:ceqanet:csv:{sch}:{row_digest[:24]}",
                county=county,
                apn=apn,
                provenance=[provenance],
            )
            if apn else None
        )
        if site is not None:
            sites.append(site)
        agency = _value(row, "lead_agency_name", "lead_agency")
        named: list[Entity] = []
        if agency:
            entity = Entity(
                entity_key=f"entity:ceqanet:csv:agency:{sch}:{row_digest[:24]}",
                name=agency,
                role=PartyRole.AGENCY,
                county=county,
                provenance=[provenance],
            )
            entities.append(entity)
            named.append(entity)
        ceqa_records.append(
            CeqaRecord(
                ceqa_key=key,
                title=title,
                county=county,
                lead_agency=agency,
                document_type=_value(row, "document_type"),
                state_clearinghouse_number=sch,
                received_date=_source_date(_value(row, "received", "received_date")),
                posted_date=_source_date(_value(row, "posted", "posted_date")),
                project_location=_value(row, "location_cross_streets", "project_location"),
                description=_value(row, "document_description", "project_description"),
                site=site,
                entities=named,
                provenance=[provenance],
            )
        )
    preview = CeqanetPersistencePreview(
        ceqa_records=tuple(ceqa_records),
        sites=tuple(sites),
        entities=tuple(entities),
        skipped_records=(),
    )
    write_plan = build_ceqanet_write_plan(preview.to_dict())
    if write_plan.skipped_items or write_plan.operation_count != preview.planned_write_count:
        raise ValueError("retained source preview could not be fully represented as a write plan")
    return ReviewedCeqanetCsvBridge(
        preview=preview,
        write_plan=write_plan,
        source_sha256=inspection.body_sha256,
        source_execution_digest=execution.execution_digest,
        source_inspection_digest=inspection.inspection_digest,
        source_record_keys=tuple(record.ceqa_key for record in ceqa_records),
    )
