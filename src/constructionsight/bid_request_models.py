"""Request-evidence models for request-driven bid preparation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BidRequestChannel(StrEnum):
    """Observed channel through which a prospect requested a bid."""

    EMAIL = "email"
    PHONE = "phone"
    PROCUREMENT_PORTAL = "procurement_portal"
    WEB_FORM = "web_form"
    MEETING = "meeting"
    OTHER = "other"


class BidRequestEvidence(BaseModel):
    """Content-bound proof that a prospect requested a scoped bid."""

    request_evidence_id: str = ""
    workflow_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    workflow_status: str = Field(min_length=1)
    request_channel: BidRequestChannel
    requester_business_name: str = Field(min_length=1, max_length=500)
    requester_business_role: str = Field(min_length=1, max_length=255)
    request_source_name: str = Field(min_length=1, max_length=500)
    request_source_reference: str = Field(min_length=1, max_length=2000)
    request_review_basis: str = Field(min_length=1, max_length=2000)
    request_text: str = Field(min_length=1, max_length=20_000)
    scope_summary: str = Field(min_length=1, max_length=10_000)
    evidence_notes: list[str] = Field(default_factory=list)
    requires_commercial_approval: Literal[True] = True
    pricing_authorized: Literal[False] = False
    bid_preparation_authorized: Literal[False] = False
    bid_submission_authorized: Literal[False] = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "requester_business_name",
        "requester_business_role",
        "request_source_name",
        "request_source_reference",
        "request_review_basis",
        "request_text",
        "scope_summary",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Reject blank request evidence disguised as whitespace."""

        stripped = value.strip()
        if not stripped:
            raise ValueError("bid request evidence fields must not be blank")
        return stripped

    @field_validator("evidence_notes")
    @classmethod
    def require_unique_evidence_notes(cls, values: list[str]) -> list[str]:
        """Reject duplicate evidence-note text."""

        if len(values) != len(set(values)):
            raise ValueError("bid request evidence notes must be unique")
        return values

    @model_validator(mode="after")
    def bind_request_evidence_identity(self) -> BidRequestEvidence:
        """Bind identity to exact request content and fixed no-effect authority."""

        expected = self.computed_request_evidence_id()
        if not self.request_evidence_id:
            self.request_evidence_id = expected
        elif self.request_evidence_id != expected:
            raise ValueError(
                "request_evidence_id does not match canonical bid request content"
            )
        return self

    def computed_request_evidence_id(self) -> str:
        """Return deterministic request identity excluding receipt time and ID."""

        payload = self.model_dump(
            mode="json",
            exclude={"request_evidence_id", "created_at"},
        )
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return "bid-request-evidence:v1:" + hashlib.sha256(canonical).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe request-evidence payload."""

        return self.model_dump(mode="json")
