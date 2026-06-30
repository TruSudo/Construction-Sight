import pytest
from pydantic import ValidationError

from constructionsight.result_ledger_models import (
    ResultLedgerRecord,
    ResultLedgerStatus,
    ResultShareRecord,
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


def test_won_ledger_requires_gross_value() -> None:
    with pytest.raises(ValidationError):
        ResultLedgerRecord(
            ledger_id="result-ledger:test",
            workflow_id="lead-workflow:test",
            package_id="lead-review:test",
            status=ResultLedgerStatus.WON,
        )


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

    assert ledger.to_dict()["status"] == "lost"
