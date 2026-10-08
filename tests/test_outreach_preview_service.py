import pytest

from constructionsight.lead_dedupe_service import (
    build_lead_fingerprint,
    check_lead_duplicate,
)
from constructionsight.lead_review_models import (
    LeadReviewItem,
    LeadReviewPackage,
    LeadReviewStatus,
)
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.outreach_preview_models import (
    OutreachChannel,
    OutreachContactReference,
)
from constructionsight.outreach_preview_service import (
    OutreachPreviewError,
    build_persisted_outreach_preview,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_store import (
    store_lead_duplicate_result,
    store_lead_review_package,
    store_lead_workflow_record,
)


def _package(
    *,
    status: LeadReviewStatus = LeadReviewStatus.READY,
    score: int = 80,
) -> LeadReviewPackage:
    items = []
    if status is LeadReviewStatus.READY:
        items = [
            LeadReviewItem(
                item_key="lead-item:preview",
                label="prepare reviewed lead package",
                rationale="corroborated retained evidence supports operator review",
            )
        ]
    return LeadReviewPackage(
        package_id=f"lead-review:preview:{status.value}",
        base_candidate_id="candidate:preview",
        lead_score=score,
        status=status,
        summary="preview test package",
        items=items,
        evidence_notes=["permit_transition: permit issued"],
    )


def _contact(*, review_basis: str = "Reviewed official business contact page.") -> OutreachContactReference:
    return OutreachContactReference(
        channel=OutreachChannel.EMAIL,
        destination="estimating@example-contractor.test",
        business_role="estimating department",
        source_name="official contractor website",
        source_reference="https://example-contractor.test/contact",
        contact_review_basis=review_basis,
    )


def test_ready_persisted_workflow_builds_preview_without_send_authority() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)

        first = build_persisted_outreach_preview(
            session,
            workflow_id=workflow.workflow_id,
            expected_current_status=LeadWorkflowStatus.READY,
            contact=_contact(),
            subject="Construction site security support",
            body="We would like to introduce our construction site security services.",
        )
        second = build_persisted_outreach_preview(
            session,
            workflow_id=workflow.workflow_id,
            expected_current_status=LeadWorkflowStatus.READY,
            contact=_contact(),
            subject="Construction site security support",
            body="We would like to introduce our construction site security services.",
        )

    assert first.preview_id == second.preview_id
    assert first.requires_human_approval is True
    assert first.external_send_authorized is False
    assert first.send_executed is False
    assert first.bid_authorized is False
    assert first.workflow_status == "ready"
    assert first.evidence_notes == ["permit_transition: permit issued"]


def test_non_ready_workflow_cannot_build_outreach_preview() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package(status=LeadReviewStatus.MONITOR, score=20)
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)

        with pytest.raises(
            OutreachPreviewError,
            match="requires a ready or active lead workflow",
        ):
            build_persisted_outreach_preview(
                session,
                workflow_id=workflow.workflow_id,
                expected_current_status=LeadWorkflowStatus.MONITOR,
                contact=_contact(),
                subject="Preview",
                body="Preview body",
            )


def test_blank_contact_review_basis_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        _contact(review_basis="   ")


def test_late_duplicate_finding_blocks_outreach_preview() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)
    candidate = build_lead_fingerprint(package=package, site_key="site:preview")
    existing = candidate.model_copy(update={"base_candidate_id": "candidate:existing"})
    duplicate = check_lead_duplicate(candidate, [existing])

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        store_lead_duplicate_result(session, duplicate)

        with pytest.raises(
            OutreachPreviewError,
            match="unresolved duplicate review",
        ):
            build_persisted_outreach_preview(
                session,
                workflow_id=workflow.workflow_id,
                expected_current_status=LeadWorkflowStatus.READY,
                contact=_contact(),
                subject="Preview",
                body="Preview body",
            )
