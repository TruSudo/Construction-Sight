from datetime import UTC, datetime

import pytest

from constructionsight.bid_pricing_models import BidPriceLineInput
from constructionsight.bid_pricing_service import (
    BidPricingPreviewError,
    build_persisted_bid_pricing_preview,
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
        package_id="lead-review:pricing-preview",
        base_candidate_id="candidate:pricing-preview",
        lead_score=90,
        status=LeadReviewStatus.READY,
        summary="pricing preview fixture",
        items=[
            LeadReviewItem(
                item_key="lead-item:pricing-preview",
                label="prepare reviewed lead package",
                rationale="retained evidence supports request review",
            )
        ],
        evidence_notes=["permit_transition: permit issued"],
    )


def _request_evidence(session, workflow_id: str):
    return build_persisted_bid_request_evidence(
        session,
        workflow_id=workflow_id,
        expected_current_status=LeadWorkflowStatus.READY,
        request_channel=BidRequestChannel.EMAIL,
        requester_business_name="Example Contractor LLC",
        requester_business_role="estimating department",
        request_source_name="retained business email",
        request_source_reference="message:fixture:pricing-preview",
        request_review_basis="Reviewed explicit pricing request.",
        request_observed_at=datetime(2026, 10, 8, 9, 0, tzinfo=UTC),
        request_text="Please send pricing for construction site security.",
        scope_summary="Night guard coverage for the reviewed construction site.",
    )


def _line(key: str, amount: str) -> BidPriceLineInput:
    return BidPriceLineInput(
        line_key=key,
        description=f"Pricing line {key}",
        pricing_basis="Manual reviewed amount for preview only.",
        amount=amount,
    )


def test_pricing_preview_uses_exact_minor_units_and_is_deterministic() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        evidence = _request_evidence(session, workflow.workflow_id)
        first = build_persisted_bid_pricing_preview(
            session,
            request_evidence=evidence,
            currency_code="usd",
            line_items=[_line("guarding", "100.00"), _line("equipment", "25.50")],
            assumptions=["Synthetic preview only."],
            exclusions=["No tax treatment is implied."],
            validity_note="Manual preview; commercial approval required.",
        )
        second = build_persisted_bid_pricing_preview(
            session,
            request_evidence=evidence,
            currency_code="USD",
            line_items=[_line("guarding", "100.00"), _line("equipment", "25.50")],
            assumptions=["Synthetic preview only."],
            exclusions=["No tax treatment is implied."],
            validity_note="Manual preview; commercial approval required.",
        )

    assert first.pricing_preview_id == second.pricing_preview_id
    assert first.currency_code == "USD"
    assert first.subtotal_minor == 12_550
    assert [line.amount_minor for line in first.line_items] == [10_000, 2_550]
    assert first.requires_commercial_approval is True
    assert first.commercial_terms_authorized is False
    assert first.customer_facing_bid_authorized is False
    assert first.bid_submission_authorized is False


def test_pricing_preview_rejects_fractional_cent_amount() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        evidence = _request_evidence(session, workflow.workflow_id)
        with pytest.raises(BidPricingPreviewError, match="at most 2 decimal places"):
            build_persisted_bid_pricing_preview(
                session,
                request_evidence=evidence,
                currency_code="USD",
                line_items=[_line("guarding", "10.001")],
                validity_note="Commercial approval required.",
            )


def test_pricing_preview_rejects_forged_request_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        evidence = _request_evidence(session, workflow.workflow_id)
        forged = evidence.model_copy(
            update={"request_text": "Changed request without a new evidence identity."}
        )
        with pytest.raises(
            BidPricingPreviewError,
            match="request_evidence_id does not match",
        ):
            build_persisted_bid_pricing_preview(
                session,
                request_evidence=forged,
                currency_code="USD",
                line_items=[_line("guarding", "100.00")],
                validity_note="Commercial approval required.",
            )


def test_pricing_preview_rejects_duplicate_line_keys() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        evidence = _request_evidence(session, workflow.workflow_id)
        with pytest.raises(BidPricingPreviewError, match="line keys must be unique"):
            build_persisted_bid_pricing_preview(
                session,
                request_evidence=evidence,
                currency_code="USD",
                line_items=[_line("guarding", "100.00"), _line("guarding", "25.00")],
                validity_note="Commercial approval required.",
            )
