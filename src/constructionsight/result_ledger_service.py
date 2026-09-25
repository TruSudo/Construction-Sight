"""Result ledger service."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from constructionsight.lead_workflow_models import LeadWorkflowRecord
from constructionsight.result_ledger_models import (
    ResultLedgerRecord,
    ResultLedgerStatus,
    ResultShareRecord,
    ResultShareStatus,
)


def build_result_ledger_record(
    *,
    workflow: LeadWorkflowRecord,
    status: ResultLedgerStatus,
    decided_date: date | None = None,
    gross_value: float | None = None,
    share_rate: float | None = None,
    reasons: list[str] | None = None,
) -> ResultLedgerRecord:
    """Build the root immutable result ledger revision for a workflow."""

    return _build_revision(
        workflow_id=workflow.workflow_id,
        package_id=workflow.package_id,
        revision=1,
        supersedes_ledger_id=None,
        correction_reason=None,
        status=status,
        decided_date=decided_date,
        gross_value=gross_value,
        share_rate=share_rate,
        reasons=reasons,
    )


def supersede_result_ledger_record(
    *,
    current: ResultLedgerRecord,
    status: ResultLedgerStatus,
    correction_reason: str,
    decided_date: date | None = None,
    gross_value: float | None = None,
    share_rate: float | None = None,
    reasons: list[str] | None = None,
) -> ResultLedgerRecord:
    """Append one authoritative revision without mutating the prior result."""

    if not correction_reason.strip():
        raise ValueError("correction_reason must not be blank")
    return _build_revision(
        workflow_id=current.workflow_id,
        package_id=current.package_id,
        revision=current.revision + 1,
        supersedes_ledger_id=current.ledger_id,
        correction_reason=correction_reason.strip(),
        status=status,
        decided_date=decided_date,
        gross_value=gross_value,
        share_rate=share_rate,
        reasons=reasons,
    )


def validate_result_ledger_history(
    records: Iterable[ResultLedgerRecord],
) -> ResultLedgerRecord:
    """Validate one linear append-only history and return its authoritative tip."""

    ordered = sorted(records, key=lambda record: record.revision)
    if not ordered:
        raise ValueError("result ledger history must contain at least one record")
    workflow_ids = {record.workflow_id for record in ordered}
    package_ids = {record.package_id for record in ordered}
    if len(workflow_ids) != 1 or len(package_ids) != 1:
        raise ValueError("result ledger history must belong to one workflow and package")
    ledger_ids = [record.ledger_id for record in ordered]
    if len(ledger_ids) != len(set(ledger_ids)):
        raise ValueError("result ledger history contains duplicate ledger ids")
    revisions = [record.revision for record in ordered]
    if revisions != list(range(1, len(ordered) + 1)):
        raise ValueError("result ledger history revisions must be contiguous from one")
    for record in ordered:
        record.assert_content_digest()
    for index, record in enumerate(ordered):
        if index == 0:
            if record.supersedes_ledger_id is not None:
                raise ValueError("root result ledger revision cannot supersede another ledger")
            continue
        predecessor = ordered[index - 1]
        if record.supersedes_ledger_id != predecessor.ledger_id:
            raise ValueError("result ledger history must form one unbranched supersession chain")
    return ordered[-1]


def _build_revision(
    *,
    workflow_id: str,
    package_id: str,
    revision: int,
    supersedes_ledger_id: str | None,
    correction_reason: str | None,
    status: ResultLedgerStatus,
    decided_date: date | None,
    gross_value: float | None,
    share_rate: float | None,
    reasons: list[str] | None,
) -> ResultLedgerRecord:
    """Build one internally consistent immutable ledger revision."""

    if status != ResultLedgerStatus.WON:
        if gross_value is not None:
            raise ValueError("gross_value may be provided only for won results")
        if share_rate is not None:
            raise ValueError("share_rate may be provided only for won results")
    if status == ResultLedgerStatus.WON and gross_value is None and share_rate is not None:
        raise ValueError("share_rate requires gross_value")
    normalized_gross_value = gross_value
    normalized_share_rate = share_rate
    if gross_value is not None:
        normalized_gross_value = money_minor_units_to_float(
            money_minor_units(gross_value, field_name="gross_value")
        )
    if share_rate is not None:
        normalized_share_rate = share_rate_ppm_to_float(
            share_rate_ppm_units(share_rate, field_name="share_rate")
        )

    share = None
    share_status = ResultShareStatus.NOT_APPLICABLE
    limitations: list[str] = []
    ledger_id = _ledger_id(workflow_id, status, revision)
    if status == ResultLedgerStatus.WON:
        if normalized_gross_value is None:
            share_status = ResultShareStatus.PENDING_GROSS_VALUE
            limitations.append("gross value is missing")
        elif normalized_share_rate is None:
            share_status = ResultShareStatus.PENDING_SHARE_RATE
            limitations.append("share rate is missing")
        else:
            share_status = ResultShareStatus.CALCULATED
            share = _share_record(
                ledger_id,
                workflow_id,
                normalized_gross_value,
                normalized_share_rate,
            )
    return ResultLedgerRecord(
        ledger_id=ledger_id,
        workflow_id=workflow_id,
        package_id=package_id,
        revision=revision,
        supersedes_ledger_id=supersedes_ledger_id,
        correction_reason=correction_reason,
        status=status,
        decided_date=decided_date,
        gross_value=normalized_gross_value,
        share_status=share_status,
        share=share,
        reasons=tuple(reasons or ()),
        limitations=tuple(limitations),
    )


def _share_record(
    ledger_id: str,
    workflow_id: str,
    gross_value: float,
    share_rate: float,
) -> ResultShareRecord:
    """Build a calculated share record bound to one ledger revision."""

    gross_minor = money_minor_units(gross_value, field_name="gross_value")
    rate_ppm = share_rate_ppm_units(share_rate, field_name="share_rate")
    share_minor = calculate_share_minor_units(gross_minor, rate_ppm)
    return ResultShareRecord(
        share_record_id=_share_id(ledger_id, gross_value, share_rate),
        workflow_id=workflow_id,
        gross_value=money_minor_units_to_float(gross_minor),
        share_rate=share_rate_ppm_to_float(rate_ppm),
        share_value=money_minor_units_to_float(share_minor),
    )


def _ledger_id(workflow_id: str, status: ResultLedgerStatus, revision: int) -> str:
    """Build deterministic revision identity while preserving root-id compatibility."""

    values = [workflow_id, status.value]
    if revision > 1:
        values.append(str(revision))
    return f"result-ledger:{_short_hash('|'.join(values))}"


def _share_id(ledger_id: str, gross_value: float, share_rate: float) -> str:
    """Build deterministic share identity from exact monetary/rate units."""

    gross_minor = money_minor_units(gross_value, field_name="gross_value")
    rate_ppm = share_rate_ppm_units(share_rate, field_name="share_rate")
    basis = "|".join([ledger_id, str(gross_minor), str(rate_ppm)])
    return f"result-share:{_short_hash(basis)}"


def _bounded_decimal_units(
    value: float | int | Decimal | str,
    *,
    scale: int,
    maximum_places: int,
    field_name: str,
    maximum_value: Decimal | None = None,
) -> int:
    """Return an exact scaled integer without binary-float arithmetic."""

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite decimal value")
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    if not decimal_value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if decimal_value < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    if maximum_value is not None and decimal_value > maximum_value:
        raise ValueError(f"{field_name} must not exceed {maximum_value}")
    exponent = decimal_value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError(f"{field_name} must be finite")
    decimal_places = max(0, -exponent)
    if decimal_places > maximum_places:
        raise ValueError(
            f"{field_name} must use at most {maximum_places} decimal places"
        )
    scaled = decimal_value * scale
    integral = scaled.to_integral_value(rounding=ROUND_HALF_EVEN)
    if scaled != integral:
        raise ValueError(
            f"{field_name} cannot be represented exactly at the governed scale"
        )
    return int(integral)


def money_minor_units(
    value: float | int | Decimal | str,
    *,
    field_name: str = "money",
) -> int:
    """Return exact currency minor units at scale two."""

    return _bounded_decimal_units(
        value,
        scale=100,
        maximum_places=2,
        field_name=field_name,
    )


def share_rate_ppm_units(
    value: float | int | Decimal | str,
    *,
    field_name: str = "share_rate",
) -> int:
    """Return an exact share rate in millionths at scale six."""

    return _bounded_decimal_units(
        value,
        scale=1_000_000,
        maximum_places=6,
        field_name=field_name,
        maximum_value=Decimal("1"),
    )


def calculate_share_minor_units(gross_minor: int, rate_ppm: int) -> int:
    """Calculate exact share cents using explicit round-half-even doctrine."""

    if gross_minor < 0 or rate_ppm < 0 or rate_ppm > 1_000_000:
        raise ValueError("monetary units and share-rate units are outside governed bounds")
    numerator = gross_minor * rate_ppm
    denominator = 1_000_000
    quotient, remainder = divmod(numerator, denominator)
    doubled = remainder * 2
    if doubled > denominator or (doubled == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def money_minor_units_to_float(value: int) -> float:
    """Return the legacy display projection for exact minor units."""

    return float(Decimal(value) / Decimal(100))


def share_rate_ppm_to_float(value: int) -> float:
    """Return the legacy display projection for an exact millionth-rate value."""

    return float(Decimal(value) / Decimal(1_000_000))


def _short_hash(value: str) -> str:
    """Return short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
