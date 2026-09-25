"""Read-only persisted source-registry projection for the local operator."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.adapters.specs import default_adapter_family_specs
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.models import PublicSource, SourceVerificationResult
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.operator_read_store import read_project_page
from constructionsight.storage.orm import SourceRecord, VerificationRecord

SOURCE_REGISTRY_RESULT_LIMIT = 500
SOURCE_IDENTITY_SCAN_LIMIT = 5_000
SOURCE_ATTRIBUTION_SCAN_LIMIT = 5_000
UNREGISTERED_SOURCE_NAME_RESULT_LIMIT = 100


class OperatorSourceRegistryEntry(BaseModel):
    """One validated public-source registry row plus adapter and verification metadata."""

    source_name: str = Field(min_length=1, max_length=255)
    jurisdiction_name: str = Field(min_length=1, max_length=255)
    county: str = Field(min_length=1, max_length=255)
    state: str = Field(min_length=2, max_length=2)
    source_type: str = Field(min_length=1, max_length=128)
    platform_family: str = Field(min_length=1, max_length=128)
    public_url: str = Field(min_length=1)
    record_categories: list[str]
    search_method: str | None = None
    extraction_difficulty: str = Field(min_length=1, max_length=64)
    update_frequency: str | None = None
    confidence_score: int = Field(ge=0, le=100)
    verification_status: str = Field(min_length=1, max_length=64)
    last_checked_date: date | None = None
    adapter_status: str = Field(min_length=1, max_length=64)
    adapter_live: bool
    adapter_requires_javascript: bool
    adapter_requires_pdf_processing: bool
    latest_verification_present: bool
    latest_verification_checked_at: datetime | None = None
    latest_verification_url_reachable: bool | None = None
    latest_detected_platform_family: str | None = None
    latest_public_search_available: bool | None = None
    latest_login_required: bool | None = None
    latest_verification_confidence_score: int | None = Field(default=None, ge=0, le=100)
    latest_verification_notes: str | None = None
    verification_metadata_consistent: bool | None = None
    attribution_name_unambiguous: bool
    attributed_ceqa_records_in_scan: int = Field(ge=0)
    attributed_permit_records_in_scan: int = Field(ge=0)
    attributed_records_in_scan: int = Field(ge=0)


class OperatorSourceRegistrySnapshot(BaseModel):
    """Bounded local registry presentation with explicit authority limitations."""

    read_only: bool = True
    network_collection_enabled: bool = False
    verification_metadata_is_authority: bool = False
    total: int = Field(ge=0)
    returned: int = Field(ge=0)
    result_limit: int = Field(ge=1)
    truncated: bool
    source_identity_scan_limit: int = Field(ge=1)
    source_identity_rows_scanned: int = Field(ge=0)
    source_identity_scan_truncated: bool
    source_attribution_available: bool
    source_attribution_scan_limit: int = Field(ge=1)
    ceqa_records_total: int = Field(ge=0)
    ceqa_records_scanned: int = Field(ge=0)
    permit_records_total: int = Field(ge=0)
    permit_records_scanned: int = Field(ge=0)
    attribution_scan_truncated: bool
    records_with_registered_source_in_scan: int = Field(ge=0)
    records_without_registered_source_in_scan: int = Field(ge=0)
    ambiguous_registry_source_names: list[str]
    unregistered_source_names_in_scan: list[str]
    unregistered_source_names_truncated: bool
    entries: list[OperatorSourceRegistryEntry]
    limitations: list[str]


def _public_source(row: SourceRecord) -> PublicSource:
    try:
        categories: object = json.loads(row.record_categories_json)
    except json.JSONDecodeError as exc:
        raise ValueError("stored source registry categories are not valid JSON") from exc
    return PublicSource.model_validate(
        {
            "jurisdiction": {
                "name": row.jurisdiction_name,
                "county": row.county,
                "state": row.state,
                "jurisdiction_type": row.jurisdiction_type,
            },
            "source_name": row.source_name,
            "source_type": row.source_type,
            "platform_family": row.platform_family,
            "public_url": row.public_url,
            "record_categories": categories,
            "search_method": row.search_method,
            "extraction_difficulty": row.extraction_difficulty,
            "update_frequency": row.update_frequency,
            "confidence_score": row.confidence_score,
            "verification_status": row.verification_status,
            "provenance_notes": row.provenance_notes,
            "last_checked_date": row.last_checked_date,
        }
    )


def _verification(
    row: VerificationRecord, source: PublicSource
) -> SourceVerificationResult:
    try:
        raw_observations: object = json.loads(row.raw_observations_json)
    except json.JSONDecodeError as exc:
        raise ValueError("stored source verification observations are not valid JSON") from exc
    if not isinstance(raw_observations, dict):
        raise ValueError("stored source verification observations are not an object")
    result = SourceVerificationResult.model_validate(
        {
            "source_name": row.source_name,
            "public_url": row.public_url,
            "checked_at": row.checked_at,
            "url_reachable": row.url_reachable,
            "portal_type_detected": row.portal_type_detected,
            "public_search_available": row.public_search_available,
            "login_required": row.login_required,
            "permit_details_visible": row.permit_details_visible,
            "agenda_packets_visible": row.agenda_packets_visible,
            "pdfs_downloadable": row.pdfs_downloadable,
            "contractor_owner_applicant_fields_visible": (
                row.contractor_owner_applicant_fields_visible
            ),
            "evidence_snapshot_text": row.evidence_snapshot_text,
            "confidence_score": row.confidence_score,
            "notes": row.notes,
            "raw_observations": raw_observations,
        }
    )
    if (
        result.source_name != source.source_name
        or str(result.public_url) != str(source.public_url)
    ):
        raise ValueError("linked source verification identity disagrees with registry row")
    return result


def _expected_registry_status(result: SourceVerificationResult) -> str:
    if result.url_reachable and result.confidence_score >= 60:
        return "verified"
    if result.url_reachable:
        return "partial"
    return "failed"


def _latest_verifications(
    session: Session, source_ids: list[int]
) -> dict[int, VerificationRecord]:
    if not source_ids:
        return {}
    rank = func.row_number().over(
        partition_by=VerificationRecord.source_id,
        order_by=(VerificationRecord.checked_at.desc(), VerificationRecord.id.desc()),
    ).label("source_rank")
    ranked = (
        select(VerificationRecord.id.label("verification_id"), rank)
        .where(VerificationRecord.source_id.in_(source_ids))
        .subquery()
    )
    records = session.scalars(
        select(VerificationRecord)
        .join(ranked, VerificationRecord.id == ranked.c.verification_id)
        .where(ranked.c.source_rank == 1)
    ).all()
    result: dict[int, VerificationRecord] = {}
    for record in records:
        if record.source_id is None or record.source_id in result:
            raise ValueError("latest source verification projection is not unique")
        result[record.source_id] = record
    return result


def _attribution(
    records: list[CeqaRecord | PermitRecord],
    *,
    configured_names: set[str],
    unambiguous_names: set[str],
) -> tuple[Counter[str], int, int, set[str]]:
    counts: Counter[str] = Counter()
    with_registered = 0
    without_registered = 0
    unregistered_names: set[str] = set()
    for record in records:
        names = {item.source_name for item in record.provenance}
        matches = names & unambiguous_names
        if matches:
            with_registered += 1
            for name in matches:
                counts[name] += 1
        else:
            without_registered += 1
        unregistered_names.update(names - configured_names)
    return counts, with_registered, without_registered, unregistered_names


def build_operator_source_registry(session: Session) -> OperatorSourceRegistrySnapshot:
    """Return configured sources plus bounded exact-name record attribution."""

    total = session.scalar(select(func.count(SourceRecord.id))) or 0
    rows = session.scalars(
        select(SourceRecord)
        .order_by(
            SourceRecord.county,
            SourceRecord.jurisdiction_name,
            SourceRecord.source_name,
            SourceRecord.public_url,
            SourceRecord.id,
        )
        .limit(SOURCE_REGISTRY_RESULT_LIMIT)
    ).all()
    sources = [(row, _public_source(row)) for row in rows]
    identity_names = list(
        session.scalars(
            select(SourceRecord.source_name)
            .order_by(SourceRecord.id)
            .limit(SOURCE_IDENTITY_SCAN_LIMIT)
        ).all()
    )
    source_identity_scan_truncated = total > len(identity_names)
    source_name_counts = Counter(identity_names)
    configured_names = (
        set(source_name_counts) if not source_identity_scan_truncated else set()
    )
    unambiguous_names = (
        {
            name for name, count in source_name_counts.items() if count == 1
        }
        if not source_identity_scan_truncated
        else set()
    )
    ambiguous_names = (
        sorted(name for name, count in source_name_counts.items() if count > 1)
        if not source_identity_scan_truncated
        else []
    )

    ceqa_records, ceqa_total = read_project_page(
        session,
        kind="ceqa",
        query="",
        county="",
        limit=SOURCE_ATTRIBUTION_SCAN_LIMIT,
        offset=0,
    )
    permit_records, permit_total = read_project_page(
        session,
        kind="permit",
        query="",
        county="",
        limit=SOURCE_ATTRIBUTION_SCAN_LIMIT,
        offset=0,
    )
    if source_identity_scan_truncated:
        ceqa_counts: Counter[str] = Counter()
        permit_counts: Counter[str] = Counter()
        ceqa_with = ceqa_without = permit_with = permit_without = 0
        unregistered_names: list[str] = []
    else:
        ceqa_counts, ceqa_with, ceqa_without, ceqa_unregistered = _attribution(
            ceqa_records,
            configured_names=configured_names,
            unambiguous_names=unambiguous_names,
        )
        permit_counts, permit_with, permit_without, permit_unregistered = _attribution(
            permit_records,
            configured_names=configured_names,
            unambiguous_names=unambiguous_names,
        )
        unregistered_names = sorted(ceqa_unregistered | permit_unregistered)
    displayed_unregistered = unregistered_names[:UNREGISTERED_SOURCE_NAME_RESULT_LIMIT]

    verifications = _latest_verifications(session, [row.id for row, _ in sources])
    specs = default_adapter_family_specs()
    entries: list[OperatorSourceRegistryEntry] = []
    for row, source in sources:
        spec = specs.get(source.platform_family)
        verification_row = verifications.get(row.id)
        verification = (
            None
            if verification_row is None
            else _verification(verification_row, source)
        )
        metadata_consistent = (
            None
            if verification is None
            else (
                source.verification_status.value == _expected_registry_status(verification)
                and source.confidence_score == verification.confidence_score
                and source.last_checked_date == verification.checked_at.date()
            )
        )
        attributed_ceqa = (
            ceqa_counts[source.source_name]
            if source.source_name in unambiguous_names
            else 0
        )
        attributed_permit = (
            permit_counts[source.source_name]
            if source.source_name in unambiguous_names
            else 0
        )
        entries.append(
            OperatorSourceRegistryEntry(
                source_name=source.source_name,
                jurisdiction_name=source.jurisdiction.name,
                county=source.jurisdiction.county,
                state=source.jurisdiction.state,
                source_type=source.source_type.value,
                platform_family=source.platform_family.value,
                public_url=str(source.public_url),
                record_categories=[category.value for category in source.record_categories],
                search_method=source.search_method,
                extraction_difficulty=source.extraction_difficulty.value,
                update_frequency=source.update_frequency,
                confidence_score=source.confidence_score,
                verification_status=source.verification_status.value,
                last_checked_date=source.last_checked_date,
                adapter_status=spec.status.value if spec is not None else "unknown",
                adapter_live=spec.is_live if spec is not None else False,
                adapter_requires_javascript=(
                    spec.requires_javascript if spec is not None else False
                ),
                adapter_requires_pdf_processing=(
                    spec.requires_pdf_processing if spec is not None else False
                ),
                latest_verification_present=verification is not None,
                latest_verification_checked_at=(
                    verification.checked_at if verification is not None else None
                ),
                latest_verification_url_reachable=(
                    verification.url_reachable if verification is not None else None
                ),
                latest_detected_platform_family=(
                    verification.portal_type_detected.value
                    if verification is not None
                    else None
                ),
                latest_public_search_available=(
                    verification.public_search_available if verification is not None else None
                ),
                latest_login_required=(
                    verification.login_required if verification is not None else None
                ),
                latest_verification_confidence_score=(
                    verification.confidence_score if verification is not None else None
                ),
                latest_verification_notes=(
                    verification.notes if verification is not None else None
                ),
                verification_metadata_consistent=metadata_consistent,
                attribution_name_unambiguous=(
                    source.source_name in unambiguous_names
                ),
                attributed_ceqa_records_in_scan=attributed_ceqa,
                attributed_permit_records_in_scan=attributed_permit,
                attributed_records_in_scan=attributed_ceqa + attributed_permit,
            )
        )
    return OperatorSourceRegistrySnapshot(
        total=total,
        returned=len(entries),
        result_limit=SOURCE_REGISTRY_RESULT_LIMIT,
        truncated=total > len(entries),
        source_identity_scan_limit=SOURCE_IDENTITY_SCAN_LIMIT,
        source_identity_rows_scanned=len(identity_names),
        source_identity_scan_truncated=source_identity_scan_truncated,
        source_attribution_available=not source_identity_scan_truncated,
        source_attribution_scan_limit=SOURCE_ATTRIBUTION_SCAN_LIMIT,
        ceqa_records_total=ceqa_total,
        ceqa_records_scanned=len(ceqa_records),
        permit_records_total=permit_total,
        permit_records_scanned=len(permit_records),
        attribution_scan_truncated=(
            ceqa_total > len(ceqa_records) or permit_total > len(permit_records)
        ),
        records_with_registered_source_in_scan=ceqa_with + permit_with,
        records_without_registered_source_in_scan=ceqa_without + permit_without,
        ambiguous_registry_source_names=ambiguous_names,
        unregistered_source_names_in_scan=displayed_unregistered,
        unregistered_source_names_truncated=(
            len(unregistered_names) > len(displayed_unregistered)
        ),
        entries=entries,
        limitations=[
            (
                "Registry verification state and confidence are stored metadata, not current "
                "proof that a source is reachable or complete."
            ),
            (
                "Latest verification observations are historical retained checks and do not "
                "authorize a new request or recurring collection."
            ),
            (
                "Record attribution uses only exact record-level provenance source_name "
                "matches to one unambiguous configured registry name."
            ),
            (
                "If the bounded source-identity scan is incomplete, attribution is withheld "
                "rather than treating unseen configured sources as unregistered."
            ),
            (
                "Attribution scans are bounded independently for CEQA and permit records; "
                "truncation prevents complete local coverage conclusions."
            ),
            (
                "Adapter status describes implemented software capability; it does not grant "
                "network collection authority."
            ),
            (
                "No registry row or attributed record count establishes complete jurisdiction "
                "coverage, a current active jobsite, or a qualified commercial lead."
            ),
        ],
    )
