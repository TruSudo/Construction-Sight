import json
from datetime import timedelta

import pytest
from sqlalchemy import inspect, select

from constructionsight.domain_types import confidence_band
from constructionsight.lead_dedupe_models import (
    LeadDuplicateResult,
    LeadDuplicateStatus,
    LeadFingerprint,
)
from constructionsight.lead_review_models import (
    LeadReviewItem,
    LeadReviewPackage,
    LeadReviewStatus,
)
from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)
from constructionsight.opportunity_enrichment_models import (
    EnrichmentSignalKind,
    OpportunityEnrichmentReport,
    OpportunityEnrichmentSignal,
)
from constructionsight.result_ledger_models import (
    ResultLedgerRecord,
    ResultLedgerStatus,
    ResultShareRecord,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import (
    LeadDuplicateResultRecord,
    LeadFingerprintRecord,
    LeadReviewPackageRecord,
    LeadWorkflowEventRecord,
    LeadWorkflowRecordRow,
    OpportunityEnrichmentReportRecord,
    ResultLedgerRecordRow,
    ResultShareRecordRow,
)
from constructionsight.storage.lead_workflow_store import (
    store_lead_duplicate_result,
    store_lead_fingerprint,
    store_lead_review_package,
    store_lead_workflow_event,
    store_lead_workflow_record,
    store_opportunity_enrichment_report,
    store_result_ledger_record,
    store_result_share_record,
)


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def _report() -> OpportunityEnrichmentReport:
    signal = OpportunityEnrichmentSignal(
        signal_key="signal:test",
        signal_kind=EnrichmentSignalKind.PERMIT_TRANSITION,
        label="permit status",
        score_delta=80,
        confidence_score=80,
        reason="permit status changed",
        limitations=["source needs review"],
    )
    return OpportunityEnrichmentReport(
        report_id="opportunity-enrichment:test",
        base_candidate_id="candidate:test",
        lead_score=80,
        confidence_score=80,
        confidence_band=confidence_band(80),
        signals=[signal],
        reasons=["permit status changed"],
        limitations=["source needs review"],
        next_action="prepare preview",
    )


def _package(score: int = 80) -> LeadReviewPackage:
    item = LeadReviewItem(
        item_key="lead-review-item:test",
        label="review evidence",
        rationale="source evidence supports review",
    )
    return LeadReviewPackage(
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        lead_score=score,
        status=LeadReviewStatus.READY,
        summary="review package",
        items=[item],
        evidence_notes=["permit_transition: permit status changed"],
    )


def _fingerprint(score: int = 80) -> LeadFingerprint:
    return LeadFingerprint(
        fingerprint_key="lead-fingerprint:test",
        base_candidate_id="candidate:test",
        site_key="site:test",
        source_key="permit:test",
        source_record_id="permit:1",
        normalized_title="WAREHOUSE PHASE II",
        lead_score=score,
    )


def _duplicate_result() -> LeadDuplicateResult:
    return LeadDuplicateResult(
        result_id="lead-duplicate:test",
        status=LeadDuplicateStatus.REVIEW_NEEDED,
        candidate=_fingerprint(),
        matched_fingerprint_keys=["lead-fingerprint:old"],
        reasons=["same source record appears in existing lead"],
        limitations=["review prior lead history"],
    )


def _workflow() -> LeadWorkflowRecord:
    event = LeadWorkflowEvent(
        event_id="lead-workflow-event:test",
        current_status=LeadWorkflowStatus.READY,
        reason="review package ready",
    )
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        fingerprint_key="lead-fingerprint:test",
        status=LeadWorkflowStatus.READY,
        lead_score=80,
        events=[event],
        notes=["ready for operator review"],
        limitations=["review prior lead history"],
    )


def _share() -> ResultShareRecord:
    return ResultShareRecord(
        share_record_id="result-share:test",
        workflow_id="lead-workflow:test",
        gross_value=1000.0,
        share_rate=0.1,
        share_value=100.0,
        notes=["standard share calculation"],
    )


def _ledger() -> ResultLedgerRecord:
    return ResultLedgerRecord(
        ledger_id="result-ledger:test",
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
        share=_share(),
        reasons=["contract won"],
    )


def test_lead_workflow_tables_are_created() -> None:
    engine, _factory = _session_factory()

    table_names = set(inspect(engine).get_table_names())

    assert "opportunity_enrichment_reports" in table_names
    assert "lead_review_packages" in table_names
    assert "lead_fingerprints" in table_names
    assert "lead_duplicate_results" in table_names
    assert "lead_workflows" in table_names
    assert "lead_workflow_events" in table_names
    assert "result_ledgers" in table_names
    assert "result_share_records" in table_names


def test_store_opportunity_enrichment_report_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_opportunity_enrichment_report(session, _report())
        session.flush()
        row = session.execute(select(OpportunityEnrichmentReportRecord)).scalar_one()

        assert row.confidence_band == "high"
        assert row.scoring_profile_key == "opportunity-scoring:default"
        assert row.scoring_profile_version == "2026-06-30.1"
        payload = json.loads(row.payload_json)
        assert payload["signals"][0]["reason"] == "permit status changed"
        assert payload["limitations"] == ["source needs review"]
        assert payload["scoring_profile_key"] == "opportunity-scoring:default"


def test_store_lead_review_package_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_lead_review_package(session, _package())
        session.flush()
        row = session.execute(select(LeadReviewPackageRecord)).scalar_one()

        assert row.status == "ready"
        payload = json.loads(row.payload_json)
        assert payload["items"][0]["rationale"] == "source evidence supports review"


def test_store_lead_fingerprint_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_lead_fingerprint(session, _fingerprint())
        session.flush()
        row = session.execute(select(LeadFingerprintRecord)).scalar_one()

        assert row.source_record_id == "permit:1"
        payload = json.loads(row.payload_json)
        assert payload["normalized_title"] == "WAREHOUSE PHASE II"


def test_store_lead_duplicate_result_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_lead_duplicate_result(session, _duplicate_result())
        session.flush()
        row = session.execute(select(LeadDuplicateResultRecord)).scalar_one()

        assert row.status == "review_needed"
        assert row.matched_count == 1
        payload = json.loads(row.payload_json)
        assert payload["limitations"] == ["review prior lead history"]


def test_store_duplicate_result_rejects_unreviewed_status_overwrite() -> None:
    _engine, factory = _session_factory()
    unresolved = _duplicate_result()
    rewritten = unresolved.model_copy(
        update={"status": LeadDuplicateStatus.UNIQUE, "matched_fingerprint_keys": []},
    )
    with managed_session(factory) as session:
        store_lead_duplicate_result(session, unresolved)
        session.flush()
        with pytest.raises(ValueError, match="duplicate results are immutable"):
            store_lead_duplicate_result(session, rewritten)
        row = session.execute(select(LeadDuplicateResultRecord)).scalar_one()
        assert row.status == LeadDuplicateStatus.REVIEW_NEEDED.value
        assert row.payload_json == json.dumps(unresolved.to_dict(), sort_keys=True)


def test_store_duplicate_result_recheck_preserves_first_verdict_snapshot() -> None:
    _engine, factory = _session_factory()
    first = _duplicate_result()
    rescanned = first.model_copy(
        update={
            "candidate": first.candidate.model_copy(
                update={
                    "created_at": first.candidate.created_at + timedelta(seconds=1),
                    "lead_score": 81,
                }
            )
        }
    )
    with managed_session(factory) as session:
        first_row = store_lead_duplicate_result(session, first)
        session.flush()
        replayed_row = store_lead_duplicate_result(session, rescanned)
        session.flush()
        assert replayed_row is first_row
        persisted = session.execute(select(LeadDuplicateResultRecord)).scalars().all()
        assert len(persisted) == 1
        assert persisted[0].payload_json == json.dumps(first.to_dict(), sort_keys=True)
        assert persisted[0].status == LeadDuplicateStatus.REVIEW_NEEDED.value


def test_store_workflow_rejects_actionable_state_with_persisted_duplicate() -> None:
    _engine, factory = _session_factory()
    with managed_session(factory) as session:
        store_lead_duplicate_result(session, _duplicate_result())
        with pytest.raises(ValueError, match="unresolved duplicate review"):
            store_lead_workflow_record(session, _workflow())
        assert session.execute(select(LeadWorkflowRecordRow)).scalar_one_or_none() is None


def test_store_workflow_rejects_duplicate_from_same_candidate_without_fingerprint() -> None:
    _engine, factory = _session_factory()
    with managed_session(factory) as session:
        store_lead_duplicate_result(session, _duplicate_result())
        workflow = _workflow().model_copy(update={"fingerprint_key": None})
        with pytest.raises(ValueError, match="unresolved duplicate review"):
            store_lead_workflow_record(session, workflow)
        assert session.execute(select(LeadWorkflowRecordRow)).scalar_one_or_none() is None


def test_store_lead_workflow_event_roundtrip() -> None:
    _engine, factory = _session_factory()
    event = LeadWorkflowEvent(
        event_id="lead-workflow-event:test",
        previous_status=LeadWorkflowStatus.MONITOR,
        current_status=LeadWorkflowStatus.REVIEW,
        reason="new evidence arrived",
    )

    with managed_session(factory) as session:
        store_lead_workflow_event(session, event, workflow_id="lead-workflow:test")
        session.flush()
        row = session.execute(select(LeadWorkflowEventRecord)).scalar_one()

        assert row.workflow_id == "lead-workflow:test"
        assert row.previous_status == "monitor"
        assert row.current_status == "review"
        payload = json.loads(row.payload_json)
        assert payload["reason"] == "new evidence arrived"


def test_store_lead_workflow_record_roundtrip_stores_events() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_lead_workflow_record(session, _workflow())
        session.flush()
        workflow_row = session.execute(select(LeadWorkflowRecordRow)).scalar_one()
        event_row = session.execute(select(LeadWorkflowEventRecord)).scalar_one()

        assert workflow_row.status == "ready"
        assert event_row.workflow_id == "lead-workflow:test"
        payload = json.loads(workflow_row.payload_json)
        assert payload["limitations"] == ["review prior lead history"]


def test_store_result_share_record_roundtrip() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_result_share_record(session, _share())
        session.flush()
        row = session.execute(select(ResultShareRecordRow)).scalar_one()

        assert row.share_value == 100.0
        payload = json.loads(row.payload_json)
        assert payload["notes"] == ["standard share calculation"]


def test_store_result_ledger_record_roundtrip_stores_share() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_result_ledger_record(session, _ledger())
        session.flush()
        ledger_row = session.execute(select(ResultLedgerRecordRow)).scalar_one()
        share_row = session.execute(select(ResultShareRecordRow)).scalar_one()

        assert ledger_row.status == "won"
        assert ledger_row.share_record_id == "result-share:test"
        assert share_row.share_value == 100.0
        payload = json.loads(ledger_row.payload_json)
        assert payload["reasons"] == ["contract won"]


def test_store_helpers_update_existing_rows() -> None:
    _engine, factory = _session_factory()

    with managed_session(factory) as session:
        store_lead_fingerprint(session, _fingerprint(score=20))
        store_lead_fingerprint(session, _fingerprint(score=80))
        session.flush()
        rows = session.execute(select(LeadFingerprintRecord)).scalars().all()

        assert len(rows) == 1
        assert rows[0].lead_score == 80
