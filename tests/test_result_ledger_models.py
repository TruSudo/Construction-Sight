import pytest
from pydantic import ValidationError

from constructionsight.result_ledger_models import (
    ResultLedgerRecord,
    ResultLedgerStatus,
    ResultShareRecord,
    ResultShareStatus,
)


def test_share_record_requires_matching_math() -> None:
    with pytest.raises(ValidationError):
        ResultShareRecord(
            share_record_id="result-share:test",
            workflow_id="lead-workflow:test",
            gross_value=1000.0,
            share_rate=0.1,
            share_value=99.0,
        )


def test_won_ledger_without_gross_value_is_pending() -> None:
    ledger = ResultLedgerRecord(
        ledger_id="result-ledger:test",
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        status=ResultLedgerStatus.WON,
    )

    assert ledger.share_status == ResultShareStatus.PENDING_GROSS_VALUE
    assert ledger.share is None


def test_won_ledger_with_gross_value_without_share_is_pending_share_rate() -> None:
    ledger = ResultLedgerRecord(
        ledger_id="result-ledger:test",
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
    )

    assert ledger.share_status == ResultShareStatus.PENDING_SHARE_RATE
    assert ledger.share is None


def test_share_requires_won_status() -> None:
    share = ResultShareRecord(
        share_record_id="result-share:test",
        workflow_id="lead-workflow:test",
        gross_value=1000.0,
        share_rate=0.1,
        share_value=100.0,
    )

    with pytest.raises(ValidationError):
        ResultLedgerRecord(
            ledger_id="result-ledger:test",
            workflow_id="lead-workflow:test",
            package_id="lead-review:test",
            status=ResultLedgerStatus.LOST,
            share=share,
        )


def test_ledger_serializes() -> None:
    ledger = ResultLedgerRecord(
        ledger_id="result-ledger:test",
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        status=ResultLedgerStatus.LOST,
        reasons=["not a fit"],
    )

    payload = ledger.to_dict()

    assert payload["status"] == "lost"
    assert payload["share_status"] == "not_applicable"
