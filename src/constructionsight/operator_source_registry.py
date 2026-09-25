"""Read-only persisted source-registry projection for the local operator."""

from __future__ import annotations

import json
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.adapters.specs import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.storage.orm import SourceRecord

SOURCE_REGISTRY_RESULT_LIMIT = 500


class OperatorSourceRegistryEntry(BaseModel):
    """One validated public-source registry row plus adapter capability metadata."""

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


class OperatorSourceRegistrySnapshot(BaseModel):
    """Bounded local registry presentation with explicit authority limitations."""

    read_only: bool = True
    network_collection_enabled: bool = False
    verification_metadata_is_authority: bool = False
    total: int = Field(ge=0)
    returned: int = Field(ge=0)
    result_limit: int = Field(ge=1)
    truncated: bool
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


def build_operator_source_registry(session: Session) -> OperatorSourceRegistrySnapshot:
    """Return a bounded validated view of stored public-source configuration."""

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
    specs = default_adapter_family_specs()
    entries: list[OperatorSourceRegistryEntry] = []
    for row in rows:
        source = _public_source(row)
        spec = specs.get(source.platform_family)
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
            )
        )
    return OperatorSourceRegistrySnapshot(
        total=total,
        returned=len(entries),
        result_limit=SOURCE_REGISTRY_RESULT_LIMIT,
        truncated=total > len(entries),
        entries=entries,
        limitations=[
            (
                "Registry verification state and confidence are stored metadata, not current "
                "proof that a source is reachable or complete."
            ),
            (
                "Adapter status describes implemented software capability; it does not grant "
                "network collection authority."
            ),
            (
                "No registry row is evidence that all permits or projects in a jurisdiction "
                "have been acquired."
            ),
        ],
    )
