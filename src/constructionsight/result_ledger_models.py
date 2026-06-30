"""Result ledger models for reviewed leads."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ResultLedgerStatus(StrEnum):
    """Outcome status for a reviewed lead."""

    OPEN = "open"
    WON = "won"
    LOST = "lost"
    NO_FIT = "no_fit"
    UNKNOWN = "unknown"


class ResultShareStatus(StrEnum):
    """Share calculation state for a result ledger record."""

    NOT_APPLICABLE = "not_applicable"
    PENDING_GROSS_VALUE = "pending_gross_value"
    PENDING_SHARE_RATE = "pending_share_rate"
    CALCULATED = "calculated"


class ResultShareRecord(BaseModel):
    """Calculated share record for a successful outcome."""

    share_record_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    gross_value: float = Field(ge=0)
    share_rate: float = Field(ge=0, le=1)
    share_value: float = Field(ge=0)
    notes: list[str] = Field(default_factory=list)

    @field_validator("notes")
    @classmethod
    def require_unique_notes(cls, values: list[str]) -> list[str]:
        """Reject duplicate notes."""

        if len(values) != len(set(values)):
            raise ValueError("share notes must contain unique values")
        return values

    @model_validator(mode="after")
    def require_share_math(self) -> ResultShareRecord:
        """Require share value to match gross value and rate."""

        expected = round(self.gross_value * self.share_rate, 2)
        if round(self.share_value, 2) != expected:
            raise ValueError("share_value must equal gross_value times share_rate")
        return self


class ResultLedgerRecord(BaseModel):
    """Outcome ledger row for one lead workflow."""

    ledger_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    status: ResultLedgerStatus
    decided_date: date | None = None
    gross_value: float | None = Field(default=None, ge=0)
    share_status: ResultShareStatus = ResultShareStatus.NOT_APPLICABLE
    share: ResultShareRecord | None = None
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate reasons or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("ledger text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_status_payload_consistency(self) -> ResultLedgerRecord:
        """Keep outcome and share fields consistent with status."""

        if self.status != ResultLedgerStatus.WON:
            if self.share is not None:
                raise ValueError("share records require won status")
            if self.share_status != ResultShareStatus.NOT_APPLICABLE:
                raise ValueError("non-won ledgers require not_applicable share status")
            return self
        if self.share is not None:
            if self.share_status == ResultShareStatus.NOT_APPLICABLE:
                self.share_status = ResultShareStatus.CALCULATED
            if self.share_status != ResultShareStatus.CALCULATED:
                raise ValueError("share records require calculated share status")
            return self
        if self.gross_value is None:
            if self.share_status == ResultShareStatus.NOT_APPLICABLE:
                self.share_status = ResultShareStatus.PENDING_GROSS_VALUE
            if self.share_status != ResultShareStatus.PENDING_GROSS_VALUE:
                raise ValueError("won ledger without gross value requires pending_gross_value")
            return self
        if self.share_status == ResultShareStatus.NOT_APPLICABLE:
            self.share_status = ResultShareStatus.PENDING_SHARE_RATE
        if self.share_status != ResultShareStatus.PENDING_SHARE_RATE:
            raise ValueError("won ledger without share requires pending_share_rate")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe ledger payload."""

        return self.model_dump(mode="json")
