"""Base adapter contract for ConstructionSight source integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from constructionsight.legal import AccessPolicyResult, SourceAccessProfile, evaluate_access
from constructionsight.models import PublicSource, SourceVerificationResult

RawRecord = TypeVar("RawRecord")
NormalizedRecord = TypeVar("NormalizedRecord")


@dataclass(frozen=True)
class AdapterError:
    """Structured non-fatal adapter error."""

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


class SourceAdapter(ABC, Generic[RawRecord, NormalizedRecord]):
    """Abstract base class all source adapters must implement."""

    def __init__(self, source: PublicSource, context: AdapterRunContext | None = None) -> None:
        self.source = source
        self.context = context or AdapterRunContext()

    def evaluate_access(self, profile: SourceAccessProfile) -> AccessPolicyResult:
        """Evaluate source access before any collection occurs."""

        return evaluate_access(profile)

    @abstractmethod
    def verify_source(self) -> SourceVerificationResult:
        """Verify that the source exists and record what public data it exposes."""

    @abstractmethod
    def discover_search(self) -> dict[str, Any]:
        """Discover public search surfaces and adapter configuration facts."""

    @abstractmethod
    def list_records(self) -> Iterable[RawRecord]:
        """List candidate records from the source."""

    @abstractmethod
    def extract_record_detail(self, record: RawRecord) -> RawRecord:
        """Extract detailed public information for a candidate record."""

    @abstractmethod
    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Normalize a raw source record into the ConstructionSight schema."""
