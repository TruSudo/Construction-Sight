from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_models import ResultLedgerStatus, ResultShareStatus
from constructionsight.result_ledger_service import build_result_ledger_record


def _workflow() -> LeadWorkflowRecord:
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        status=LeadWorkflowStatus.READY,
        lead_score=80,
    )


def test_build_result_ledger_record_with_share() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
        share_rate=0.1,
    )

    assert ledger.status == ResultLedgerStatus.WON
    assert ledger.share_status == ResultShareStatus.CALCULATED
    assert ledger.share is not None
    assert ledger.share.share_value == 100.0
    assert ledger.limitations == []


def test_build_result_ledger_record_missing_share_rate() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
    )

    assert ledger.status == ResultLedgerStatus.WON
    assert ledger.share_status == ResultShareStatus.PENDING_SHARE_RATE
    assert ledger.share is None
    assert ledger.limitations == ["share rate is missing"]


def test_build_result_ledger_record_missing_gross_value() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
    )

    assert ledger.status == ResultLedgerStatus.WON
    assert ledger.share_status == ResultShareStatus.PENDING_GROSS_VALUE
    assert ledger.gross_value is None
    assert ledger.share is None
    assert ledger.limitations == ["gross value is missing"]


def test_build_result_ledger_record_for_lost_result() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.LOST,
        reasons=["not selected"],
    )

    assert ledger.status == ResultLedgerStatus.LOST
    assert ledger.share_status == ResultShareStatus.NOT_APPLICABLE
    assert ledger.gross_value is None
    assert ledger.reasons == ["not selected"]
