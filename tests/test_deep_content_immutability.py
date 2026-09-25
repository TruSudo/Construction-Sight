from __future__ import annotations

import pytest
from pydantic import ValidationError

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveVerification
from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_observation_service import build_parcel_record_observation
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.result_ledger_service import build_result_ledger_record


def _workflow() -> LeadWorkflowRecord:
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:immutability",
        package_id="lead-review:immutability",
        base_candidate_id="candidate:immutability",
        status=LeadWorkflowStatus.READY,
        lead_score=80,
    )


def test_result_ledger_digest_bound_collections_are_immutable() -> None:
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
        share_rate=0.1,
        reasons=["executed agreement"],
    )

    assert ledger.reasons == ("executed agreement",)
    assert ledger.share is not None
    assert ledger.share.notes == ()

    with pytest.raises(ValidationError, match="frozen"):
        setattr(ledger, "reasons", ("changed after digest",))
    with pytest.raises(ValidationError, match="frozen"):
        setattr(ledger.share, "notes", ("changed after digest",))


def test_parcel_observation_retains_recursively_frozen_record() -> None:
    record = ParcelCoreRecord(
        parcel_record_id="parcel:immutability",
        source_key="parcel-source:test",
        apn="12345678",
        normalized_apn="12345678",
        county="San Bernardino",
        limitations=["retained source limitation"],
    )
    observation = build_parcel_record_observation(record)

    assert observation.record.limitations == ("retained source limitation",)
    with pytest.raises(ValidationError, match="frozen"):
        setattr(observation.record, "limitations", ("mutated later",))


def test_live_verification_finding_collection_is_immutable() -> None:
    verification = CeqanetCsvLiveVerification(
        passed=False,
        finding_count=1,
        findings=["retained finding"],
        request_url="https://ceqanet.opr.ca.gov/",
        status_code=403,
        execution_digest="0" * 64,
    )

    assert verification.findings == ("retained finding",)
    with pytest.raises(ValidationError, match="frozen"):
        setattr(verification, "findings", ("rewritten finding",))
