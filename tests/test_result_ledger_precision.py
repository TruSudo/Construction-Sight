import pytest
from pydantic import ValidationError

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_models import ResultLedgerStatus, ResultShareRecord
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


def test_currency_values_are_limited_to_cents() -> None:
    with pytest.raises(ValidationError, match="at most 2 decimal places"):
        build_result_ledger_record(
            workflow=_workflow(),
            status=ResultLedgerStatus.WON,
            gross_value=100.001,
        )


def test_share_rate_is_limited_to_six_decimal_places() -> None:
    with pytest.raises(ValidationError, match="at most 6 decimal places"):
        ResultShareRecord(
            share_record_id="result-share:precision",
            workflow_id=_workflow().workflow_id,
            gross_value=100.0,
            share_rate=0.1234567,
            share_value=12.35,
        )


def test_share_identity_distinguishes_fifth_decimal_rate() -> None:
    first = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
        share_rate=0.12345,
    )
    second_workflow = _workflow().model_copy(
        update={"workflow_id": "lead-workflow:precision-second"}
    )
    second = build_result_ledger_record(
        workflow=second_workflow,
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
        share_rate=0.12346,
    )

    assert first.share is not None
    assert second.share is not None
    assert first.share.share_record_id != second.share.share_record_id
