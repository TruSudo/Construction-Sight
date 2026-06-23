"""Deterministic CEQAnet fixture query helpers.

This module is fixture-only. It does not perform live HTTP requests,
submit search forms, download documents, collect result pages, or mutate
persistence. It gives Phase 6 a governed query contract that can later be
reused by a live read-only CEQAnet implementation after access review.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from constructionsight.ceqa_models import CeqaRecord


@dataclass(frozen=True)
class CeqanetFixtureQuery:
    """Conservative filters for already-normalized CEQAnet fixture records."""

    counties: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    lead_agencies: tuple[str, ...] = ()
    text_terms: tuple[str, ...] = ()
    received_from: date | None = None
    received_to: date | None = None
    posted_from: date | None = None
    posted_to: date | None = None
    high_signal_only: bool = False
    limit: int | None = None

    def __post_init__(self) -> None:
        """Reject invalid limit values early."""

        if self.limit is not None and self.limit < 1:
            raise ValueError("CEQAnet fixture query limit must be at least 1 when provided")


@dataclass(frozen=True)
class CeqanetFixtureQueryResult:
    """Auditable result metadata for a fixture query."""

    records: tuple[CeqaRecord, ...]
    source_record_count: int
    matched_record_count: int
    truncated: bool
    query: CeqanetFixtureQuery


def _normalize_text(value: str | None) -> str:
    """Return a stable lowercase text representation for comparisons."""

    if value is None:
        return ""
    return " ".join(value.casefold().split())


def _normalize_terms(values: Iterable[str]) -> tuple[str, ...]:
    """Normalize non-blank query terms while preserving deterministic order."""

    return tuple(term for term in (_normalize_text(value) for value in values) if term)


def _record_search_text(record: CeqaRecord) -> str:
    """Return searchable normalized text for high-level fixture matching."""

    return " ".join(
        value
        for value in (
            _normalize_text(record.title),
            _normalize_text(record.county),
            _normalize_text(record.lead_agency),
            _normalize_text(record.document_type),
            _normalize_text(record.project_location),
            _normalize_text(record.description),
            _normalize_text(record.state_clearinghouse_number),
        )
        if value
    )


def _date_in_range(
    value: date | None,
    *,
    lower_bound: date | None,
    upper_bound: date | None,
) -> bool:
    """Return true when an optional date satisfies optional inclusive bounds."""

    if lower_bound is None and upper_bound is None:
        return True
    if value is None:
        return False
    if lower_bound is not None and value < lower_bound:
        return False
    return upper_bound is None or value <= upper_bound


class CeqanetFixtureQueryService:
    """Filter already-normalized CEQAnet fixture records deterministically."""

    def query(
        self,
        records: Iterable[CeqaRecord],
        query: CeqanetFixtureQuery,
    ) -> CeqanetFixtureQueryResult:
        """Return records matching all supplied fixture-query filters."""

        source_records = tuple(records)
        matched_records = tuple(record for record in source_records if self.matches(record, query))
        truncated = query.limit is not None and len(matched_records) > query.limit
        if query.limit is not None:
            matched_records = matched_records[: query.limit]
        return CeqanetFixtureQueryResult(
            records=matched_records,
            source_record_count=len(source_records),
            matched_record_count=len(matched_records),
            truncated=truncated,
            query=query,
        )

    def matches(self, record: CeqaRecord, query: CeqanetFixtureQuery) -> bool:
        """Return true when one normalized CEQA record satisfies the query."""

        if query.high_signal_only and not record.is_high_signal_document:
            return False
        if not self._matches_any(_normalize_text(record.county), query.counties):
            return False
        if not self._matches_any(_normalize_text(record.document_type), query.document_types):
            return False
        if not self._matches_any(_normalize_text(record.lead_agency), query.lead_agencies):
            return False
        if not _date_in_range(
            record.received_date,
            lower_bound=query.received_from,
            upper_bound=query.received_to,
        ):
            return False
        if not _date_in_range(
            record.posted_date,
            lower_bound=query.posted_from,
            upper_bound=query.posted_to,
        ):
            return False
        terms = _normalize_terms(query.text_terms)
        return not terms or all(term in _record_search_text(record) for term in terms)

    @staticmethod
    def _matches_any(record_value: str, accepted_values: tuple[str, ...]) -> bool:
        """Return true when no filter is set or the normalized value matches one option."""

        accepted = _normalize_terms(accepted_values)
        return not accepted or record_value in accepted
