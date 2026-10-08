"""Build internal proposal drafts from current request and pricing previews."""

from __future__ import annotations

from sqlalchemy.orm import Session

from constructionsight.bid_pricing_models import (
    BidPriceLineInput,
    BidPricingPreview,
)
from constructionsight.bid_pricing_service import (
    BidPricingPreviewError,
    build_persisted_bid_pricing_preview,
)
from constructionsight.bid_proposal_models import BidProposalDraft
from constructionsight.bid_request_models import BidRequestEvidence


class BidProposalDraftError(ValueError):
    """Raised when current request/pricing state cannot support a proposal draft."""


def build_persisted_bid_proposal_draft(
    session: Session,
    *,
    request_evidence: BidRequestEvidence,
    pricing_preview: BidPricingPreview,
    proposal_title: str,
    cover_note: str,
    additional_terms: list[str] | None = None,
) -> BidProposalDraft:
    """Build an internal proposal draft after exact pricing-state revalidation."""

    try:
        evidence = BidRequestEvidence.model_validate(
            request_evidence.model_dump(mode="python")
        )
        supplied_pricing = BidPricingPreview.model_validate(
            pricing_preview.model_dump(mode="python")
        )
        if supplied_pricing.request_evidence_id != evidence.request_evidence_id:
            raise BidProposalDraftError(
                "pricing preview is not bound to the supplied bid request evidence"
            )
        current_pricing = build_persisted_bid_pricing_preview(
            session,
            request_evidence=evidence,
            currency_code=supplied_pricing.currency_code,
            line_items=[
                BidPriceLineInput(
                    line_key=line.line_key,
                    description=line.description,
                    pricing_basis=line.pricing_basis,
                    amount=_minor_units_decimal(line.amount_minor),
                )
                for line in supplied_pricing.line_items
            ],
            assumptions=list(supplied_pricing.assumptions),
            exclusions=list(supplied_pricing.exclusions),
            validity_note=supplied_pricing.validity_note,
        )
    except (BidPricingPreviewError, ValueError) as exc:
        if isinstance(exc, BidProposalDraftError):
            raise
        raise BidProposalDraftError(str(exc)) from exc

    if current_pricing.pricing_preview_id != supplied_pricing.pricing_preview_id:
        raise BidProposalDraftError(
            "bid pricing preview no longer matches current persisted workflow state"
        )

    try:
        return BidProposalDraft(
            request_evidence_id=evidence.request_evidence_id,
            pricing_preview_id=current_pricing.pricing_preview_id,
            workflow_id=evidence.workflow_id,
            package_id=evidence.package_id,
            base_candidate_id=evidence.base_candidate_id,
            prepared_for_business_name=evidence.requester_business_name,
            requester_business_role=evidence.requester_business_role,
            proposal_title=proposal_title,
            cover_note=cover_note,
            scope_summary=evidence.scope_summary,
            currency_code=current_pricing.currency_code,
            pricing_method=current_pricing.pricing_method,
            line_items=list(current_pricing.line_items),
            subtotal_minor=current_pricing.subtotal_minor or 0,
            assumptions=list(current_pricing.assumptions),
            exclusions=list(current_pricing.exclusions),
            validity_note=current_pricing.validity_note,
            additional_terms=list(additional_terms or []),
        )
    except ValueError as exc:
        raise BidProposalDraftError(str(exc)) from exc


def _minor_units_decimal(value: int) -> str:
    """Render exact currency minor units as a scale-two decimal string."""

    if value < 0:
        raise BidProposalDraftError("pricing line amount cannot be negative")
    whole, remainder = divmod(value, 100)
    return f"{whole}.{remainder:02d}"
