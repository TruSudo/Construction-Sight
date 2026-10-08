from datetime import UTC, datetime

import pytest

from constructionsight.bid_pricing_models import BidPriceLineInput
from constructionsight.bid_pricing_service import build_persisted_bid_pricing_preview
from constructionsight.bid_proposal_service import (
    BidProposalDraftError,
    build_persisted_bid_proposal_draft,
)
from constructionsight.bid_request_models import BidRequestChannel
from constructionsight.bid_request_service import build_persisted_bid_request_evidence
from constructionsight.lead_review_models import (
    LeadReviewItem,
    LeadReviewPackage,
    LeadReviewStatus,
)
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_store import (
    store_lead_review_package,
    store_lead_workflow_record,
)


def _package() -> LeadReviewPackage:
    return LeadReviewPackage(
        package_id="lead-review:proposal-draft",
        base_candidate_id="candidate:proposal-draft",
        lead_score=94,
        status=LeadReviewStatus.READY,
        summary="proposal draft fixture",
        items=[
            LeadReviewItem(
                item_key="lead-item:proposal-draft",
                label="prepare reviewed lead package",
                rationale="retained evidence supports request review",
            )
        ],
        evidence_notes=["permit_transition: permit issued"],
    )


def _request(session, workflow_id: str):
    return build_persisted_bid_request_evidence(
        session,
        workflow_id=workflow_id,
        expected_current_status=LeadWorkflowStatus.READY,
        request_channel=BidRequestChannel.EMAIL,
        requester_business_name="Example Contractor LLC",
        requester_business_role="estimating department",
        request_source_name="retained business email",
        request_source_reference="message:fixture:proposal-draft",
        request_review_basis="Reviewed explicit pricing request.",
        request_observed_at=datetime(2026, 10, 8, 10, 0, tzinfo=UTC),
        request_text="Please send pricing for construction site security.",
        scope_summary="Night guard coverage for the reviewed construction site.",
    )


def _pricing(session, request_evidence):
    return build_persisted_bid_pricing_preview(
        session,
        request_evidence=request_evidence,
        currency_code="USD",
        line_items=[
            BidPriceLineInput(
                line_key="guarding",
                description="Night guard coverage",
                pricing_basis="Manual reviewed amount for preview only.",
                amount="125.50",
            )
        ],
        assumptions=["Synthetic preview only."],
        exclusions=["No tax treatment is implied."],
        validity_note="Manual preview; commercial approval required.",
    )


def test_proposal_draft_binds_request_pricing_scope_and_exact_money() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        request = _request(session, workflow.workflow_id)
        pricing = _pricing(session, request)
        first = build_persisted_bid_proposal_draft(
            session,
            request_evidence=request,
            pricing_preview=pricing,
            proposal_title="Construction Site Security Proposal",
            cover_note="Internal draft prepared for commercial review only.",
            additional_terms=["Final schedule subject to approved scope."],
        )
        second = build_persisted_bid_proposal_draft(
            session,
            request_evidence=request,
            pricing_preview=pricing,
            proposal_title="Construction Site Security Proposal",
            cover_note="Internal draft prepared for commercial review only.",
            additional_terms=["Final schedule subject to approved scope."],
        )

    assert first.proposal_draft_id == second.proposal_draft_id
    assert first.request_evidence_id == request.request_evidence_id
    assert first.pricing_preview_id == pricing.pricing_preview_id
    assert first.prepared_for_business_name == "Example Contractor LLC"
    assert first.scope_summary == request.scope_summary
    assert first.subtotal_minor == 12_550
    assert first.requires_commercial_approval is True
    assert first.commercial_terms_authorized is False
    assert first.customer_facing_bid_authorized is False
    assert first.bid_submission_authorized is False


def test_proposal_draft_rejects_forged_pricing_preview() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        request = _request(session, workflow.workflow_id)
        pricing = _pricing(session, request)
        forged = pricing.model_copy(update={"validity_note": "Changed without new identity."})
        with pytest.raises(
            BidProposalDraftError,
            match="pricing_preview_id does not match",
        ):
            build_persisted_bid_proposal_draft(
                session,
                request_evidence=request,
                pricing_preview=forged,
                proposal_title="Internal proposal",
                cover_note="Commercial review required.",
            )


def test_proposal_draft_rejects_request_pricing_identity_mismatch() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        request = _request(session, workflow.workflow_id)
        pricing = _pricing(session, request)
        mismatched_request = request.model_copy(
            update={
                "request_source_reference": "message:other",
                "request_evidence_id": "",
            }
        )
        mismatched_request = type(request).model_validate(
            mismatched_request.model_dump(mode="python")
        )
        with pytest.raises(
            BidProposalDraftError,
            match="not bound to the supplied bid request evidence",
        ):
            build_persisted_bid_proposal_draft(
                session,
                request_evidence=mismatched_request,
                pricing_preview=pricing,
                proposal_title="Internal proposal",
                cover_note="Commercial review required.",
            )
