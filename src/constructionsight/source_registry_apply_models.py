"""Controlled source registry apply models."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SourceRegistryApplyRow(BaseModel):
    """Auditable result for one source plan row."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    planned_action: str = Field(min_length=1)
    previous_verification_status: str = Field(min_length=1)
    resulting_verification_status: str = Field(min_length=1)
    applied: bool
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    applied_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations", "evidence_refs")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate audit values."""

        if len(values) != len(set(values)):
            raise ValueError("source registry apply text lists must contain unique values")
        return values


class SourceRegistryApplyReport(BaseModel):
    """Auditable outcome of a controlled source registry apply operation."""

    source_count: int = Field(ge=0)
    proposed_update_count: int = Field(ge=0)
    applied_count: int = Field(ge=0)
    action_counts: dict[str, int] = Field(default_factory=dict)
    plan_digest: str = Field(min_length=64, max_length=64)
    original_registry_digest: str = Field(min_length=64, max_length=64)
    updated_registry_digest: str = Field(min_length=64, max_length=64)
    registry_changed: bool
    rows: list[SourceRegistryApplyRow] = Field(default_factory=list)
    applied_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_rows(
        cls,
        *,
        plan_digest: str,
        original_registry_digest: str,
        updated_registry_digest: str,
        rows: list[SourceRegistryApplyRow],
    ) -> SourceRegistryApplyReport:
        """Build an apply report from validated row outcomes."""

        applied_count = sum(1 for row in rows if row.applied)
        return cls(
            source_count=len(rows),
            proposed_update_count=applied_count,
            applied_count=applied_count,
            action_counts=dict(Counter(row.planned_action for row in rows)),
            plan_digest=plan_digest,
            original_registry_digest=original_registry_digest,
            updated_registry_digest=updated_registry_digest,
            registry_changed=original_registry_digest != updated_registry_digest,
            rows=rows,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report payload."""

        return self.model_dump(mode="json")
