"""Source readiness workflow models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SourceReadinessStatus(StrEnum):
    """Conservative source-readiness outcome."""

    SEED_ONLY = "seed_only"
    REACHABLE = "reachable"
    BLOCKED = "blocked"
    FAILED = "failed"
    PARTIAL = "partial"
    VERIFIED_CANDIDATE = "verified_candidate"


class HttpReachabilityResult(BaseModel):
    """HTTP reachability result captured during source-readiness checks."""

    checked: bool = False
    reachable: bool | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    method: str | None = None
    final_url: str | None = None
    error: str | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str | None) -> str | None:
        """Normalize HTTP method text."""

        return value.upper() if value else value


class SourceReadinessRow(BaseModel):
    """Readiness row for one public source registry record."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    platform_family: str = Field(min_length=1)
    public_url: str = Field(min_length=1)
    lawful_access_boundary: str = Field(min_length=1)
    verification_status: str = Field(min_length=1)
    adapter_status: str = Field(min_length=1)
    readiness_status: SourceReadinessStatus
    http_reachability: HttpReachabilityResult
    reason: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("source readiness limitations must contain unique values")
        return values


class SourceReadinessReport(BaseModel):
    """Aggregated source-readiness report."""

    source_count: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[SourceReadinessRow] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe report payload."""

        return self.model_dump(mode="json")
