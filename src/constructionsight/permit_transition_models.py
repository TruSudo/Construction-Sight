"""Permit snapshot and transition models."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class PermitTransitionKind(StrEnum):
    """Kinds of permit changes ConstructionSight tracks."""

    NEW_RECORD = "new_record"
    STATUS_CHANGED = "status_changed"
    VALUE_CHANGED = "value_changed"
    CONTRACTOR_CHANGED = "contractor_changed"
    DATE_CHANGED = "date_changed"
    SITE_CHANGED = "site_changed"
    DESCRIPTION_CHANGED = "description_changed"


class PermitSnapshot(BaseModel):
    """Point-in-time source-neutral permit record snapshot."""

    snapshot_id: str = ""
    source_key: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    permit_number: str | None = None
    jurisdiction: str | None = None
    county: str | None = None
    apn: str | None = None
    site_key: str | None = None
    permit_type: str | None = None
    work_description: str | None = None
    status: str | None = None
    file_date: date | None = None
    issue_date: date | None = None
    final_date: date | None = None
    expiration_date: date | None = None
    first_seen_date: date | None = None
    job_value: float | None = Field(default=None, ge=0)
    contractor_key: str | None = None
    contractor_group_key: str | None = None
    source_updated_at: datetime | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("permit snapshot limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_some_signal_and_identity(self) -> PermitSnapshot:
        """Require one permit signal and bind identity to exact observation content."""

        if not any(
            [
                self.permit_number,
                self.status,
                self.work_description,
                self.file_date,
                self.issue_date,
                self.final_date,
                self.job_value is not None,
            ]
        ):
            raise ValueError("permit snapshot requires at least one permit signal")
        expected = self.computed_snapshot_id()
        if not self.snapshot_id:
            self.snapshot_id = expected
        elif self.snapshot_id != expected:
            raise ValueError("snapshot_id does not match canonical snapshot content")
        return self

    def computed_snapshot_id(self) -> str:
        """Return a full content identity for this exact observation."""

        payload = self.model_dump(mode="json", exclude={"snapshot_id"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"permit-snapshot:v2:{digest}"

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe snapshot payload."""

        return self.model_dump(mode="json")


class PermitTransition(BaseModel):
    """One detected transition between permit snapshots."""

    transition_id: str = ""
    transition_kind: PermitTransitionKind
    source_key: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    previous_snapshot_id: str | None = None
    current_snapshot_id: str = Field(min_length=1)
    field_name: str | None = None
    previous_value: str | None = None
    current_value: str | None = None
    reason: str = Field(min_length=1)
    opportunity_relevant: bool = True
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("permit transition limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_change_payload_and_identity(self) -> PermitTransition:
        """Require complete occurrence linkage and canonical transition identity."""

        non_new_transition = self.transition_kind != PermitTransitionKind.NEW_RECORD
        if non_new_transition and self.field_name is None:
            raise ValueError("non-new permit transitions require field_name")
        if non_new_transition and self.previous_snapshot_id is None:
            raise ValueError("non-new permit transitions require previous_snapshot_id")
        expected = self.computed_transition_id()
        if not self.transition_id:
            self.transition_id = expected
        elif self.transition_id != expected:
            raise ValueError("transition_id does not match canonical transition content")
        return self

    def computed_transition_id(self) -> str:
        """Return a full identity for one transition occurrence."""

        payload = {
            "transition_kind": self.transition_kind.value,
            "source_key": self.source_key,
            "source_record_id": self.source_record_id,
            "previous_snapshot_id": self.previous_snapshot_id,
            "current_snapshot_id": self.current_snapshot_id,
            "field_name": self.field_name,
            "previous_value": self.previous_value,
            "current_value": self.current_value,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"permit-transition:v2:{digest}"

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe transition payload."""

        return self.model_dump(mode="json")
