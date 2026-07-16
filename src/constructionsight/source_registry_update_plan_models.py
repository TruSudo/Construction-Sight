"""Source registry update plan models."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SourceRegistryUpdatePlanRow(BaseModel):
    """Dry-run registry update plan row."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    current_verification_status: str = Field(min_length=1)
    proposed_verification_status: str | None = None
    planned_action: str = Field(min_length=1)
    update_required: bool
    original_source_payload: dict[str, Any] = Field(default_factory=dict)
    proposed_source_payload: dict[str, Any] | None = None
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations", "evidence_refs")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate text values."""

        if len(values) != len(set(values)):
            raise ValueError("registry update plan text lists must contain unique values")
        return values


class SourceRegistryUpdatePlanReport(BaseModel):
    """Aggregated dry-run registry update plan."""

    source_count: int = Field(ge=0)
    update_count: int = Field(ge=0)
    action_counts: dict[str, int] = Field(default_factory=dict)
    registry_digest: str = Field(min_length=64, max_length=64)
    plan_digest: str = Field(min_length=64, max_length=64)
    rows: list[SourceRegistryUpdatePlanRow] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_rows(
        cls,
        rows: list[SourceRegistryUpdatePlanRow],
        *,
        registry_digest: str,
    ) -> SourceRegistryUpdatePlanReport:
        """Build plan summary counts and a stable approval digest from rows."""

        return cls(
            source_count=len(rows),
            update_count=sum(1 for row in rows if row.update_required),
            action_counts=dict(Counter(row.planned_action for row in rows)),
            registry_digest=registry_digest,
            plan_digest=compute_source_registry_update_plan_digest(
                rows,
                registry_digest=registry_digest,
            ),
            rows=rows,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report payload."""

        return self.model_dump(mode="json")


def compute_source_registry_update_plan_digest(
    rows: list[SourceRegistryUpdatePlanRow],
    *,
    registry_digest: str,
) -> str:
    """Return a deterministic digest for approval-significant plan content."""

    canonical_payload = {
        "registry_digest": registry_digest,
        "rows": [row.model_dump(mode="json", exclude={"generated_at"}) for row in rows],
    }
    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
