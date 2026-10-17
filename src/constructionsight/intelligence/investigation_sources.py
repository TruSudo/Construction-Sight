"""Offline normalizers connecting retained source families to shared investigations.

These adapters preserve source claims and their limitations. They acquire no new
data, verify no construction activity, and authorize no commercial action.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from constructionsight.agenda_models import AgendaItemRecord
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.document_models import DocumentRecord
from constructionsight.intake_models import FactConfidence, MaterialFactKind, UniversalIntakeRecord
from constructionsight.intelligence.artifact_identity import IdentityArtifactType as Artifact
from constructionsight.intelligence.artifact_identity import normalize_artifact_value
from constructionsight.intelligence.investigation_service import InvestigationObservation
from constructionsight.intelligence.schemas import EvidenceRecord
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.permit_models import PermitRecord
from constructionsight.planning_models import PlanningCaseRecord
from constructionsight.provenance import Provenance
from constructionsight.site_models import Site
from constructionsight.site_resolution_service import resolve_site_from_intake
from constructionsight.smarts_evidence_ledger import RetainedSmartsObservation
from constructionsight.smarts_intake_bridge import SOURCE_FAMILY, SOURCE_NAME

RETAINED_SOURCE_KINDS = ("ceqa", "permit", "planning", "agenda", "document", "intake", "parcel")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.casefold() not in {"n/a", "null", "none", "unknown"} else None


def _artifacts(**values: str | None) -> dict[Artifact, list[str]]:
    return {Artifact(key): [value] for key, value in values.items() if value}


def _evidence(
    *,
    family: str,
    source_name: str,
    record_id: str,
    record_type: str,
    at: datetime,
    raw: dict[str, Any],
    url: str | None = None,
    jurisdiction: str | None = None,
    observed_at: datetime | None = None,
    limitations: list[str] | None = None,
) -> EvidenceRecord:
    content: dict[str, Any] = {
        "family": family,
        "source": source_name,
        "record_id": record_id,
        "record_type": record_type,
        "retained_at": at.isoformat(),
        "payload": raw,
        "source_url": url,
        "jurisdiction": jurisdiction,
        "observed_at": observed_at.isoformat() if observed_at else None,
    }
    if limitations is not None:
        content["source_limitations"] = limitations
    digest = hashlib.sha256(
        json.dumps(
            content,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return EvidenceRecord(
        evidence_id=f"evidence:source-observation:{digest}",
        source_family=family,
        source_name=source_name,
        source_record_id=record_id,
        record_type=record_type,
        retrieved_at=at,
        observed_at=observed_at,
        source_url=url,
        jurisdiction=jurisdiction,
        raw_observations=raw,
        retrieval_method="offline_retained_source_replay",
        limitations=[
            "Source claims are retained, not independently verified.",
            "No current construction, identity or commercial readiness is established.",
        ]
        + (limitations or []),
    )


def from_smarts(item: RetainedSmartsObservation) -> InvestigationObservation:
    """Use the existing SMARTS identity/site preview, with exact-response lineage."""
    row = item.row
    candidates = item.preview.site_resolution.candidates
    latitude = longitude = None
    # Use the existing site resolver's unambiguous, CA-envelope-checked projection.
    if len(candidates) == 1:
        latitude, longitude = candidates[0].latitude, candidates[0].longitude
        if latitude is None or longitude is None:
            latitude = longitude = None
    return InvestigationObservation(
        evidence=_evidence(
            family=SOURCE_FAMILY,
            source_name=SOURCE_NAME,
            record_id=item.source_key,
            record_type="smarts",
            at=item.recorded_at,
            url=item.page.request_url,
            raw={
                "source_row": row,
                "response_sha256": item.page.response_sha256,
                "row_sha256": item.preview.record_sha256,
                "journal_observation_id": item.observation_id,
                # Preview receipt timestamps are regenerated on every read. Bind the
                # stable existing intake/resolution identities, not transient metadata.
                "intake_id": item.preview.intake.intake_id,
                "site_resolution_id": item.preview.site_resolution.resolution_id,
                "intake_limitations": item.preview.limitations,
            },
        ),
        title=_text(row.get("SITE_NAME")),
        county=_text(row.get("SITE_COUNTY")),
        artifacts=_artifacts(
            apn=_text(row.get("APN")), exact_site_address=_text(row.get("SITE_ADDRESS"))
        ),
        latitude=latitude,
        longitude=longitude,
    )


def _retained_time(provenance: list[Provenance]) -> datetime:
    captured = [item.captured_at for item in provenance if item.captured_at is not None]
    if not captured:
        raise ValueError("retained domain record requires a captured provenance timestamp")
    return max(captured)


def _location(site: Site | None) -> dict[str, Any]:
    if site is None:
        return {"latitude": None, "longitude": None}
    # Incomplete coordinates remain unmapped; their original claim stays in evidence.
    if site.latitude is None or site.longitude is None:
        return {"latitude": None, "longitude": None}
    return {"latitude": site.latitude, "longitude": site.longitude}


def from_domain(
    record: CeqaRecord | PermitRecord | PlanningCaseRecord | AgendaItemRecord,
) -> InvestigationObservation:
    """Adapt existing typed CEQA/permit records, retaining their related source parties."""
    at = _retained_time(record.provenance)
    source = record.provenance[0]
    title: str | None
    if isinstance(record, CeqaRecord):
        family, identity, title = "ceqa", record.ceqa_key, record.title
        jurisdiction = record.site.jurisdiction if record.site else None
        artifacts = _artifacts(
            ceqa_sch_number=record.state_clearinghouse_number,
            apn=record.site.apn if record.site else None,
            exact_site_address=record.site.address if record.site else None,
        )
        location = _location(record.site)
    elif isinstance(record, PermitRecord):
        family, identity, title = "permit", record.permit_key, record.description
        jurisdiction = record.jurisdiction
        artifacts = _artifacts(
            permit_number=record.permit_number,
            apn=record.site.apn if record.site else None,
            exact_site_address=record.site.address if record.site else None,
        )
        location = _location(record.site)
    elif isinstance(record, PlanningCaseRecord):
        family, identity, title = "planning", record.case_key, record.description
        jurisdiction = record.jurisdiction
        artifacts = _artifacts(
            planning_case_number=record.case_number,
            apn=record.site.apn if record.site else None,
            exact_site_address=record.site.address if record.site else None,
        )
        location = _location(record.site)
    else:
        family, identity, title = "agenda", record.agenda_key, record.title
        jurisdiction = record.jurisdiction
        artifacts = _artifacts(
            apn=record.site.apn if record.site else None,
            exact_site_address=record.site.address if record.site else None,
        )
        location = _location(record.site)
    return InvestigationObservation(
        evidence=_evidence(
            family=family,
            source_name=source.source_name,
            record_id=identity,
            record_type=family,
            at=at,
            jurisdiction=jurisdiction,
            raw={"normalized_source_record": record.model_dump(mode="json")},
            url=str(source.source_url) if source.source_url else None,
        ),
        title=title,
        county=record.county,
        artifacts=artifacts,
        parties=record.entities,
        **location,
    )


def from_document(record: DocumentRecord) -> InvestigationObservation:
    at = record.captured_at or _retained_time(record.provenance)
    return InvestigationObservation(
        evidence=_evidence(
            family="document",
            source_name=record.source_name,
            record_id=record.document_key,
            record_type="document",
            at=at,
            url=str(record.url) if record.url else None,
            raw={"normalized_document": record.model_dump(mode="json")},
            limitations=["Document location and project identity have not been resolved."],
        ),
        title=record.title,
    )


def from_intake(record: UniversalIntakeRecord) -> InvestigationObservation:
    """Reuse retained intake and site resolution while keeping uncertain facts out of anchors."""
    kinds = {
        MaterialFactKind.APN: Artifact.APN,
        MaterialFactKind.ADDRESS: Artifact.EXACT_SITE_ADDRESS,
        MaterialFactKind.SCH_NUMBER: Artifact.CEQA_SCH_NUMBER,
        MaterialFactKind.PERMIT_NUMBER: Artifact.PERMIT_NUMBER,
        MaterialFactKind.PROJECT_TITLE: Artifact.PROJECT_TITLE,
    }
    artifacts: dict[Artifact, list[str]] = {}
    seen: set[tuple[Artifact, str]] = set()
    excluded = 0
    title = None
    for fact in record.extracted_facts:
        if fact.evidence_id != record.evidence.evidence_id:
            raise ValueError("intake fact is not bound to the retained intake evidence")
        if fact.confidence not in {FactConfidence.SOURCE_CLAIMED, FactConfidence.VERIFIED}:
            excluded += 1
            continue
        kind = kinds.get(fact.fact_kind)
        if kind is None:
            continue
        normalized = normalize_artifact_value(kind, fact.value)
        if not normalized or (kind, normalized) in seen:
            continue
        seen.add((kind, normalized))
        artifacts.setdefault(kind, []).append(fact.value)
        if kind is Artifact.PROJECT_TITLE and title is None:
            title = fact.value
    # The existing resolver applies the same source-claim gate. Uncertain facts
    # remain intact in retained evidence and the explicit source limitations.
    resolution = resolve_site_from_intake(record)
    latitude = longitude = None
    if len(resolution.candidates) == 1:
        latitude, longitude = resolution.candidates[0].latitude, resolution.candidates[0].longitude
        if latitude is None or longitude is None:
            latitude = longitude = None
    limitations = list(record.evidence.limitations)
    limitations.extend(fragment.reason for fragment in record.unmapped_fragments)
    if excluded:
        limitations.append(f"{excluded} uncertain/inferred facts excluded from identity anchors.")
    identity = record.record_hints.get("source_record_id") or f"artifact:{record.evidence.sha256}"
    return InvestigationObservation(
        evidence=_evidence(
            family=record.evidence.source_family or "unclassified_intake",
            source_name=record.evidence.source_name,
            record_id=identity,
            record_type="intake",
            at=record.evidence.observed_at,
            jurisdiction=_text(record.source_hints.get("jurisdiction")),
            url=record.evidence.source_url,
            raw={
                "universal_intake": record.to_dict(),
                "retained_input_sha256": record.evidence.sha256,
                "site_resolution_id": resolution.resolution_id,
            },
            limitations=list(dict.fromkeys(limitations)),
        ),
        title=title,
        county=_text(record.source_hints.get("county")),
        artifacts=artifacts,
        latitude=latitude,
        longitude=longitude,
    )


def normalize_retained_record(kind: str, payload: Any) -> InvestigationObservation:
    if kind == "ceqa":
        return from_domain(CeqaRecord.model_validate(payload))
    if kind == "permit":
        return from_domain(PermitRecord.model_validate(payload))
    if kind == "planning":
        return from_domain(PlanningCaseRecord.model_validate(payload))
    if kind == "agenda":
        return from_domain(AgendaItemRecord.model_validate(payload))
    if kind == "document":
        return from_document(DocumentRecord.model_validate(payload))
    if kind == "intake":
        return from_intake(UniversalIntakeRecord.model_validate(payload))
    if kind == "parcel":
        return from_parcel(ParcelCoreRecord.model_validate(payload))
    raise ValueError("unsupported retained source kind")


def from_parcel(record: ParcelCoreRecord) -> InvestigationObservation:
    """Preserve parcel identity and geometry as parcel evidence, not project identity."""
    latitude = longitude = None
    if record.geometry is not None:
        latitude, longitude = record.geometry.centroid_latitude, record.geometry.centroid_longitude
        if latitude is None or longitude is None:
            latitude = longitude = None
    return InvestigationObservation(
        evidence=_evidence(
            family="parcel",
            source_name=record.source_key,
            record_id=record.source_record_id or record.parcel_record_id,
            record_type="parcel",
            at=record.created_at,
            observed_at=record.source_updated_at,
            jurisdiction=record.jurisdiction,
            raw={"parcel_record": record.to_dict()},
        ),
        title=None,
        county=record.county,
        artifacts=_artifacts(apn=record.apn, exact_site_address=record.address),
        latitude=latitude,
        longitude=longitude,
    )
