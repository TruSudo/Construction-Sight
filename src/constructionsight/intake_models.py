"""Universal intake domain models.

These models encode Exhaustive Lawful Intake and Progressive Understanding as a
finite, source-neutral contract. They accept lawful digital evidence by format
family, preserve provenance, distinguish extracted facts from unmapped evidence,
and route unfamiliar structures for review or adapter development.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class DigitalFormatFamily(StrEnum):
    """Finite high-level digital evidence format families."""

    PLAIN_TEXT = "plain_text"
    HTML = "html"
    XML = "xml"
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    TSV = "tsv"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    ZIP = "zip"
    EMAIL = "email"
    IMAGE = "image"
    MEDIA = "media"
    SQLITE = "sqlite"
    BINARY = "binary"
    UNKNOWN = "unknown"


class IntakeUnderstandingStatus(StrEnum):
    """How well the system currently understands an intake item."""

    PRESERVED_ONLY = "preserved_only"
    FORMAT_DETECTED = "format_detected"
    PARTIALLY_UNDERSTOOD = "partially_understood"
    STRUCTURED = "structured"
    ADAPTER_READY = "adapter_ready"
    UNSUPPORTED = "unsupported"


class IntakeRouting(StrEnum):
    """Next route for an intake item."""

    GENERIC_EXTRACTION = "generic_extraction"
    SOURCE_ADAPTER = "source_adapter"
    HUMAN_REVIEW = "human_review"
    ADAPTER_BACKLOG = "adapter_backlog"
    OPPORTUNITY_INTAKE = "opportunity_intake"
    ARCHIVE_ONLY = "archive_only"
    REJECT = "reject"


class MaterialFactKind(StrEnum):
    """Common construction-intelligence fact kinds extractable across sources."""

    ADDRESS = "address"
    APN = "apn"
    SCH_NUMBER = "sch_number"
    PERMIT_NUMBER = "permit_number"
    CSLB_LICENSE = "cslb_license"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    MONEY = "money"
    DATE = "date"
    AGENCY = "agency"
    PROJECT_TITLE = "project_title"
    PERSON_OR_ORGANIZATION = "person_or_organization"
    KEYWORD = "keyword"
    UNKNOWN = "unknown"


class FactConfidence(StrEnum):
    """Confidence classification for extracted material facts."""

    VERIFIED = "verified"
    SOURCE_CLAIMED = "source_claimed"
    INFERRED = "inferred"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class FormatDetection(BaseModel):
    """Binary and structural format-detection result."""

    format_family: DigitalFormatFamily
    media_type: str | None = None
    encoding: str | None = None
    detector_name: str = Field(default="universal_intake_detector.v1", min_length=1)
    detector_version: str = Field(default="1", min_length=1)
    matched_signals: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("matched_signals", "limitations")
    @classmethod
    def require_unique_values(cls, values: list[str]) -> list[str]:
        """Keep detection signals deterministic."""

        if len(values) != len(set(values)):
            raise ValueError("format detection lists must contain unique values")
        return values


class IntakeEvidenceRef(BaseModel):
    """Evidence-preservation reference for one lawful intake item."""

    evidence_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_family: str | None = None
    source_url: str | None = None
    original_filename: str | None = None
    snapshot_path: str | None = None
    observed_at: datetime = Field(default_factory=utc_now)
    byte_count: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    access_method: str = Field(default="lawful_input", min_length=1)
    lawful_basis: str = Field(default="public_or_user_provided", min_length=1)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("sha256")
    @classmethod
    def require_lower_hex_sha256(cls, value: str) -> str:
        """Require deterministic lower-case SHA-256 strings."""

        if value != value.lower() or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must be lower-case hexadecimal")
        return value

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("limitations must contain unique values")
        return values


class ExtractedMaterialFact(BaseModel):
    """One extracted fact from a source-neutral intake item."""

    fact_id: str = Field(min_length=1)
    fact_kind: MaterialFactKind
    value: str = Field(min_length=1)
    normalized_value: str | None = None
    confidence: FactConfidence = FactConfidence.SOURCE_CLAIMED
    evidence_id: str = Field(min_length=1)
    extractor_name: str = Field(default="generic_intake_extractor.v1", min_length=1)
    source_field: str | None = None
    context: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate fact limitations."""

        if len(values) != len(set(values)):
            raise ValueError("limitations must contain unique values")
        return values


class UnmappedEvidenceFragment(BaseModel):
    """Evidence fragment preserved because no safe mapping exists yet."""

    fragment_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    preview: str | None = None
    suggested_adapter_family: str | None = None
    review_required: bool = True


class UniversalIntakeRecord(BaseModel):
    """Source-neutral intake result before lead/opportunity normalization."""

    intake_id: str = Field(min_length=1)
    evidence: IntakeEvidenceRef
    format_detection: FormatDetection
    understanding_status: IntakeUnderstandingStatus
    routing: IntakeRouting
    extracted_facts: list[ExtractedMaterialFact] = Field(default_factory=list)
    unmapped_fragments: list[UnmappedEvidenceFragment] = Field(default_factory=list)
    source_hints: dict[str, str] = Field(default_factory=dict)
    record_hints: dict[str, str] = Field(default_factory=dict)
    adapter_candidate: str | None = None
    next_action: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def require_status_to_match_payload(self) -> UniversalIntakeRecord:
        """Ensure understanding status honestly reflects extracted payload."""

        if self.understanding_status == IntakeUnderstandingStatus.PRESERVED_ONLY and self.extracted_facts:
            raise ValueError("preserved-only intake cannot contain extracted facts")
        if self.routing == IntakeRouting.OPPORTUNITY_INTAKE and not self.extracted_facts:
            raise ValueError("opportunity intake requires extracted facts")
        if self.routing in {IntakeRouting.HUMAN_REVIEW, IntakeRouting.ADAPTER_BACKLOG} and not (
            self.unmapped_fragments or self.extracted_facts
        ):
            raise ValueError("review/backlog routing requires facts or unmapped fragments")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe intake payload."""

        return self.model_dump(mode="json")
