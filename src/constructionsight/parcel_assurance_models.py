"""Field-level parcel evidence and assurance models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.parcel_source_models import ParcelFieldRole


class ParcelEvidenceAuthority(StrEnum):
    """Evidence authority carried by one field-level claim."""

    AUTHORITATIVE = "authoritative"
    OFFICIAL = "official"
    LICENSED = "licensed"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


class ParcelClaimMethod(StrEnum):
    """How a field-level claim was produced."""

    DIRECT_OBSERVATION = "direct_observation"
    DETERMINISTIC_DERIVATION = "deterministic_derivation"
    INFERENCE = "inference"


class ParcelAssuranceStatus(StrEnum):
    """Field-level assurance outcomes without an opaque global score."""

    AUTHORITATIVE_CORROBORATED = "authoritative_corroborated"
    AUTHORITATIVE_SOURCE = "authoritative_source"
    INDEPENDENTLY_CORROBORATED = "independently_corroborated"
    DEPENDENT_SOURCES_AGREE = "dependent_sources_agree"
    SINGLE_SOURCE = "single_source"
    CONFLICT = "conflict"
    MISSING = "missing"


class ParcelAssuranceReviewStatus(StrEnum):
    """Operator review state for a complete assurance report."""

    EVALUATED = "evaluated"
    INCOMPLETE = "incomplete"
    REVIEW_REQUIRED = "review_required"


class ParcelAssuranceSourceContext(BaseModel):
    """Explicit dependency and authority context for one parcel source."""

    source_key: str = Field(min_length=1)
    lineage_key: str = Field(min_length=1)
    default_authority: ParcelEvidenceAuthority = ParcelEvidenceAuthority.UNKNOWN
    authoritative_fields: list[ParcelFieldRole] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("source_key", "lineage_key")
    @classmethod
    def reject_blank_keys(cls, value: str) -> str:
        """Reject whitespace-only source and lineage keys."""

        if not value.strip():
            raise ValueError("source and lineage keys cannot be blank")
        return value

    @field_validator("default_authority")
    @classmethod
    def require_field_specific_authority(
        cls,
        value: ParcelEvidenceAuthority,
    ) -> ParcelEvidenceAuthority:
        """Prevent one source label from making every field authoritative."""

        if value == ParcelEvidenceAuthority.AUTHORITATIVE:
            raise ValueError("authoritative evidence must be assigned by field")
        return value

    @field_validator("authoritative_fields")
    @classmethod
    def require_unique_authoritative_fields(
        cls,
        values: list[ParcelFieldRole],
    ) -> list[ParcelFieldRole]:
        """Reject duplicate or non-factual authority assignments."""

        unsupported = {
            ParcelFieldRole.SOURCE_RECORD_ID,
            ParcelFieldRole.UPDATED_AT,
            ParcelFieldRole.UNKNOWN,
        }
        if len(values) != len(set(values)):
            raise ValueError("authoritative_fields must contain unique values")
        if any(value in unsupported for value in values):
            raise ValueError("authoritative_fields must identify parcel facts")
        return values

    @field_validator("limitations")
    @classmethod
    def require_unique_source_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate source limitations."""

        if len(values) != len(set(values)):
            raise ValueError("source limitations must contain unique values")
        return values

    def authority_for(self, field_role: ParcelFieldRole) -> ParcelEvidenceAuthority:
        """Return proposition-specific authority for a field role."""

        if field_role in self.authoritative_fields:
            return ParcelEvidenceAuthority.AUTHORITATIVE
        return self.default_authority


class ParcelEvidenceClaim(BaseModel):
    """One retained source claim about one parcel fact."""

    claim_id: str = Field(min_length=1)
    parcel_record_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    source_record_id: str | None = None
    lineage_key: str = Field(min_length=1)
    field_role: ParcelFieldRole
    original_value: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    authority: ParcelEvidenceAuthority
    claim_method: ParcelClaimMethod = ParcelClaimMethod.DIRECT_OBSERVATION
    evidence_reference: str = Field(min_length=1)
    source_effective_at: datetime | None = None
    observed_at: datetime
    limitations: list[str] = Field(default_factory=list)

    @field_validator("field_role")
    @classmethod
    def require_factual_field(cls, value: ParcelFieldRole) -> ParcelFieldRole:
        """Keep source metadata out of parcel fact claims."""

        unsupported = {
            ParcelFieldRole.SOURCE_RECORD_ID,
            ParcelFieldRole.UPDATED_AT,
            ParcelFieldRole.UNKNOWN,
        }
        if value in unsupported:
            raise ValueError("parcel evidence claims require a factual field role")
        return value

    @field_validator("limitations")
    @classmethod
    def require_unique_claim_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate claim limitations."""

        if len(values) != len(set(values)):
            raise ValueError("claim limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def prevent_derived_authority(self) -> ParcelEvidenceClaim:
        """Do not promote derived or inferred output to authoritative evidence."""

        if (
            self.claim_method != ParcelClaimMethod.DIRECT_OBSERVATION
            and self.authority == ParcelEvidenceAuthority.AUTHORITATIVE
        ):
            raise ValueError("derived or inferred claims cannot be authoritative")
        return self


class ParcelAssuranceValueGroup(BaseModel):
    """Claims that agree on one normalized field value."""

    normalized_value: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=1)
    lineage_keys: list[str] = Field(min_length=1)
    authorities: list[ParcelEvidenceAuthority] = Field(min_length=1)

    @field_validator("claim_ids", "lineage_keys", "authorities")
    @classmethod
    def require_unique_group_values(cls, values: list[Any]) -> list[Any]:
        """Keep assurance value groups deterministic."""

        if len(values) != len(set(values)):
            raise ValueError("assurance value-group lists must contain unique values")
        return values


class ParcelFieldAssurance(BaseModel):
    """Explainable assurance outcome for one parcel field."""

    field_role: ParcelFieldRole
    status: ParcelAssuranceStatus
    selected_normalized_value: str | None = None
    claim_ids: list[str] = Field(default_factory=list)
    value_groups: list[ParcelAssuranceValueGroup] = Field(default_factory=list)
    independent_lineage_count: int = Field(ge=0)
    authoritative_claim_count: int = Field(ge=0)
    requires_human_review: bool = False
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("claim_ids", "reasons", "limitations")
    @classmethod
    def require_unique_assurance_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate assurance identifiers and explanations."""

        if len(values) != len(set(values)):
            raise ValueError("assurance lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_status_consistency(self) -> ParcelFieldAssurance:
        """Keep assurance labels consistent with their evidence shape."""

        if self.status == ParcelAssuranceStatus.MISSING:
            if self.claim_ids or self.value_groups or self.selected_normalized_value:
                raise ValueError("missing assurance cannot carry claims or a value")
            if self.independent_lineage_count != 0:
                raise ValueError("missing assurance cannot carry source lineages")
            return self
        if not self.claim_ids or not self.value_groups:
            raise ValueError("non-missing assurance requires claims and value groups")
        if self.status == ParcelAssuranceStatus.CONFLICT:
            if len(self.value_groups) < 2 or not self.requires_human_review:
                raise ValueError("conflict assurance requires values and human review")
            if self.selected_normalized_value is not None:
                raise ValueError("conflict assurance cannot select a value")
            return self
        if len(self.value_groups) != 1 or self.selected_normalized_value is None:
            raise ValueError("agreeing assurance requires exactly one selected value")
        independent_statuses = {
            ParcelAssuranceStatus.AUTHORITATIVE_CORROBORATED,
            ParcelAssuranceStatus.INDEPENDENTLY_CORROBORATED,
        }
        if self.status in independent_statuses and self.independent_lineage_count < 2:
            raise ValueError("corroborated assurance requires independent lineages")
        authoritative_statuses = {
            ParcelAssuranceStatus.AUTHORITATIVE_CORROBORATED,
            ParcelAssuranceStatus.AUTHORITATIVE_SOURCE,
        }
        if self.status in authoritative_statuses and self.authoritative_claim_count < 1:
            raise ValueError("authoritative assurance requires an authoritative claim")
        return self


class ParcelAssuranceReport(BaseModel):
    """Persistable field-by-field assurance report for one parcel identity."""

    report_id: str = Field(min_length=1)
    normalized_apn: str = Field(min_length=1)
    county: str = Field(min_length=1)
    review_status: ParcelAssuranceReviewStatus
    source_count: int = Field(ge=0)
    independent_lineage_count: int = Field(ge=0)
    source_keys: list[str] = Field(default_factory=list)
    lineage_keys: list[str] = Field(default_factory=list)
    claims: list[ParcelEvidenceClaim] = Field(default_factory=list)
    field_assurances: list[ParcelFieldAssurance] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("limitations")
    @classmethod
    def require_unique_report_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate report limitations."""

        if len(values) != len(set(values)):
            raise ValueError("report limitations must contain unique values")
        return values

    @field_validator("source_keys", "lineage_keys")
    @classmethod
    def require_unique_report_keys(cls, values: list[str]) -> list[str]:
        """Reject duplicate evaluated source and lineage keys."""

        if len(values) != len(set(values)):
            raise ValueError("report source and lineage keys must be unique")
        return values

    @model_validator(mode="after")
    def require_report_consistency(self) -> ParcelAssuranceReport:
        """Verify report counts, identity, and review state."""

        claim_ids = [claim.claim_id for claim in self.claims]
        field_roles = [assurance.field_role for assurance in self.field_assurances]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("report claims must have unique claim IDs")
        if len(field_roles) != len(set(field_roles)):
            raise ValueError("report must evaluate each field role at most once")
        if self.source_count != len(self.source_keys):
            raise ValueError("source_count must match evaluated source keys")
        if self.independent_lineage_count != len(self.lineage_keys):
            raise ValueError("independent_lineage_count must match lineage keys")
        if not {claim.source_key for claim in self.claims}.issubset(self.source_keys):
            raise ValueError("report claims must use evaluated source keys")
        if not {claim.lineage_key for claim in self.claims}.issubset(self.lineage_keys):
            raise ValueError("report claims must use evaluated lineage keys")
        expected_review_status = ParcelAssuranceReviewStatus.EVALUATED
        if any(assurance.requires_human_review for assurance in self.field_assurances):
            expected_review_status = ParcelAssuranceReviewStatus.REVIEW_REQUIRED
        elif any(
            assurance.status == ParcelAssuranceStatus.MISSING for assurance in self.field_assurances
        ):
            expected_review_status = ParcelAssuranceReviewStatus.INCOMPLETE
        if self.review_status != expected_review_status:
            raise ValueError("review_status must match field assurance outcomes")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe report payload."""

        return self.model_dump(mode="json")
