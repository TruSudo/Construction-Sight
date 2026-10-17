"""Historical financial, authority and retained-evidence guarantees at runtime boundaries."""

from __future__ import annotations

import json
import sqlite3

import pytest
from sqlalchemy import select

from constructionsight import command_center_commercial as commercial
from constructionsight import data_folder
from constructionsight.command_center_graph import graph_view
from constructionsight.intelligence import EntityIdentity, EntityType, EvidenceRecord
from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.live_command_center import projection
from constructionsight.operator_services.result_authority_apply_service import (
    apply_authorized_authoritative_result,
)
from constructionsight.result_authority_service import (
    ResultAuthorityError,
    apply_authoritative_result,
)
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.result_ledger_service import build_result_ledger_record, money_minor_units
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_orm import IntelligenceEvidenceRecord
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_lead_workflow_record
from constructionsight.storage.result_authority_orm import (
    ResultAuthorityEventRow,
    ResultAuthorityHeadRow,
)
from tests.test_command_center_commercial import payload
from tests.test_command_center_state import snapshot
from tests.test_investigation_multisource_acceptance import retained_inputs


def _won_contract(directory, gross="19.99", percent="7.5"):
    lead = projection(snapshot(), directory)["rows"][0]
    bid = commercial.save_bid(directory, lead, payload(status="won", contract_value=gross))
    agreement = commercial.contract(
        directory,
        {
            "bid_id": bid["id"],
            "partner": "Synthetic partner",
            "percent": percent,
            "terms": "Synthetic reviewed agreement",
        },
    )
    return lead, bid, agreement


@pytest.mark.parametrize(
    "gross,percent,expected",
    [
        ("0.01", "50", 0),
        ("0.03", "50", 2),
        ("19.99", "7.5", 150),
    ],
)
def test_native_and_preserved_ledger_apply_identical_exact_rounding(
    tmp_path, gross, percent, expected
):
    from decimal import Decimal

    _, _, agreement = _won_contract(tmp_path, gross, percent)
    old = build_result_ledger_record(
        workflow=LeadWorkflowRecord(
            workflow_id="workflow:exact",
            package_id="package:exact",
            base_candidate_id="candidate:exact",
            status=LeadWorkflowStatus.CLOSED_SUCCESS,
            lead_score=0,
        ),
        status=ResultLedgerStatus.WON,
        gross_value=float(gross),
        share_rate=float(Decimal(percent) / 100),
    )
    assert agreement["calculated_minor"] == expected
    assert money_minor_units(old.share.share_value) == expected
    assert commercial.ledger(tmp_path)[0]["receivable_minor"] == 0


@pytest.mark.parametrize(
    "operation", ["UPDATE cc_contracts SET data='{}'", "DELETE FROM cc_contracts"]
)
def test_native_contract_history_cannot_be_rewritten(tmp_path, operation):
    _won_contract(tmp_path)
    with (
        commercial.connect(tmp_path) as db,
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
    ):
        db.execute(operation)
    assert commercial.ledger(tmp_path)[0]["contract_minor"] == 1999


def test_contract_remains_pinned_to_its_agreed_bid_version(tmp_path):
    lead, bid, agreement = _won_contract(tmp_path)
    commercial.save_bid(
        tmp_path,
        lead,
        payload(
            id=bid["id"],
            expected_version=1,
            status="won",
            contract_value="100.00",
        ),
    )
    retained = commercial.ledger(tmp_path)[0]
    assert (retained["bid_version"], retained["contract_minor"], retained["calculated_minor"]) == (
        1,
        1999,
        agreement["calculated_minor"],
    )


def test_bid_and_outcome_feedback_roll_back_as_one_transaction(tmp_path):
    lead = projection(snapshot(), tmp_path)["rows"][0]
    commercial.initialize(tmp_path)
    with commercial.connect(tmp_path) as db:
        db.execute(
            "CREATE TRIGGER fail_audit BEFORE INSERT ON feedback_events "
            "BEGIN SELECT RAISE(ABORT, 'synthetic audit failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="audit failure"):
        commercial.save_bid(tmp_path, lead, payload(status="won", contract_value="100.00"))
    assert commercial.bids(tmp_path) == []
    assert projection(snapshot(), tmp_path)["rows"][0]["feedback"]["status"] != "Won"


def test_orphan_royalty_entry_is_rejected_by_database_and_restore_validation(tmp_path):
    _won_contract(tmp_path)
    statement = (
        "INSERT INTO cc_ledger VALUES ('orphan','missing','2026-10-17','received',100,'test',NULL)"
    )
    with commercial.connect(tmp_path) as db, pytest.raises(sqlite3.IntegrityError, match="Unknown"):
        db.execute(statement)
    # Simulate a pre-hardening/corrupt archive without modifying any original records.
    with commercial.connect(tmp_path) as db:
        db.execute("DROP TRIGGER cc_ledger_contract_exists")
        db.execute(statement)
    with pytest.raises(ValueError, match="invalid contract"):
        commercial.ledger(tmp_path)
    with pytest.raises(ValueError, match="invalid contract"):
        data_folder.make_backup(tmp_path)


@pytest.mark.parametrize(
    "workflow_status,result_status",
    [
        (LeadWorkflowStatus.READY, ResultLedgerStatus.WON),
        (LeadWorkflowStatus.ACTIVE, ResultLedgerStatus.LOST),
        (LeadWorkflowStatus.REVIEW, ResultLedgerStatus.NO_FIT),
        (LeadWorkflowStatus.CLOSED_SUCCESS, ResultLedgerStatus.LOST),
        (LeadWorkflowStatus.CLOSED_NO_FIT, ResultLedgerStatus.WON),
    ],
)
@pytest.mark.parametrize("authorized", [False, True])
def test_incompatible_final_outcome_creates_no_authority_or_ledger(
    tmp_path,
    workflow_status,
    result_status,
    authorized,
):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'authority.sqlite3'}")
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        store_lead_workflow_record(
            session,
            LeadWorkflowRecord(
                workflow_id="workflow:finality",
                package_id="package:finality",
                base_candidate_id="candidate:finality",
                status=workflow_status,
                lead_score=0,
            ),
        )
    with managed_session(factory) as session, pytest.raises(ResultAuthorityError):
        if authorized:
            apply_authorized_authoritative_result(
                session,
                workflow_id="workflow:finality",
                expected_current_ledger_id=None,
                status=result_status,
                authorization_reason="Synthetic incompatible outcome",
                caller_confirmation=True,
            )
        else:
            apply_authoritative_result(
                session,
                workflow_id="workflow:finality",
                expected_current_ledger_id=None,
                status=result_status,
                authority_reason="Synthetic incompatible outcome",
            )
    with managed_session(factory) as session:
        for model in [ResultLedgerRecordRow, ResultAuthorityEventRow, ResultAuthorityHeadRow]:
            assert list(session.scalars(select(model))) == []


@pytest.mark.parametrize("damage", ["missing_hash", "indexed_identity", "changed_content"])
def test_retained_evidence_damage_cannot_be_published_or_used_for_new_claims(tmp_path, damage):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'evidence.sqlite3'}")
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        IntelligenceStore(session).upsert_evidence(
            EvidenceRecord(
                evidence_id="evidence:original",
                source_name="Synthetic source",
                record_type="synthetic",
                evidence_text="Original retained claim",
            )
        )
    with managed_session(factory) as session:
        row = session.scalar(select(IntelligenceEvidenceRecord))
        value = json.loads(row.payload_json)
        if damage == "missing_hash":
            value.pop("content_hash")
        elif damage == "indexed_identity":
            row.source_name = "Wrong source index"
        else:
            value["evidence_text"] = "Changed claim"
        row.payload_json = json.dumps(value)
    with managed_session(factory) as session:
        store = IntelligenceStore(session)
        with pytest.raises(ValueError):
            store.get_evidence("evidence:original")
        with pytest.raises(ValueError):
            store.list_evidence()
        with pytest.raises(ValueError):
            store.upsert_entity(
                EntityIdentity(
                    entity_id="entity:new",
                    entity_type=EntityType.DOCUMENT,
                    canonical_name="New claim",
                    evidence_record_ids=["evidence:original"],
                )
            )


def test_native_exact_input_inspector_rejects_changed_original_bytes(tmp_path):
    directory = tmp_path / "private"
    kind, record = retained_inputs()[0]
    original = record.model_dump_json(round_trip=True).encode()
    runtime = InvestigationRuntime(directory)
    try:
        runtime.enqueue_bytes(original, kind)
        assert runtime.process(max_jobs=150)["failed_jobs"] == 0
    finally:
        runtime.close()
    import hashlib

    digest = hashlib.sha256(original).hexdigest()
    evidence_id = "evidence:retained-input:" + digest
    assert graph_view(directory, mode="evidence", evidence_id=evidence_id)["available"]
    (directory / "investigation-inputs" / digest).write_bytes(b"Changed original input")
    with pytest.raises(ValueError, match="exact-byte integrity"):
        graph_view(directory, mode="evidence", evidence_id=evidence_id)
    with pytest.raises(ValueError, match="identity mismatch"):
        data_folder.make_backup(directory)


def test_native_finance_backup_restore_preserves_agreement_and_corrections(tmp_path):
    directory = tmp_path / "original"
    _, _, agreement = _won_contract(directory)
    received = commercial.transaction(
        directory,
        {
            "contract_id": agreement["id"],
            "kind": "received",
            "amount": "1.25",
            "reference": "R1",
        },
    )
    commercial.transaction(
        directory,
        {
            "contract_id": agreement["id"],
            "kind": "reversal",
            "reverses": received["id"],
            "reference": "Correction R1",
        },
    )
    expected = commercial.ledger(directory)
    archive = tmp_path / "snapshot.zip"
    archive.write_bytes(data_folder.make_backup(directory))
    staged = tmp_path / "staged"
    checked = data_folder.preview_restore(archive, staged)
    restored = tmp_path / "restored"
    data_folder.apply_restore(staged, checked, restored)
    assert commercial.ledger(restored) == expected
    assert commercial.ledger(directory) == expected


@pytest.mark.parametrize("gross,wrong", [(0.01, 0.01), (0.03, 0.01)])
def test_legacy_share_validator_rejects_binary_float_half_cent_results(gross, wrong):
    from constructionsight.result_ledger_models import ResultShareRecord

    with pytest.raises(ValueError, match="share_value"):
        ResultShareRecord(
            share_record_id="share:wrong",
            workflow_id="workflow:rounding",
            gross_value=gross,
            share_rate=0.5,
            share_value=wrong,
        )


def test_native_workflow_uses_private_primary_database_guards(tmp_path):
    private = tmp_path / "private"
    with commercial.connect(private) as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    before = (private / "workflow.sqlite3").read_bytes()
    other = tmp_path / "other"
    other.mkdir(mode=0o700)
    (other / "workflow.sqlite3").symlink_to(private / "workflow.sqlite3")
    with pytest.raises(ValueError):
        commercial.connect(other)
    assert (private / "workflow.sqlite3").read_bytes() == before
    private.chmod(0o755)
    with pytest.raises(ValueError, match="owner-only"):
        commercial.connect(private)
    private.chmod(0o700)


def test_unvalidated_model_copy_cannot_introduce_changed_evidence_content(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'evidence-copy.sqlite3'}")
    initialize_database(engine)
    factory = session_factory(engine)
    original = EvidenceRecord(
        evidence_id="evidence:copy",
        source_name="Synthetic source",
        record_type="test",
        evidence_text="Original claim",
    )
    altered = original.model_copy(update={"evidence_text": "Unreviewed altered claim"})
    with managed_session(factory) as session, pytest.raises(ValueError, match="content_hash"):
        IntelligenceStore(session).upsert_evidence(altered)
    with managed_session(factory) as session:
        assert IntelligenceStore(session).list_evidence() == []
