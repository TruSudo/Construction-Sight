"""Base adapter contracts for ConstructionSight source integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from constructionsight.legal import AccessDecision, AccessPolicyResult, SourceAccessProfile, evaluate_access
from constructionsight.models import PublicSource, SourceVerificationResult

RawRecord = TypeVar("RawRecord")
NormalizedRecord = TypeVar("NormalizedRecord", bound=BaseModel)


class AdapterCapability(StrEnum):
    """Declared capability supported by a source adapter."""

    VERIFY_SOURCE = "verify_source"
    DISCOVER_SEARCH = "discover_search"
    LIST_RECORDS = "list_records"
    EXTRACT_DETAILS = "extract_details"
    NORMALIZE_RECORDS = "normalize_records"
    STORE_RECORDS = "store_records"


class AdapterOutcome(StrEnum):
    """Execution outcome for adapter operations."""

    SUCCESS = "success"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AdapterError:
    """Structured adapter error."""

    source_name: str
    operation: str
    message: str
    recoverable: bool = True
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class AdapterRunContext:
    """Runtime context shared with adapters."""

    dry_run: bool = True
    max_records: int | None = None
    user_agent: str = "ConstructionSight/0.1 lawful-public-record-research"
    request_timeout_seconds: float = 20.0
    respect_source_rate_limits: bool = True


@dataclass(frozen=True)
class AdapterOperationResult(Generic[NormalizedRecord]):
    """Standard result envelope returned by adapter operations."""

    source_name: str
    operation: str
    outcome: AdapterOutcome
    records: tuple[NormalizedRecord, ...] = field(default_factory=tuple)
    errors: tuple[AdapterError, ...] = field(default_factory=tuple)
    notes: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return true when the operation completed without failure/blocking."""

        return self.outcome in {AdapterOutcome.SUCCESS, AdapterOutcome.PARTIAL}


class AdapterSearchDescriptor(BaseModel):
    """Description of a public search surface discovered by an adapter."""

    source_name: str = Field(min_length=1)
    search_name: str = Field(min_length=1)
    public_url: str = Field(min_length=1)
    method: str = Field(default="GET", min_length=1)
    record_types: list[str] = Field(default_factory=list)
    notes: str | None = None


class SourceAdapter(ABC, Generic[RawRecord, NormalizedRecord]):
    """Abstract base class all source adapters must implement.

    Adapters must verify sources, discover public search surfaces, list public
    records, extract details, and normalize raw records into ConstructionSight's
    domain models. They must run a lawful-access preflight before collection.
    """

    capabilities: tuple[AdapterCapability, ...] = (
        AdapterCapability.VERIFY_SOURCE,
        AdapterCapability.DISCOVER_SEARCH,
        AdapterCapability.LIST_RECORDS,
        AdapterCapability.EXTRACT_DETAILS,
        AdapterCapability.NORMALIZE_RECORDS,
    )

    def __init__(self, source: PublicSource, context: AdapterRunContext | None = None) -> None:
        self.source = source
        self.context = context or AdapterRunContext()

    @property
    def source_name(self) -> str:
        """Return the adapter source name."""

        return self.source.source_name

    def evaluate_access(self, profile: SourceAccessProfile) -> AccessPolicyResult:
        """Evaluate source access before any collection occurs."""

        return evaluate_access(profile)

    def preflight(self, profile: SourceAccessProfile | None = None) -> AccessPolicyResult:
        """Run the required lawful-access preflight for this source."""

        return self.evaluate_access(profile or SourceAccessProfile(public_url=str(self.source.public_url)))

    def blocked_result(self, operation: str, access_result: AccessPolicyResult) -> AdapterOperationResult[NormalizedRecord]:
        """Build a standard blocked result from a failed preflight."""

        outcome = (
            AdapterOutcome.BLOCKED
            if access_result.decision is AccessDecision.BLOCKED
            else AdapterOutcome.SKIPPED
        )
        return AdapterOperationResult(
            source_name=self.source_name,
            operation=operation,
            outcome=outcome,
            errors=(
                AdapterError(
                    source_name=self.source_name,
                    operation=operation,
                    message=access_result.reason,
                    recoverable=access_result.decision is not AccessDecision.BLOCKED,
                ),
            ),
        )

    @abstractmethod
    def verify_source(self) -> SourceVerificationResult:
        """Verify that the source exists and record what public data it exposes."""

    @abstractmethod
    def discover_search(self) -> list[AdapterSearchDescriptor]:
        """Discover public search surfaces and adapter configuration facts."""

    @abstractmethod
    def list_records(self) -> Iterable[RawRecord]:
        """List candidate public records from the source."""

    @abstractmethod
    def extract_record_detail(self, record: RawRecord) -> RawRecord:
        """Extract detailed public information for a candidate record."""

    @abstractmethod
    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Normalize a raw source record into a ConstructionSight domain model."""
