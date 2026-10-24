"""Native entry to original guarded no-send, no-submission commercial previews.

Every result is derived from current persisted original workflow authority.
This module never creates a lead, price authorization, bid, outreach or contract.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.bid_pricing_models import BidPriceLineInput, BidPricingPreview
from constructionsight.bid_pricing_service import build_persisted_bid_pricing_preview
from constructionsight.bid_proposal_models import BidProposalDraft
from constructionsight.bid_proposal_service import build_persisted_bid_proposal_draft
from constructionsight.bid_request_models import BidRequestChannel, BidRequestEvidence
from constructionsight.bid_request_service import build_persisted_bid_request_evidence
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.outreach_preview_models import (
    OutreachChannel,
    OutreachContactReference,
    OutreachPreview,
)
from constructionsight.outreach_preview_service import build_persisted_outreach_preview
from constructionsight.storage.operator_read_store import create_operator_read_engine

_FIELDS = {
    "outreach": frozenset({
        "workflow_id", "expected_current_status", "channel", "destination",
        "business_role", "source_name", "source_reference", "contact_review_basis",
        "subject", "body",
    }),
    "bid_request": frozenset({
        "workflow_id", "expected_current_status", "request_channel",
        "requester_business_name", "requester_business_role", "request_source_name",
        "request_source_reference", "request_review_basis", "request_observed_at",
        "request_text", "scope_summary",
    }),
    "pricing": frozenset({
        "request_evidence", "currency_code", "line_items", "assumptions",
        "exclusions", "validity_note",
    }),
    "proposal": frozenset({
        "request_evidence", "pricing_preview", "proposal_title",
        "cover_note", "additional_terms",
    }),
}


def retained_commercial_preview(
    database: Path | None, *, operation: str, data: dict[str, Any],
) -> dict[str, Any]:
    """Reuse original persisted review boundaries for explicit local previews only."""

    if operation not in _FIELDS or not isinstance(data, dict):
        raise ValueError("unsupported original commercial preview")
    if set(data) != _FIELDS[operation]:
        raise ValueError("commercial preview fields do not match required input")
    if database is None:
        raise ValueError("no original operator database configured")
    if database.is_symlink() or not database.is_file():
        raise ValueError("original operator database must be an existing regular file")
    try:
        engine = create_operator_read_engine(database)
    except (SQLAlchemyError, OSError) as exc:
        raise ValueError("original commercial evidence store is unavailable") from exc
    try:
        with Session(engine, autoflush=False) as session:
            preview: OutreachPreview | BidRequestEvidence | BidPricingPreview | BidProposalDraft
            if operation == "outreach":
                contact = OutreachContactReference(
                    channel=OutreachChannel(_string(data, "channel")),
                    destination=_string(data, "destination"),
                    business_role=_string(data, "business_role"),
                    source_name=_string(data, "source_name"),
                    source_reference=_string(data, "source_reference"),
                    contact_review_basis=_string(data, "contact_review_basis"),
                )
                preview = build_persisted_outreach_preview(
                    session, workflow_id=_string(data, "workflow_id"),
                    expected_current_status=LeadWorkflowStatus(
                        _string(data, "expected_current_status")
                    ),
                    contact=contact, subject=_string(data, "subject"),
                    body=_string(data, "body"),
                )
            elif operation == "bid_request":
                observed_at = datetime.fromisoformat(_string(data, "request_observed_at"))
                preview = build_persisted_bid_request_evidence(
                    session, workflow_id=_string(data, "workflow_id"),
                    expected_current_status=LeadWorkflowStatus(
                        _string(data, "expected_current_status")
                    ),
                    request_channel=BidRequestChannel(_string(data, "request_channel")),
                    requester_business_name=_string(data, "requester_business_name"),
                    requester_business_role=_string(data, "requester_business_role"),
                    request_source_name=_string(data, "request_source_name"),
                    request_source_reference=_string(data, "request_source_reference"),
                    request_review_basis=_string(data, "request_review_basis"),
                    request_observed_at=observed_at,
                    request_text=_string(data, "request_text"),
                    scope_summary=_string(data, "scope_summary"),
                )
            elif operation == "pricing":
                raw_lines = data["line_items"]
                if not isinstance(raw_lines, list) or len(raw_lines) > 100:
                    raise ValueError("pricing lines must be a bounded array")
                preview = build_persisted_bid_pricing_preview(
                    session,
                    request_evidence=BidRequestEvidence.model_validate(
                        data["request_evidence"]
                    ),
                    currency_code=_string(data, "currency_code"),
                    line_items=[BidPriceLineInput.model_validate(line) for line in raw_lines],
                    assumptions=_strings(data, "assumptions"),
                    exclusions=_strings(data, "exclusions"),
                    validity_note=_string(data, "validity_note"),
                )
            else:
                preview = build_persisted_bid_proposal_draft(
                    session,
                    request_evidence=BidRequestEvidence.model_validate(
                        data["request_evidence"]
                    ),
                    pricing_preview=BidPricingPreview.model_validate(
                        data["pricing_preview"]
                    ),
                    proposal_title=_string(data, "proposal_title"),
                    cover_note=_string(data, "cover_note"),
                    additional_terms=_strings(data, "additional_terms"),
                )
            return {
                "operation": operation,
                "read_only": True,
                "network_executed": False,
                "outreach_sent": False,
                "bid_submitted": False,
                "native_commercial_authority_created": False,
                "preview": preview.to_dict(),
            }
    except SQLAlchemyError as exc:
        raise ValueError("original commercial evidence read failed") from exc
    finally:
        engine.dispose()


def _string(data: dict[str, Any], field: str) -> str:
    result = data[field]
    if not isinstance(result, str):
        raise ValueError(f"{field} must be text")
    return result


def _strings(data: dict[str, Any], field: str) -> list[str]:
    value = data[field]
    if not isinstance(value, list) or len(value) > 100 or not all(
        isinstance(entry, str) for entry in value
    ):
        raise ValueError(f"{field} must be a bounded list of text")
    return value
