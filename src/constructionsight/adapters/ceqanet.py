"""CEQAnet adapter implementation.

Phase 6 starts with deterministic fixture-backed parsing and normalization.
Live HTTP querying is intentionally layered on only after the CEQAnet
normalization contract is tested and stable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import httpx
from pydantic import HttpUrl, TypeAdapter

from constructionsight.adapters.base import AdapterSearchDescriptor, SourceAdapter
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.legal import AccessDecision
from constructionsight.models import PlatformFamily, SourceVerificationResult
from constructionsight.provenance import Provenance

CEQANET_ADVANCED_SEARCH_URL = "https://ceqanet.lci.ca.gov/Search/Advanced"
CEQANET_SEARCH_URL = "https://ceqanet.lci.ca.gov/Search"


def _validate_http_url(value: str) -> HttpUrl:
    """Validate a string as a Pydantic HttpUrl."""

    return TypeAdapter(HttpUrl).validate_python(value)


class CeqanetHttpClient(Protocol):
    """Minimal HTTP client protocol for CEQAnet live discovery."""

    def get(self, url: str, *, follow_redirects: bool, timeout: float) -> httpx.Response:
        """Fetch a public URL."""


@dataclass(frozen=True)
class CeqanetDiscoveryResult:
    """Live CEQAnet public search discovery result."""

    url: str
    reachable: bool
    status_code: int | None
    advanced_search_available: bool
    sch_number_field_detected: bool
    document_type_field_detected: bool
    date_field_detected: bool
    lead_agency_field_detected: bool
    notes: str | None = None

    @property
    def confidence_score(self) -> int:
        """Compute conservative confidence from public discovery signals."""

        score = 0
        if self.reachable:
            score += 30
        if self.advanced_search_available:
            score += 25
        for flag in (
            self.sch_number_field_detected,
            self.document_type_field_detected,
            self.date_field_detected,
            self.lead_agency_field_detected,
        ):
            if flag:
                score += 10
        return min(score, 100)

    def to_source_verification_result(
        self,
        *,
        source_name: str,
        source_url: str,
    ) -> SourceVerificationResult:
        """Convert CEQAnet search-surface discovery into persisted verification evidence."""

        return SourceVerificationResult(
            source_name=source_name,
            platform=PlatformFamily.CEQANET,
            url=source_url,
            reachable=self.reachable,
            status_code=self.status_code,
            access_decision=AccessDecision.ALLOWED if self.reachable else AccessDecision.BLOCKED,
            adapter_key="ceqanet",
            confidence_score=self.confidence_score,
            notes=self.notes,
        )


class CeqanetLiveDiscovery:
    """Discover the public CEQAnet search surface without collecting records."""

    def __init__(
        self,
        client: CeqanetHttpClient | None = None,
        *,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.client = client or httpx.Client(headers={"User-Agent": "ConstructionSight/0.1"})
        self.timeout_seconds = timeout_seconds

    def discover(self, url: str = CEQANET_ADVANCED_SEARCH_URL) -> CeqanetDiscoveryResult:
        """Fetch the public advanced search page and detect expected form fields."""

        try:
            response = self.client.get(url, follow_redirects=True, timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            return CeqanetDiscoveryResult(
                url=url,
                reachable=False,
                status_code=None,
                advanced_search_available=False,
                sch_number_field_detected=False,
                document_type_field_detected=False,
                date_field_detected=False,
                lead_agency_field_detected=False,
                notes=f"HTTP error during CEQAnet discovery: {exc.__class__.__name__}",
            )

        body = response.text
        reachable = 200 <= response.status_code < 400
        return CeqanetDiscoveryResult(
            url=str(response.url),
            reachable=reachable,
            status_code=response.status_code,
            advanced_search_available="Advanced Search" in body or "/Search/Advanced" in body,
            sch_number_field_detected='name="Sch"' in body or "name='Sch'" in body,
            document_type_field_detected='name="DocumentType"' in body
            or "name='DocumentType'" in body,
            date_field_detected='name="StartRange"' in body or "name='StartRange'" in body,
            lead_agency_field_detected='name="LeadAgency"' in body
            or "name='LeadAgency'" in body,
            notes=None,
        )


class CeqanetFixtureParser:
    """Normalize CEQAnet-like fixture rows into CEQA records."""

    def parse_rows(
        self,
        rows: Iterable[dict[str, Any]],
        *,
        source_name: str,
        source_url: str,
    ) -> list[CeqaRecord]:
        """Parse multiple CEQAnet-like rows into normalized CEQA records."""

        return [
            self.parse_row(row, source_name=source_name, source_url=source_url) for row in rows
        ]

    def parse_row(
        self,
        row: dict[str, Any],
        *,
        source_name: str,
        source_url: str,
    ) -> CeqaRecord:
        """Parse one CEQAnet-like row into a normalized CEQA record."""

        sch_number = _clean_optional(row.get("sch_number") or row.get("SCH Number"))
        record_url = _clean_optional(row.get("record_url")) or source_url
        return CeqaRecord(
            ceqa_key=_ceqa_key(sch_number=sch_number, title=_clean_text(row.get("title"))),
            title=_clean_text(row.get("title") or row.get("Project Title")),
            state_clearinghouse_number=sch_number,
            document_type=_clean_optional(row.get("document_type") or row.get("Document Type")),
            lead_agency=_clean_optional(row.get("lead_agency") or row.get("Lead Agency")),
            county=_clean_optional(row.get("county") or row.get("County")),
            received_date=_parse_date(row.get("received_date") or row.get("Received")),
            posted_date=_parse_date(row.get("posted_date") or row.get("Posted")),
            project_location=_clean_optional(row.get("project_location") or row.get("Location")),
            description=_clean_optional(row.get("description") or row.get("Description")),
            provenance=Provenance(source_name=source_name, source_url=_validate_http_url(record_url)),
        )


def _clean_text(value: Any) -> str:
    """Return a normalized non-empty text value."""

    if value is None:
        return "Untitled CEQA Project"
    text = str(value).strip()
    return text or "Untitled CEQA Project"


def _clean_optional(value: Any) -> str | None:
    """Return normalized optional text."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: Any) -> date | None:
    """Parse a CEQAnet date-like value when possible."""

    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _ceqa_key(*, sch_number: str | None, title: str) -> str:
    """Build a deterministic CEQA key."""

    if sch_number:
        return f"ceqanet:sch:{sch_number}"
    slug = "-".join(title.lower().split())[:80]
    return f"ceqanet:title:{slug}"


class CeqanetAdapter(SourceAdapter):
    """CEQAnet source adapter shell."""

    key = "ceqanet"
    platform = PlatformFamily.CEQANET

    def search_descriptors(self) -> list[AdapterSearchDescriptor]:
        """Return lawful public CEQAnet search descriptors."""

        return [
            AdapterSearchDescriptor(
                label="CEQAnet advanced search",
                url=CEQANET_ADVANCED_SEARCH_URL,
                supports_live_discovery=True,
                supports_record_collection=False,
            )
        ]
