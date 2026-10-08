"""Governed outreach-preview models with no external send authority."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class OutreachChannel(StrEnum):
    """Business contact channels that may be represented in a preview."""

    EMAIL = "email"
    PROCUREMENT_PORTAL = "procurement_portal"
    WEB_FORM = "web_form"
    PHONE = "phone"
    OTHER = "other"


class OutreachContactReference(BaseModel):
    """Operator-confirmed business contact path and its provenance."""

    channel: OutreachChannel
    destination: str = Field(min_length=1, max_length=1000)
    business_role: str = Field(min_length=1, max_length=255)
    source_name: str = Field(min_length=1, max_length=500)
    source_reference: str = Field(min_length=1, max_length=2000)
    operator_confirmed_business_contact: bool = False


class OutreachPreview(BaseModel):
    """Immutable-content preview that cannot itself authorize or send outreach."""

    preview_id: str = ""
    workflow_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    workflow_status: str = Field(min_length=1)
    contact: OutreachContactReference
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    evidence_notes: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    external_send_authorized: bool = False
    send_executed: bool = False
    bid_authorized: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_preview_only_boundary(self) -> OutreachPreview:
        """Bind preview identity and forbid effect authority at the model boundary."""

        if not self.requires_human_approval:
            raise ValueError("outreach previews must require human approval")
        if self.external_send_authorized or self.send_executed or self.bid_authorized:
            raise ValueError("outreach preview cannot authorize send or bid effects")
        expected = self.computed_preview_id()
        if not self.preview_id:
            self.preview_id = expected
        elif self.preview_id != expected:
            raise ValueError("preview_id does not match canonical preview content")
        return self

    def computed_preview_id(self) -> str:
        """Return content-bound preview identity excluding receipt time and ID."""

        payload = self.model_dump(
            mode="json",
            exclude={"preview_id", "created_at"},
        )
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return "outreach-preview:v1:" + hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe preview payload."""

        return self.model_dump(mode="json")
