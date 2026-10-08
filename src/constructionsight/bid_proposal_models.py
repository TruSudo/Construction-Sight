"""Internal, non-authorizing Bid Studio proposal draft models."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.bid_pricing_models import BidPriceLine


class BidProposalDraft(BaseModel):
    """Content-bound internal proposal draft before commercial approval."""

    proposal_draft_id: str = ""
    request_evidence_id: str = Field(min_length=1)
    pricing_preview_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    prepared_for_business_name: str = Field(min_length=1, max_length=500)
    requester_business_role: str = Field(min_length=1, max_length=255)
    proposal_title: str = Field(min_length=1, max_length=500)
    cover_note: str = Field(min_length=1, max_length=10_000)
    scope_summary: str = Field(min_length=1, max_length=10_000)
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    pricing_method: str = Field(min_length=1)
    line_items: list[BidPriceLine] = Field(min_length=1, max_length=100)
    subtotal_minor: int = Field(ge=0, le=100_000_000_000)
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    exclusions: list[str] = Field(default_factory=list, max_length=50)
    validity_note: str = Field(min_length=1, max_length=2000)
    additional_terms: list[str] = Field(default_factory=list, max_length=50)
    draft_format: Literal["internal_proposal_draft/v1"] = "internal_proposal_draft/v1"
    requires_commercial_approval: Literal[True] = True
    commercial_terms_authorized: Literal[False] = False
    customer_facing_bid_authorized: Literal[False] = False
    bid_submission_authorized: Literal[False] = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "prepared_for_business_name",
        "requester_business_role",
        "proposal_title",
        "cover_note",
        "scope_summary",
        "pricing_method",
        "validity_note",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Reject blank proposal content disguised as whitespace."""

        stripped = value.strip()
        if not stripped:
            raise ValueError("proposal draft text fields must not be blank")
        return stripped

    @field_validator("assumptions", "exclusions", "additional_terms")
    @classmethod
    def require_unique_trimmed_text(cls, values: list[str]) -> list[str]:
        """Normalize and reject duplicate proposal list text."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("proposal draft list values must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("proposal draft list values must be unique")
        return normalized

    @model_validator(mode="after")
    def bind_proposal_identity_and_money(self) -> BidProposalDraft:
        """Require exact pricing math and bind all draft-significant content."""

        keys = [line.line_key for line in self.line_items]
        if len(keys) != len(set(keys)):
            raise ValueError("proposal draft line keys must be unique")
        if self.subtotal_minor != sum(line.amount_minor for line in self.line_items):
            raise ValueError("proposal draft subtotal disagrees with pricing lines")
        expected = self.computed_proposal_draft_id()
        if not self.proposal_draft_id:
            self.proposal_draft_id = expected
        elif self.proposal_draft_id != expected:
            raise ValueError(
                "proposal_draft_id does not match canonical proposal content"
            )
        return self

    def computed_proposal_draft_id(self) -> str:
        """Return deterministic draft identity excluding receipt time and ID."""

        payload = self.model_dump(
            mode="json",
            exclude={"proposal_draft_id", "created_at"},
        )
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return "bid-proposal-draft:v1:" + hashlib.sha256(canonical).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe proposal draft payload."""

        return self.model_dump(mode="json")
