"""Models for serialized authoritative result-ledger operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.result_ledger_models import ResultLedgerRecord


class ResultAuthorityHead(BaseModel):
    """Mutable compare-and-swap pointer to one immutable ledger history tip."""

    workflow_id: str = Field(min_length=1)
    current_ledger_id: str = Field(min_length=1)
    current_revision: int = Field(ge=1)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority head payload."""

        return self.model_dump(mode="json")


class ResultAuthorityEvent(BaseModel):
    """Append-only audit event for one authority-head selection or correction."""

    event_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    previous_ledger_id: str | None = None
    current_ledger_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        """Require a nonblank normalized audit reason."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("result authority reason must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_revision_linkage(self) -> ResultAuthorityEvent:
        """Require root and correction events to match their revision semantics."""

        if self.revision == 1 and self.previous_ledger_id is not None:
            raise ValueError("root result authority event cannot have a previous ledger")
        if self.revision > 1 and self.previous_ledger_id is None:
            raise ValueError("correcting result authority event requires a previous ledger")
        if self.previous_ledger_id == self.current_ledger_id:
            raise ValueError("result authority event must change the ledger selection")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority event payload."""

        return self.model_dump(mode="json")


class ResultAuthoritySnapshot(BaseModel):
    """Read model for one validated result history and its authoritative tip."""

    workflow_id: str = Field(min_length=1)
    current: ResultLedgerRecord
    history: list[ResultLedgerRecord]
    head: ResultAuthorityHead | None = None

    @model_validator(mode="after")
    def require_snapshot_integrity(self) -> ResultAuthoritySnapshot:
        """Require the current result and optional persisted head to agree."""

        if not self.history:
            raise ValueError("result authority snapshot requires history")
        if self.current.workflow_id != self.workflow_id:
            raise ValueError("result authority snapshot workflow mismatch")
        if self.history[-1].ledger_id != self.current.ledger_id:
            raise ValueError("result authority snapshot current result must be history tip")
        if self.head is not None:
            if self.head.workflow_id != self.workflow_id:
                raise ValueError("result authority head workflow mismatch")
            if self.head.current_ledger_id != self.current.ledger_id:
                raise ValueError("result authority head ledger mismatch")
            if self.head.current_revision != self.current.revision:
                raise ValueError("result authority head revision mismatch")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority snapshot payload."""

        return self.model_dump(mode="json")


class ResultAuthorityApplyReport(BaseModel):
    """Outcome of one governed initial result or correction operation."""

    previous_ledger_id: str | None = None
    current: ResultLedgerRecord
    head: ResultAuthorityHead
    event: ResultAuthorityEvent

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe apply report payload."""

        return self.model_dump(mode="json")
