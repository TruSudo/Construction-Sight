"""Exact-money, non-authorizing Bid Studio pricing preview models."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BidPriceLineInput(BaseModel):
    """Operator-supplied manual line amount before exact-money normalization."""

    line_key: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=1000)
    pricing_basis: str = Field(min_length=1, max_length=2000)
    amount: str = Field(min_length=1, max_length=100)


class BidPriceLine(BaseModel):
    """Normalized pricing line represented only in currency minor units."""

    line_key: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=1000)
    pricing_basis: str = Field(min_length=1, max_length=2000)
    amount_minor: int = Field(ge=0, le=100_000_000_000)


class BidPricingPreview(BaseModel):
    """Content-bound manual pricing preview with no customer-facing authority."""

    pricing_preview_id: str = ""
    request_evidence_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    pricing_method: Literal["manual_line_amounts/v1"] = "manual_line_amounts/v1"
    line_items: list[BidPriceLine] = Field(min_length=1, max_length=100)
    subtotal_minor: int | None = Field(default=None, ge=0)
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    exclusions: list[str] = Field(default_factory=list, max_length=50)
    validity_note: str = Field(min_length=1, max_length=2000)
    requires_commercial_approval: Literal[True] = True
    commercial_terms_authorized: Literal[False] = False
    customer_facing_bid_authorized: Literal[False] = False
    bid_submission_authorized: Literal[False] = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("assumptions", "exclusions")
    @classmethod
    def require_unique_trimmed_text(cls, values: list[str]) -> list[str]:
        """Reject duplicate, blank, or padded proposal text."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("pricing preview text values must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("pricing preview text values must be unique")
        return normalized

    @field_validator("validity_note")
    @classmethod
    def strip_validity_note(cls, value: str) -> str:
        """Reject blank validity language."""

        stripped = value.strip()
        if not stripped:
            raise ValueError("pricing preview validity note must not be blank")
        return stripped

    @model_validator(mode="after")
    def bind_pricing_identity_and_math(self) -> BidPricingPreview:
        """Require exact subtotal math, unique lines, and content-bound identity."""

        keys = [line.line_key for line in self.line_items]
        if len(keys) != len(set(keys)):
            raise ValueError("pricing preview line keys must be unique")
        expected_subtotal = sum(line.amount_minor for line in self.line_items)
        if self.subtotal_minor is None:
            self.subtotal_minor = expected_subtotal
        elif self.subtotal_minor != expected_subtotal:
            raise ValueError("pricing preview subtotal disagrees with line amounts")

        expected_id = self.computed_pricing_preview_id()
        if not self.pricing_preview_id:
            self.pricing_preview_id = expected_id
        elif self.pricing_preview_id != expected_id:
            raise ValueError(
                "pricing_preview_id does not match canonical pricing content"
            )
        return self

    def computed_pricing_preview_id(self) -> str:
        """Return deterministic identity excluding receipt time and stored ID."""

        payload = self.model_dump(
            mode="json",
            exclude={"pricing_preview_id", "created_at"},
        )
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return "bid-pricing-preview:v1:" + hashlib.sha256(canonical).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe pricing preview payload."""

        return self.model_dump(mode="json")
