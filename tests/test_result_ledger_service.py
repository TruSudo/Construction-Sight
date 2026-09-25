import pytest

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_models import (
    ResultLedgerRecord,
    ResultLedgerStatus,
    ResultShareStatus,
)
from constructionsight.result_ledger_service import (
    build_result_ledger_record,
    supersede_result_ledger_record,
    validate_result_ledger_history,
)


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
    assert ledger.revision == 1
    assert ledger.supersedes_ledger_id is None
    assert ledger.share_status == ResultShareStatus.CALCULATED
    assert ledger.share is not None
    assert ledger.share.share_value == 100.0
    assert ledger.limitations == ()


def test_build_result_ledger_record_missing_share_rate() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
    )

    assert ledger.status == ResultLedgerStatus.WON
    assert ledger.share_status == ResultShareStatus.PENDING_SHARE_RATE
    assert ledger.share is None
    assert ledger.limitations == ("share rate is missing",)


def test_build_result_ledger_record_missing_gross_value() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
    )

    assert ledger.status == ResultLedgerStatus.WON
    assert ledger.share_status == ResultShareStatus.PENDING_GROSS_VALUE
    assert ledger.gross_value is None
    assert ledger.share is None
    assert ledger.limitations == ("gross value is missing",)


def test_build_result_ledger_record_for_lost_result() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.LOST,
        reasons=["not selected"],
    )

    assert ledger.status == ResultLedgerStatus.LOST
    assert ledger.share_status == ResultShareStatus.NOT_APPLICABLE
    assert ledger.gross_value is None
    assert ledger.reasons == ("not selected",)


def test_supersede_result_ledger_record_creates_linear_revision() -> None:
    original = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.UNKNOWN,
        reasons=["outcome not yet confirmed"],
    )

    corrected = supersede_result_ledger_record(
        current=original,
        status=ResultLedgerStatus.WON,
        correction_reason="signed contract received",
        decided_date=None,
        gross_value=2500.0,
        share_rate=0.1,
        reasons=["award confirmed by executed agreement"],
    )

    assert corrected.revision == 2
    assert corrected.supersedes_ledger_id == original.ledger_id
    assert corrected.correction_reason == "signed contract received"
    assert corrected.ledger_id != original.ledger_id
    assert corrected.share is not None
    assert validate_result_ledger_history([corrected, original]) == corrected


def test_supersede_result_ledger_record_rejects_blank_reason() -> None:
    original = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.UNKNOWN,
    )

    with pytest.raises(ValueError, match="correction_reason must not be blank"):
        supersede_result_ledger_record(
            current=original,
            status=ResultLedgerStatus.LOST,
            correction_reason="   ",
        )


def test_validate_result_ledger_history_rejects_branch() -> None:
    original = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.UNKNOWN,
    )
    second = supersede_result_ledger_record(
        current=original,
        status=ResultLedgerStatus.LOST,
        correction_reason="first correction",
    )
    third = supersede_result_ledger_record(
        current=second,
        status=ResultLedgerStatus.WON,
        correction_reason="second correction",
        gross_value=1000.0,
        share_rate=0.1,
    )
    payload = third.model_dump(mode="python")
    payload["supersedes_ledger_id"] = original.ledger_id
    payload["content_digest"] = None
    branched = ResultLedgerRecord.model_validate(payload)

    with pytest.raises(ValueError, match="unbranched supersession chain"):
        validate_result_ledger_history([original, second, branched])


def test_validate_result_ledger_history_rejects_revision_gap() -> None:
    original = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.UNKNOWN,
    )
    second = supersede_result_ledger_record(
        current=original,
        status=ResultLedgerStatus.LOST,
        correction_reason="correction",
    )
    payload = second.model_dump(mode="python")
    payload["revision"] = 3
    payload["content_digest"] = None
    gapped = ResultLedgerRecord.model_validate(payload)

    with pytest.raises(ValueError, match="contiguous from one"):
        validate_result_ledger_history([original, gapped])


def test_materially_different_results_have_distinct_content_digests() -> None:
    first = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.LOST,
        reasons=["not selected"],
    )
    second = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.LOST,
        reasons=["budget cancelled"],
    )

    assert first.ledger_id == second.ledger_id
    assert first.content_digest != second.content_digest


def test_content_digest_rejects_post_validation_material_mutation() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.LOST,
        reasons=["not selected"],
    )
    tampered = ledger.model_copy(update={"reasons": ["changed later"]})

    with pytest.raises(ValueError, match="material content changed"):
        tampered.to_dict()
