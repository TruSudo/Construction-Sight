import pytest

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_models import ResultLedgerRecord, ResultLedgerStatus
from constructionsight.result_ledger_service import build_result_ledger_record


def _workflow() -> LeadWorkflowRecord:
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:precision",
        package_id="lead-review:precision",
        base_candidate_id="candidate:precision",
        status=LeadWorkflowStatus.READY,
        lead_score=80,
    )


def test_non_won_result_rejects_monetary_payload() -> None:
    with pytest.raises(ValueError, match="gross_value may be provided only"):
        build_result_ledger_record(
            workflow=_workflow(),
            status=ResultLedgerStatus.LOST,
            gross_value=100.0,
        )


def test_share_rate_requires_gross_value() -> None:
    with pytest.raises(ValueError, match="share_rate requires gross_value"):
        build_result_ledger_record(
            workflow=_workflow(),
            status=ResultLedgerStatus.WON,
            share_rate=0.1,
        )


def test_currency_values_are_limited_to_cents_for_new_writes() -> None:
    with pytest.raises(ValueError, match="at most 2 decimal places"):
        build_result_ledger_record(
            workflow=_workflow(),
            status=ResultLedgerStatus.WON,
            gross_value=100.001,
        )


def test_share_rate_is_limited_to_six_decimal_places_for_new_writes() -> None:
    with pytest.raises(ValueError, match="at most 6 decimal places"):
        build_result_ledger_record(
            workflow=_workflow(),
            status=ResultLedgerStatus.WON,
            gross_value=100.0,
            share_rate=0.1234567,
        )


def test_share_identity_distinguishes_fifth_decimal_rate() -> None:
    first = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
        share_rate=0.12345,
    )
    second = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
        share_rate=0.12346,
    )

    assert first.ledger_id == second.ledger_id
    assert first.share is not None
    assert second.share is not None
    assert first.share.share_record_id != second.share.share_record_id


def test_legacy_non_won_monetary_payload_remains_readable() -> None:
    legacy = ResultLedgerRecord(
        ledger_id="result-ledger:legacy",
        workflow_id=_workflow().workflow_id,
        package_id=_workflow().package_id,
        status=ResultLedgerStatus.LOST,
        gross_value=100.001,
    )

    assert legacy.status == ResultLedgerStatus.LOST
    assert legacy.gross_value == 100.001
