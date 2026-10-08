"""Build exact-money Bid Studio pricing previews from validated request evidence."""

from __future__ import annotations

from sqlalchemy.orm import Session

from constructionsight.bid_pricing_models import (
    BidPriceLine,
    BidPriceLineInput,
    BidPricingPreview,
)
from constructionsight.bid_request_models import BidRequestEvidence
from constructionsight.bid_request_service import (
    BidRequestEvidenceError,
    build_persisted_bid_request_evidence,
)
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.result_ledger_service import money_minor_units


class BidPricingPreviewError(ValueError):
    """Raised when request evidence or pricing input cannot support a preview."""


def build_persisted_bid_pricing_preview(
    session: Session,
    *,
    request_evidence: BidRequestEvidence,
    currency_code: str,
    line_items: list[BidPriceLineInput],
    assumptions: list[str] | None = None,
    exclusions: list[str] | None = None,
    validity_note: str,
) -> BidPricingPreview:
    """Build manual exact-money pricing only after current request revalidation."""

    if not 1 <= len(line_items) <= 100:
        raise BidPricingPreviewError(
            "pricing preview requires between 1 and 100 line items"
        )
    try:
        evidence = BidRequestEvidence.model_validate(
            request_evidence.model_dump(mode="python")
        )
        expected_status = LeadWorkflowStatus(evidence.workflow_status)
        current = build_persisted_bid_request_evidence(
            session,
            workflow_id=evidence.workflow_id,
            expected_current_status=expected_status,
            request_channel=evidence.request_channel,
            requester_business_name=evidence.requester_business_name,
            requester_business_role=evidence.requester_business_role,
            request_source_name=evidence.request_source_name,
            request_source_reference=evidence.request_source_reference,
            request_review_basis=evidence.request_review_basis,
            request_observed_at=evidence.request_observed_at,
            request_text=evidence.request_text,
            scope_summary=evidence.scope_summary,
        )
    except (BidRequestEvidenceError, ValueError) as exc:
        raise BidPricingPreviewError(str(exc)) from exc

    if current.request_evidence_id != evidence.request_evidence_id:
        raise BidPricingPreviewError(
            "bid request evidence no longer matches current persisted workflow state"
        )

    normalized_lines: list[BidPriceLine] = []
    for index, raw_line in enumerate(line_items):
        line = BidPriceLineInput.model_validate(raw_line)
        try:
            amount_minor = money_minor_units(
                line.amount,
                field_name=f"line_items[{index}].amount",
            )
        except ValueError as exc:
            raise BidPricingPreviewError(str(exc)) from exc
        normalized_lines.append(
            BidPriceLine(
                line_key=line.line_key.strip(),
                description=line.description.strip(),
                pricing_basis=line.pricing_basis.strip(),
                amount_minor=amount_minor,
            )
        )

    try:
        return BidPricingPreview(
            request_evidence_id=evidence.request_evidence_id,
            workflow_id=evidence.workflow_id,
            package_id=evidence.package_id,
            base_candidate_id=evidence.base_candidate_id,
            currency_code=currency_code.strip().upper(),
            line_items=normalized_lines,
            assumptions=list(assumptions or []),
            exclusions=list(exclusions or []),
            validity_note=validity_note,
        )
    except ValueError as exc:
        raise BidPricingPreviewError(str(exc)) from exc
