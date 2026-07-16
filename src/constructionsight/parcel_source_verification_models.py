"""Evidence-bound parcel source verification and county coverage models."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.parcel_assurance_models import ParcelEvidenceAuthority
from constructionsight.parcel_source_models import (
    ParcelAccessBoundary,
    ParcelConstantFieldValue,
    ParcelCoverageStatus,
    ParcelFieldMapping,
    ParcelFieldRole,
    ParcelSourceFormat,
)

_EVIDENCE_ID_RE = re.compile(r"^parcel-source-evidence:[0-9a-f]{64}$")


class ParcelSourceEvidenceKind(StrEnum):
    """Kinds of official evidence supporting a source verification profile."""

    OFFICIAL_DATASET_METADATA = "official_dataset_metadata"
    OFFICIAL_SERVICE_SCHEMA = "official_service_schema"
    OFFICIAL_LIMITATION = "official_limitation"


class ParcelSourceVerificationStatus(StrEnum):
    """Verification maturity without implying acquisition completeness."""

    VERIFIED_PREVIEW = "verified_preview"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


class ParcelCountyCoverageStatus(StrEnum):
    """Countywide source coverage result."""

    READY_FOR_BOUNDED_IMPORT = "ready_for_bounded_import"
    INCOMPLETE = "incomplete"
    REVIEW_REQUIRED = "review_required"


class ParcelCountyCoverageGapCode(StrEnum):
    """Explicit reasons countywide acquisition is not yet ready."""

    SOURCE_REVIEW_REQUIRED = "source_review_required"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    MISSING_AUTHORITATIVE_FIELD = "missing_authoritative_field"
    COUNTYWIDE_RECORD_COVERAGE_UNVERIFIED = "countywide_record_coverage_unverified"
    BULK_ACQUISITION_UNVERIFIED = "bulk_acquisition_unverified"
    INSUFFICIENT_INDEPENDENT_LINEAGES = "insufficient_independent_lineages"


class ParcelSourceEvidence(BaseModel):
    """Immutable digest-bound observation from one official public source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(pattern=r"^parcel-source-evidence:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    evidence_kind: ParcelSourceEvidenceKind
    public_url: str = Field(min_length=1)
    observed_at: datetime
    facts: tuple[str, ...] = Field(min_length=1)
    field_roles: tuple[ParcelFieldRole, ...] = ()
    limitations: tuple[str, ...] = ()

    @field_validator("public_url")
    @classmethod
    def require_https_url(cls, value: str) -> str:
        """Require a public HTTPS evidence reference."""

        if not value.startswith("https://"):
            raise ValueError("parcel source evidence URLs must use HTTPS")
        return value

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        """Require an unambiguous evidence observation time."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("parcel source evidence observed_at must be timezone-aware")
        return value

    @field_validator("facts", "limitations")
    @classmethod
    def require_canonical_text(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require unique, sorted, nonblank evidence statements."""

        if any(not value.strip() for value in values):
            raise ValueError("parcel source evidence statements cannot be blank")
        if tuple(sorted(set(values))) != values:
            raise ValueError("parcel source evidence statements must be unique and sorted")
        return values

    @field_validator("field_roles")
    @classmethod
    def require_canonical_field_roles(
        cls,
        values: tuple[ParcelFieldRole, ...],
    ) -> tuple[ParcelFieldRole, ...]:
        """Require unique field roles in canonical order."""

        if tuple(sorted(set(values), key=lambda role: role.value)) != values:
            raise ValueError("parcel source evidence field roles must be unique and sorted")
        return values

    @model_validator(mode="after")
    def require_digest_identity(self) -> ParcelSourceEvidence:
        """Reject evidence whose ID does not bind its complete content."""

        expected = parcel_source_evidence_id(
            source_key=self.source_key,
            county=self.county,
            evidence_kind=self.evidence_kind,
            public_url=self.public_url,
            observed_at=self.observed_at,
            facts=self.facts,
            field_roles=self.field_roles,
            limitations=self.limitations,
        )
        if self.evidence_id != expected:
            raise ValueError("parcel source evidence ID does not match evidence content")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe evidence."""

        return self.model_dump(mode="json")


class ParcelSourceVerificationProfile(BaseModel):
    """Verified registry-source snapshot with field-specific authority limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(pattern=r"^parcel-source-verification:[0-9a-f]{64}$")
    source_key: str = Field(min_length=1)
    county: str = Field(min_length=1)
    lineage_key: str = Field(min_length=1)
    status: ParcelSourceVerificationStatus
    access_boundary: ParcelAccessBoundary
    coverage_status: ParcelCoverageStatus
    source_format: ParcelSourceFormat
    source_url: str = Field(min_length=1)
    documentation_url: str | None = None
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    schema_fields: tuple[str, ...] = Field(min_length=1)
    field_mappings: tuple[ParcelFieldMapping, ...] = ()
    constant_fields: tuple[ParcelConstantFieldValue, ...] = ()
    default_authority: ParcelEvidenceAuthority = ParcelEvidenceAuthority.OFFICIAL
    authoritative_fields: tuple[ParcelFieldRole, ...] = ()
    public_access_verified: bool
    schema_verified: bool
    county_extent_declared: bool
    countywide_record_coverage_verified: bool
    bulk_acquisition_verified: bool
    max_record_count: int | None = Field(default=None, ge=1)
    spatial_reference: str | None = None
    limitations: tuple[str, ...] = Field(min_length=1)
    next_action: str = Field(min_length=1)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        """Require an unambiguous profile observation time."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("parcel source profile observed_at must be timezone-aware")
        return value

    @field_validator("source_url", "documentation_url")
    @classmethod
    def require_https_profile_urls(cls, value: str | None) -> str | None:
        """Require HTTPS for profile source references."""

        if value is not None and not value.startswith("https://"):
            raise ValueError("parcel source profile URLs must use HTTPS")
        return value

    @field_validator("evidence_ids", "schema_fields", "limitations")
    @classmethod
    def require_canonical_text(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require unique, sorted, nonblank profile collections."""

        if any(not value.strip() for value in values):
            raise ValueError("parcel source profile text values cannot be blank")
        if tuple(sorted(set(values))) != values:
            raise ValueError("parcel source profile text values must be unique and sorted")
        return values

    @field_validator("evidence_ids")
    @classmethod
    def require_evidence_id_format(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require every profile evidence reference to be a digest identity."""

        if any(_EVIDENCE_ID_RE.fullmatch(value) is None for value in values):
            raise ValueError("verification profile evidence IDs must be digest identities")
        return values

    @field_validator("authoritative_fields")
    @classmethod
    def require_canonical_authoritative_fields(
        cls,
        values: tuple[ParcelFieldRole, ...],
    ) -> tuple[ParcelFieldRole, ...]:
        """Require unique authoritative field roles in canonical order."""

        if tuple(sorted(set(values), key=lambda role: role.value)) != values:
            raise ValueError("authoritative fields must be unique and sorted")
        return values

    @field_validator("default_authority")
    @classmethod
    def prevent_global_authority(
        cls,
        value: ParcelEvidenceAuthority,
    ) -> ParcelEvidenceAuthority:
        """Require authoritative claims to remain field-specific."""

        if value == ParcelEvidenceAuthority.AUTHORITATIVE:
            raise ValueError("default parcel source authority cannot be authoritative")
        return value

    @model_validator(mode="after")
    def require_profile_consistency(self) -> ParcelSourceVerificationProfile:
        """Keep maturity, mappings, and digest identity honest."""

        mapping_roles = [mapping.field_role for mapping in self.field_mappings]
        mapping_fields = [mapping.source_field.casefold() for mapping in self.field_mappings]
        constant_roles = [constant.field_role for constant in self.constant_fields]
        if len(mapping_roles) != len(set(mapping_roles)):
            raise ValueError("verification profile field mappings must have unique roles")
        if len(mapping_fields) != len(set(mapping_fields)):
            raise ValueError("verification profile field mappings must have unique fields")
        schema_fields = {field.casefold() for field in self.schema_fields}
        if not set(mapping_fields) <= schema_fields:
            raise ValueError("verification profile mappings must exist in the schema snapshot")
        mapping_order = tuple(
            (mapping.field_role.value, mapping.source_field.casefold())
            for mapping in self.field_mappings
        )
        if mapping_order != tuple(sorted(mapping_order)):
            raise ValueError("verification profile field mappings must be sorted")
        if len(constant_roles) != len(set(constant_roles)):
            raise ValueError("verification profile constants must have unique roles")
        if tuple(role.value for role in constant_roles) != tuple(
            sorted(role.value for role in constant_roles)
        ):
            raise ValueError("verification profile constants must be sorted")
        if set(mapping_roles) & set(constant_roles):
            raise ValueError("verification profile roles cannot be mapped and constant")
        available_roles = set(mapping_roles) | set(constant_roles)
        if not set(self.authoritative_fields) <= available_roles:
            raise ValueError("authoritative fields must be available from the source")
        if self.status == ParcelSourceVerificationStatus.VERIFIED_PREVIEW:
            if not self.public_access_verified or not self.schema_verified:
                raise ValueError("verified-preview profiles require access and schema proof")
            if self.coverage_status not in {
                ParcelCoverageStatus.READY_FOR_PREVIEW,
                ParcelCoverageStatus.READY_FOR_IMPORT,
            }:
                raise ValueError("verified-preview profiles require preview-ready coverage")
        if self.coverage_status == ParcelCoverageStatus.READY_FOR_IMPORT and (
            self.status != ParcelSourceVerificationStatus.VERIFIED_PREVIEW
            or not all(
                (
                    self.public_access_verified,
                    self.schema_verified,
                    self.countywide_record_coverage_verified,
                    self.bulk_acquisition_verified,
                )
            )
        ):
            raise ValueError(
                "import-ready coverage requires verified access, schema, countywide, and bulk proof"
            )
        expected = parcel_source_verification_profile_id(
            self.model_dump(mode="json", exclude={"profile_id"})
        )
        if self.profile_id != expected:
            raise ValueError("parcel source verification ID does not match profile content")
        return self

    @property
    def available_fields(self) -> tuple[ParcelFieldRole, ...]:
        """Return every mapped or constant canonical field role."""

        return tuple(
            sorted(
                {
                    *(mapping.field_role for mapping in self.field_mappings),
                    *(constant.field_role for constant in self.constant_fields),
                },
                key=lambda role: role.value,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe profile."""

        return self.model_dump(mode="json")


class ParcelCountyCoverageRequirement(BaseModel):
    """Explicit countywide fact and redundancy requirements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    county: str = Field(min_length=1)
    required_fields: tuple[ParcelFieldRole, ...] = Field(min_length=1)
    authoritative_fields: tuple[ParcelFieldRole, ...] = Field(min_length=1)
    minimum_independent_lineages: int = Field(default=2, ge=1)
    require_countywide_record_coverage: bool = True
    require_bulk_acquisition: bool = True

    @field_validator("required_fields", "authoritative_fields")
    @classmethod
    def require_canonical_fields(
        cls,
        values: tuple[ParcelFieldRole, ...],
    ) -> tuple[ParcelFieldRole, ...]:
        """Require unique required roles in canonical order."""

        if tuple(sorted(set(values), key=lambda role: role.value)) != values:
            raise ValueError("county coverage fields must be unique and sorted")
        return values

    @model_validator(mode="after")
    def require_authority_subset(self) -> ParcelCountyCoverageRequirement:
        """Keep authoritative requirements within the requested fact set."""

        if not set(self.authoritative_fields) <= set(self.required_fields):
            raise ValueError("authoritative fields must be a subset of required fields")
        return self


class ParcelCountyCoverageGap(BaseModel):
    """One explicit countywide readiness gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ParcelCountyCoverageGapCode
    county: str = Field(min_length=1)
    source_keys: tuple[str, ...] = ()
    field_roles: tuple[ParcelFieldRole, ...] = ()
    explanation: str = Field(min_length=1)
    next_action: str = Field(min_length=1)

    @field_validator("source_keys")
    @classmethod
    def require_canonical_source_keys(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require unique source keys in canonical order."""

        if tuple(sorted(set(values))) != values:
            raise ValueError("county coverage source keys must be unique and sorted")
        return values

    @field_validator("field_roles")
    @classmethod
    def require_canonical_gap_fields(
        cls,
        values: tuple[ParcelFieldRole, ...],
    ) -> tuple[ParcelFieldRole, ...]:
        """Require unique gap fields in canonical order."""

        if tuple(sorted(set(values), key=lambda role: role.value)) != values:
            raise ValueError("county coverage gap fields must be unique and sorted")
        return values


class ParcelCountyCoverageReport(BaseModel):
    """Deterministic report of readiness for exhaustive county parcel acquisition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str = Field(pattern=r"^parcel-county-coverage:[0-9a-f]{64}$")
    status: ParcelCountyCoverageStatus
    counties: tuple[str, ...] = Field(min_length=1)
    profile_ids: tuple[str, ...]
    requirements: tuple[ParcelCountyCoverageRequirement, ...] = Field(min_length=1)
    gaps: tuple[ParcelCountyCoverageGap, ...] = ()
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_aware_generated_at(cls, value: datetime) -> datetime:
        """Require an unambiguous report generation time."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("county coverage generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_report_consistency(self) -> ParcelCountyCoverageReport:
        """Keep report status and deterministic identity consistent."""

        requirement_counties = tuple(requirement.county for requirement in self.requirements)
        expected_counties = tuple(sorted(requirement_counties))
        if requirement_counties != expected_counties:
            raise ValueError("county coverage requirements must be sorted by county")
        if self.counties != expected_counties:
            raise ValueError("county coverage counties must match sorted requirements")
        if len({county.casefold() for county in self.counties}) != len(self.counties):
            raise ValueError("county coverage requirements must identify unique counties")
        if tuple(sorted(set(self.profile_ids))) != self.profile_ids:
            raise ValueError("county coverage profile IDs must be unique and sorted")
        gap_order = tuple((gap.county, gap.code.value, gap.explanation) for gap in self.gaps)
        if gap_order != tuple(sorted(gap_order)):
            raise ValueError("county coverage gaps must be canonically sorted")
        if not self.gaps:
            expected_status = ParcelCountyCoverageStatus.READY_FOR_BOUNDED_IMPORT
        elif any(
            gap.code == ParcelCountyCoverageGapCode.SOURCE_REVIEW_REQUIRED for gap in self.gaps
        ):
            expected_status = ParcelCountyCoverageStatus.REVIEW_REQUIRED
        else:
            expected_status = ParcelCountyCoverageStatus.INCOMPLETE
        if self.status != expected_status:
            raise ValueError("county coverage status does not match its gaps")
        expected_id = parcel_county_coverage_report_id(
            self.model_dump(mode="json", exclude={"report_id", "generated_at"})
        )
        if self.report_id != expected_id:
            raise ValueError("county coverage report ID does not match report content")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe coverage report."""

        return self.model_dump(mode="json")


def parcel_source_evidence_id(
    *,
    source_key: str,
    county: str,
    evidence_kind: ParcelSourceEvidenceKind,
    public_url: str,
    observed_at: datetime,
    facts: tuple[str, ...],
    field_roles: tuple[ParcelFieldRole, ...],
    limitations: tuple[str, ...],
) -> str:
    """Return an evidence ID bound to the complete observation."""

    return _digest_id(
        "parcel-source-evidence",
        {
            "source_key": source_key,
            "county": county,
            "evidence_kind": evidence_kind.value,
            "public_url": public_url,
            "observed_at": observed_at.isoformat(),
            "facts": list(facts),
            "field_roles": [role.value for role in field_roles],
            "limitations": list(limitations),
        },
    )


def parcel_source_verification_profile_id(payload: dict[str, Any]) -> str:
    """Return a profile ID bound to all profile content."""

    return _digest_id("parcel-source-verification", payload)


def parcel_county_coverage_report_id(payload: dict[str, Any]) -> str:
    """Return a semantic coverage report ID excluding generation time."""

    return _digest_id("parcel-county-coverage", payload)


def _digest_id(namespace: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{namespace}:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
