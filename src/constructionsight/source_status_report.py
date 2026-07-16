"""Source and adapter status reporting."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from constructionsight.adapters.specs import AdapterFamilySpec, AdapterImplementationStatus
from constructionsight.models import PlatformFamily, PublicSource, VerificationStatus


@dataclass(frozen=True)
class SourceStatusRow:
    """One source status report row."""

    source_name: str
    jurisdiction_name: str
    platform_family: str
    verification_status: str
    adapter_status: str
    status_level: str
    can_use_as_verified_source: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe row payload."""

        return asdict(self)


@dataclass(frozen=True)
class SourceStatusReport:
    """Aggregated source status report."""

    source_count: int
    status_counts: dict[str, int]
    verification_counts: dict[str, int]
    adapter_counts: dict[str, int]
    verified_source_count: int
    rows: list[SourceStatusRow]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report payload."""

        return {
            "source_count": self.source_count,
            "status_counts": self.status_counts,
            "verification_counts": self.verification_counts,
            "adapter_counts": self.adapter_counts,
            "verified_source_count": self.verified_source_count,
            "rows": [row.to_dict() for row in self.rows],
        }


def build_source_status_report(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
) -> SourceStatusReport:
    """Build source status rows from source registry records and adapter specs."""

    rows = [_row_for_source(source, adapter_specs) for source in sources]
    return SourceStatusReport(
        source_count=len(rows),
        status_counts=dict(Counter(row.status_level for row in rows)),
        verification_counts=dict(Counter(row.verification_status for row in rows)),
        adapter_counts=dict(Counter(row.adapter_status for row in rows)),
        verified_source_count=sum(1 for row in rows if row.can_use_as_verified_source),
        rows=rows,
    )


def _row_for_source(
    source: PublicSource,
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
) -> SourceStatusRow:
    """Build one source status row."""

    spec = adapter_specs.get(source.platform_family)
    adapter_status = (
        spec.status if spec is not None else AdapterImplementationStatus.PLACEHOLDER
    )
    status_level, reason = _status_level(source.verification_status, adapter_status)
    can_use_as_verified_source = (
        source.verification_status == VerificationStatus.VERIFIED
        and adapter_status
        in {
            AdapterImplementationStatus.LIVE_READ_ONLY,
            AdapterImplementationStatus.PRODUCTION_READY,
        }
    )
    return SourceStatusRow(
        source_name=source.source_name,
        jurisdiction_name=source.jurisdiction.name,
        platform_family=source.platform_family.value,
        verification_status=source.verification_status.value,
        adapter_status=adapter_status.value,
        status_level=status_level,
        can_use_as_verified_source=can_use_as_verified_source,
        reason=reason,
    )


def _status_level(
    verification_status: VerificationStatus,
    adapter_status: AdapterImplementationStatus,
) -> tuple[str, str]:
    """Return source status level and reason."""

    if verification_status == VerificationStatus.UNVERIFIED:
        return ("seed_only", "source record is not verified")
    if verification_status in {VerificationStatus.FAILED, VerificationStatus.BLOCKED}:
        return ("not_usable", "source verification did not establish usable status")
    if verification_status == VerificationStatus.PARTIAL:
        return ("partial_verification", "source verification is partial")
    if adapter_status == AdapterImplementationStatus.PLACEHOLDER:
        return ("verified_source_placeholder_adapter", "adapter is placeholder-only")
    if adapter_status == AdapterImplementationStatus.CONTRACT_READY:
        return ("contract_ready_not_live", "adapter contract exists")
    if adapter_status == AdapterImplementationStatus.LIVE_READ_ONLY:
        return ("verified_live_read_only", "source and adapter are read-only ready")
    return ("verified_production_ready", "source and adapter are production ready")
