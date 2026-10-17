"""Historical transition rows and source projection must agree before native review."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from constructionsight.command_center_legacy_events import verified_original_workflow_events
from constructionsight.lead_operator_service import (
    load_persisted_lead_workflow,
    transition_persisted_lead_workflow,
)
from constructionsight.lead_workflow_models import LeadWorkflowEvent, LeadWorkflowStatus
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.lead_workflow_orm import LeadWorkflowEventRecord
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_event,
    store_lead_workflow_record,
)
from tests.test_bid_proposal_service import _package
from constructionsight.lead_workflow_service import create_lead_workflow


def _history(tmp_path: Path) -> tuple[object, str]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'original.sqlite3'}")
    initialize_database(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)
    with Session(engine) as session, session.begin():
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
    with Session(engine) as session, session.begin():
        transition_persisted_lead_workflow(
            session, workflow_id=workflow.workflow_id,
            expected_current_status=LeadWorkflowStatus.READY,
            next_status=LeadWorkflowStatus.ACTIVE,
            reason="Original historical operator activated review",
        )
    return engine, workflow.workflow_id


def test_two_original_transition_events_have_exact_verified_projection(tmp_path: Path) -> None:
    engine, workflow_id = _history(tmp_path)
    with Session(engine) as session:
        workflow = load_persisted_lead_workflow(session, workflow_id)
        verified = verified_original_workflow_events(session, workflow)
        assert verified["history_integrity_validated"] is True
        assert verified["event_count"] == 2
        assert verified["current_status"] == "active"
        assert [r["current_status"] for r in verified["transitions"]] == [
            "ready", "active",
        ]
        assert verified["transitions"][1]["previous_status"] == "ready"
        assert verified["transitions"][1]["reason"] == (
            "Original historical operator activated review"
        )
        assert verified["commercial_authority_granted"] is False if (
            "commercial_authority_granted" in verified
        ) else verified["bid_authorized"] is False
        assert verified["outreach_authorized"] is False
    engine.dispose()


@pytest.mark.parametrize("corruption", ["edit_previous_status", "extra_event"])
def test_original_history_rejects_forged_or_orphan_transition_event_rows(
    tmp_path: Path, corruption: str,
) -> None:
    engine, workflow_id = _history(tmp_path)
    with Session(engine) as session, session.begin():
        if corruption == "edit_previous_status":
            second = session.query(LeadWorkflowEventRecord).filter_by(
                workflow_id=workflow_id, current_status="active"
            ).one()
            session.execute(
                update(LeadWorkflowEventRecord)
                .where(LeadWorkflowEventRecord.id == second.id)
                .values(previous_status="monitor")
            )
        else:
            store_lead_workflow_event(
                session,
                LeadWorkflowEvent(
                    event_id="lead-workflow-event:extra-unlisted",
                    previous_status=LeadWorkflowStatus.ACTIVE,
                    current_status=LeadWorkflowStatus.PAUSED,
                    reason="Unexpected standalone persisted event",
                ),
                workflow_id=workflow_id,
            )
    with Session(engine) as session:
        workflow = load_persisted_lead_workflow(session, workflow_id)
        with pytest.raises(ValueError, match="transition"):
            verified_original_workflow_events(session, workflow)
    engine.dispose()
