"""Native lead inspection preserves exact original outcomes without granting authority."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_operator_service import load_persisted_lead_workflow
from constructionsight.lead_workflow_models import LeadWorkflowRecord
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.live_command_center import make_server
from constructionsight.operator_results import MAX_REVISIONS_PER_WORKFLOW
from constructionsight.result_ledger_models import ResultLedgerRecord, ResultLedgerStatus
from constructionsight.result_ledger_service import (
    build_result_ledger_record,
    supersede_result_ledger_record,
)
from constructionsight.storage.database import create_private_database_engine
from constructionsight.storage.lead_workflow_orm import (
    LeadFingerprintRecord,
    LeadReviewPackageRecord,
    ResultLedgerRecordRow,
    ResultShareRecordRow,
)
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_record,
    store_result_ledger_record,
)
from tests.test_bid_proposal_service import _package
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_command_center_live_graph import _ingest


@dataclass(frozen=True)
class NativeLead:
    directory: Path
    investigation_id: str
    source_evidence_id: str
    workflow: LeadWorkflowRecord

    @property
    def database(self) -> Path:
        return self.directory / "investigations.sqlite3"


@contextmanager
def _client(directory: Path) -> Iterator[httpx.Client]:
    server = make_server(snapshot(), 0, directory=directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            yield client
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@contextmanager
def _session(lead: NativeLead) -> Iterator[Session]:
    engine = create_private_database_engine(lead.database, create=False)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def native_lead(tmp_path: Path) -> NativeLead:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    _ingest(directory)
    with _client(directory) as client:
        identity = client.get("/api/investigations").json()["rows"][0]["investigation_id"]
        response = client.get(
            "/api/investigation-lead-preview", params={"investigation_id": identity}
        )
        assert response.status_code == 200, response.text
        preview = response.json()
        retained = client.post(
            "/api/investigation-lead-handoff",
            json={
                "investigation_id": identity,
                "expected_evidence_id": preview["current_evidence_id"],
                "expected_evidence_sha256": preview["current_evidence_sha256"],
                "expected_event_anchor": preview["event_anchor"],
                "reason": "Preserve this source claim for independent manual review.",
                "caller_confirmation": True,
            },
            headers={"Origin": str(client.base_url).rstrip("/")},
        )
        assert retained.status_code == 200, retained.text
    engine = create_private_database_engine(directory / "investigations.sqlite3", create=False)
    try:
        with Session(engine) as session:
            workflow = load_persisted_lead_workflow(session, retained.json()["workflow_id"])
    finally:
        engine.dispose()
    return NativeLead(directory, identity, preview["current_evidence_id"], workflow)


def _correction_history(lead: NativeLead) -> list[ResultLedgerRecord]:
    first = build_result_ledger_record(
        workflow=lead.workflow, status=ResultLedgerStatus.UNKNOWN,
        reasons=["Synthetic original outcome was uncertain"],
    )
    second = supersede_result_ledger_record(
        current=first, status=ResultLedgerStatus.WON,
        correction_reason="Synthetic evidence corrected the original outcome",
        gross_value=1234.56, share_rate=0.1,
        reasons=["Synthetic stored outcome only; no award or contract verified"],
    )
    third = supersede_result_ledger_record(
        current=second, status=ResultLedgerStatus.LOST,
        correction_reason="Synthetic later correction withdrew the successful outcome",
        reasons=["Earlier calculated share is superseded, never a payment receipt"],
    )
    records = [first, second, third]
    with _session(lead) as session, session.begin():
        for record in records:
            store_result_ledger_record(session, record)
    return records


def _only_row(client: httpx.Client) -> dict[str, Any]:
    response = client.get("/api/investigation-lead-workflows")
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 1
    assert page["has_more"] is False
    assert page["read_only"] is True
    assert page["commercial_authority_granted"] is False
    assert len(page["rows"]) == 1
    return page["rows"][0]


def _assert_no_authority(row: dict[str, Any]) -> None:
    for field in ("commercial_authority_granted", "outreach_authorized", "bid_authorized"):
        assert row[field] is False
    for field in (
        "award_verified", "contract_verified", "share_entitlement_verified",
        "payment_received_verified",
    ):
        assert row["historical_result"][field] is False


def test_native_lead_without_result_does_not_borrow_another_workflows_money(
    native_lead: NativeLead,
) -> None:
    package = _package().model_copy(update={
        "package_id": "lead-review:unrelated-result",
        "base_candidate_id": "candidate:unrelated-result",
    })
    unrelated = create_lead_workflow(package=package)
    result = build_result_ledger_record(
        workflow=unrelated, status=ResultLedgerStatus.WON,
        gross_value=87654.32, share_rate=0.08,
    )
    with _session(native_lead) as session, session.begin():
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, unrelated)
        store_result_ledger_record(session, result)
    before = native_lead.database.read_bytes()
    with _client(native_lead.directory) as client:
        row = _only_row(client)
        outcome = row["historical_result"]
        assert outcome["workflow_id"] == native_lead.workflow.workflow_id
        assert outcome["package_id"] == native_lead.workflow.package_id
        assert outcome["money_unit_encoding"] == "decimal_integer_string"
        assert outcome["has_retained_outcome"] is False
        assert outcome["history_integrity_validated"] is False
        assert outcome["revision_count"] == 0
        assert outcome["revision_history"] == []
        assert outcome["current_revision"] is None
        assert unrelated.workflow_id not in json.dumps(row)
        assert result.ledger_id not in json.dumps(row)
        _assert_no_authority(row)
    assert native_lead.database.read_bytes() == before


def test_native_lead_result_corrections_keep_exact_history_across_source_drift_and_restart(
    native_lead: NativeLead,
) -> None:
    records = _correction_history(native_lead)
    before = native_lead.database.read_bytes()
    with _client(native_lead.directory) as client:
        row = _only_row(client)
        outcome = row["historical_result"]
        assert outcome["workflow_id"] == native_lead.workflow.workflow_id
        assert outcome["package_id"] == native_lead.workflow.package_id
        assert outcome["money_unit_encoding"] == "decimal_integer_string"
        assert outcome["has_retained_outcome"] is True
        assert outcome["history_integrity_validated"] is True
        assert outcome["revision_count"] == 3
        assert outcome["latest_revision_only_is_current"] is True
        assert outcome["past_revisions_must_not_be_summed"] is True
        revisions = outcome["revision_history"]
        assert [revision["revision"] for revision in revisions] == [1, 2, 3]
        assert [revision["status"] for revision in revisions] == ["unknown", "won", "lost"]
        assert [revision["ledger_id"] for revision in revisions] == [
            record.ledger_id for record in records
        ]
        assert [revision["content_digest"] for revision in revisions] == [
            record.content_digest for record in records
        ]
        assert [revision["supersedes_ledger_id"] for revision in revisions] == [
            None, records[0].ledger_id, records[1].ledger_id,
        ]
        assert [revision["correction_reason"] for revision in revisions] == [
            record.correction_reason for record in records
        ]
        won = revisions[1]
        assert won["gross_value_minor"] == "123456"
        assert won["share_rate_ppm"] == 100000
        assert won["calculated_share_minor"] == "12346"
        assert records[1].share is not None
        assert won["share_record_id"] == records[1].share.share_record_id
        assert won["reasons"] == list(records[1].reasons)
        assert won["limitations"] == list(records[1].limitations)
        current = outcome["current_revision"]
        assert current == revisions[-1]
        assert current["gross_value_minor"] is None
        assert current["calculated_share_minor"] is None
        assert current["share_status"] == "not_applicable"
        assert row["source_evidence_state"] == "current_source_observation"
        assert row["canonical_investigation_id"] == native_lead.investigation_id
        assert row["workflow_status"] == native_lead.workflow.status.value
        _assert_no_authority(row)
        for revision in revisions:
            assert revision["share_entitlement_verified"] is False
            assert revision["payment_received_verified"] is False
    assert native_lead.database.read_bytes() == before

    _ingest(native_lead.directory, "Synthetic source revised after historical result correction")
    changed = native_lead.database.read_bytes()
    # A fresh server reopens the persisted workflow after the worker commits.
    with _client(native_lead.directory) as client:
        after = _only_row(client)
        assert after["canonical_investigation_id"] == native_lead.investigation_id
        assert after["workflow_id"] == native_lead.workflow.workflow_id
        assert after["original_source_evidence_id"] == native_lead.source_evidence_id
        assert after["current_source_evidence_id"] != native_lead.source_evidence_id
        assert after["source_evidence_state"] == "source_revision_requires_review"
        assert after["historical_result"] == outcome
        assert after["workflow_status"] == native_lead.workflow.status.value
        _assert_no_authority(after)
    assert native_lead.database.read_bytes() == changed


def test_native_lead_exact_money_survives_javascript_integer_boundary(
    native_lead: NativeLead,
) -> None:
    record = build_result_ledger_record(
        workflow=native_lead.workflow, status=ResultLedgerStatus.WON,
        gross_value=90071992547410.03, share_rate=1.0,
    )
    with _session(native_lead) as session, session.begin():
        store_result_ledger_record(session, record)
    with _client(native_lead.directory) as client:
        row = _only_row(client)
        outcome = row["historical_result"]
        assert outcome["money_unit_encoding"] == "decimal_integer_string"
        current = outcome["current_revision"]
        assert current["gross_value_minor"] == "9007199254741003"
        assert current["calculated_share_minor"] == "9007199254741003"
        assert current["share_rate_ppm"] == 1000000
        assert current["content_digest"] == record.content_digest
        _assert_no_authority(row)


@pytest.mark.parametrize("corruption", [
    "superseded_share", "exact_money_index", "content_digest", "package_lineage",
    "fingerprint_index", "fingerprint_payload", "review_candidate", "cross_workflow",
])
def test_native_lead_results_fail_closed_on_history_or_identity_corruption(
    native_lead: NativeLead, corruption: str,
) -> None:
    records = _correction_history(native_lead)
    with _session(native_lead) as session, session.begin():
        if corruption == "superseded_share":
            assert records[1].share is not None
            share = session.scalar(select(ResultShareRecordRow).where(
                ResultShareRecordRow.share_record_id == records[1].share.share_record_id
            ))
            assert share is not None
            share.share_value_minor = 99999
        elif corruption in {"exact_money_index", "content_digest", "cross_workflow"}:
            selected = records[1] if corruption == "exact_money_index" else records[0]
            ledger = session.scalar(select(ResultLedgerRecordRow).where(
                ResultLedgerRecordRow.ledger_id == selected.ledger_id
            ))
            assert ledger is not None
            if corruption == "exact_money_index":
                ledger.gross_value_minor = 123455
            else:
                payload = json.loads(ledger.payload_json)
                if corruption == "content_digest":
                    payload["reasons"] = ["Changed retained outcome without rebinding digest"]
                else:
                    payload["workflow_id"] = "workflow:unrelated-contamination"
                    payload["content_digest"] = None
                    payload = ResultLedgerRecord.model_validate(payload).to_dict()
                ledger.payload_json = json.dumps(payload)
        elif corruption == "package_lineage":
            # A fully coherent alternate package must still fail workflow binding.
            for ledger in session.scalars(select(ResultLedgerRecordRow)):
                payload = json.loads(ledger.payload_json)
                payload["package_id"] = "lead-review:unrelated-package"
                payload["content_digest"] = None
                ledger.package_id = payload["package_id"]
                ledger.payload_json = json.dumps(
                    ResultLedgerRecord.model_validate(payload).to_dict()
                )
        elif corruption.startswith("fingerprint_"):
            fingerprint = session.scalar(select(LeadFingerprintRecord))
            assert fingerprint is not None
            if corruption == "fingerprint_index":
                fingerprint.base_candidate_id = "candidate:unrelated-index"
            else:
                payload = json.loads(fingerprint.payload_json)
                payload["base_candidate_id"] = "candidate:unrelated-payload"
                fingerprint.payload_json = json.dumps(payload)
        else:
            review = session.scalar(select(LeadReviewPackageRecord).where(
                LeadReviewPackageRecord.package_id == native_lead.workflow.package_id
            ))
            assert review is not None
            payload = json.loads(review.payload_json)
            payload["base_candidate_id"] = "candidate:unrelated-review"
            review.base_candidate_id = payload["base_candidate_id"]
            review.payload_json = json.dumps(payload)
    before = native_lead.database.read_bytes()
    with _client(native_lead.directory) as client:
        response = client.get("/api/investigation-lead-workflows")
        assert response.status_code == 409, response.text
        assert "historical_result" not in response.text
    assert native_lead.database.read_bytes() == before


def test_native_lead_history_limit_never_silently_selects_a_partial_current_result(
    native_lead: NativeLead,
) -> None:
    current = build_result_ledger_record(
        workflow=native_lead.workflow, status=ResultLedgerStatus.UNKNOWN,
    )
    with _session(native_lead) as session, session.begin():
        store_result_ledger_record(session, current)
        for revision in range(2, MAX_REVISIONS_PER_WORKFLOW + 1):
            current = supersede_result_ledger_record(
                current=current, status=ResultLedgerStatus.UNKNOWN,
                correction_reason=f"Synthetic retained correction {revision}",
            )
            store_result_ledger_record(session, current)
    with _client(native_lead.directory) as client:
        outcome = _only_row(client)["historical_result"]
        assert outcome["revision_count"] == MAX_REVISIONS_PER_WORKFLOW
        assert len(outcome["revision_history"]) == MAX_REVISIONS_PER_WORKFLOW
        assert outcome["current_revision"]["ledger_id"] == current.ledger_id
        assert outcome["current_revision"]["revision"] == MAX_REVISIONS_PER_WORKFLOW
    with _session(native_lead) as session, session.begin():
        current = supersede_result_ledger_record(
            current=current, status=ResultLedgerStatus.UNKNOWN,
            correction_reason="Synthetic correction exceeds complete inspection limit",
        )
        store_result_ledger_record(session, current)
    before = native_lead.database.read_bytes()
    with _client(native_lead.directory) as client:
        response = client.get("/api/investigation-lead-workflows")
        assert response.status_code == 409, response.text
        assert "inspection limit" in response.text
        assert "historical_result" not in response.text
    assert native_lead.database.read_bytes() == before
