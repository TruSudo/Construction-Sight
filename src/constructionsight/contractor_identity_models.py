"""Contractor identity models for ConstructionSight."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.domain_types import ConfidenceBand, confidence_band


class ContractorIdentityStatus(StrEnum):
    """Normalized contractor identity status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class ContractorSourceKind(StrEnum):
    """Source category for contractor identity evidence."""

    PERMIT_RECORD = "permit_record"
    CSLB = "cslb"
    SHOVELS_STYLE = "shovels_style"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


class ContractorLicense(BaseModel):
    """Normalized contractor license signal."""

    license_number: str = Field(min_length=1)
    license_state: str = Field(default="CA", min_length=2, max_length=2)
    status: ContractorIdentityStatus = ContractorIdentityStatus.UNKNOWN
    classification: str | None = None
    issued_date: date | None = None
    expiration_date: date | None = None
    source_kind: ContractorSourceKind = ContractorSourceKind.UNKNOWN
    limitations: list[str] = Field(default_factory=list)

    @field_validator("license_number")
    @classmethod
    def normalize_license_number(cls, value: str) -> str:
        """Normalize license number spacing."""

        normalized = "".join(part for part in value.strip().split())
        if not normalized:
            raise ValueError("license_number cannot be blank")
        return normalized

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("contractor license limitations must contain unique values")
        return values


class ContractorIdentity(BaseModel):
    """Provider-neutral contractor identity record."""

    contractor_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    source_kind: ContractorSourceKind = ContractorSourceKind.UNKNOWN
    license: ContractorLicense | None = None
    contractor_group_key: str | None = None
    status: ContractorIdentityStatus = ContractorIdentityStatus.UNKNOWN
    primary_trade: str | None = None
    county: str | None = None
    state: str = Field(default="CA", min_length=2, max_length=2)
    confidence_score: int = Field(default=0, ge=0, le=100)
    confidence_band: ConfidenceBand = ConfidenceBand.UNKNOWN
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("display_name", "normalized_name")
    @classmethod
    def reject_blank_names(cls, value: str) -> str:
        """Reject blank contractor names."""

        if not value.strip():
            raise ValueError("contractor names cannot be blank")
        return value

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate reasons or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("contractor identity text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_confidence_consistency(self) -> ContractorIdentity:
        """Require confidence band to match score."""

        expected = confidence_band(self.confidence_score)
        if self.confidence_band != expected:
            raise ValueError("confidence_band must match confidence_score")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe contractor payload."""

        return self.model_dump(mode="json")


class ContractorIdentityResolution(BaseModel):
    """Result of resolving contractor identity from source signals."""

    resolution_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    candidates: list[ContractorIdentity] = Field(default_factory=list)
    primary_contractor_key: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("contractor resolution limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_primary_candidate_consistency(self) -> ContractorIdentityResolution:
        """Require primary key to be among candidates."""

        candidate_keys = {candidate.contractor_key for candidate in self.candidates}
        primary_key_missing = (
            self.primary_contractor_key is not None
            and self.primary_contractor_key not in candidate_keys
        )
        if primary_key_missing:
            raise ValueError("primary_contractor_key must be in candidates")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe resolution payload."""

        return self.model_dump(mode="json")
