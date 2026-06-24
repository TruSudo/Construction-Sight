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
            public_url=_validate_http_url(source_url),
            url_reachable=self.reachable,
            portal_type_detected=PlatformFamily.CEQANET,
            public_search_available=self.advanced_search_available,
            login_required=False if self.reachable else None,
            permit_details_visible=None,
            agenda_packets_visible=None,
            pdfs_downloadable=None,
            contractor_owner_applicant_fields_visible=None,
            evidence_snapshot_text=(
                "CEQAnet advanced-search discovery: "
                f"url={self.url}; "
                f"status_code={self.status_code}; "
                f"advanced_search_available={self.advanced_search_available}; "
                f"sch_number_field_detected={self.sch_number_field_detected}; "
                f"document_type_field_detected={self.document_type_field_detected}; "
                f"date_field_detected={self.date_field_detected}; "
                f"lead_agency_field_detected={self.lead_agency_field_detected}"
            ),
            confidence_score=self.confidence_score,
            notes=self.notes or "Public CEQAnet advanced-search discovery completed.",
            raw_observations={
                "discovery_url": self.url,
                "status_code": self.status_code,
                "reachable": self.reachable,
                "advanced_search_available": self.advanced_search_available,
                "sch_number_field_detected": self.sch_number_field_detected,
                "document_type_field_detected": self.document_type_field_detected,
                "date_field_detected": self.date_field_detected,
                "lead_agency_field_detected": self.lead_agency_field_detected,
                "confidence_score": self.confidence_score,
            },
        )


class CeqanetFixtureParser:
    """Parse CEQAnet-like fixture dictionaries into normalized records."""

    def parse_row(self, row: dict[str, Any], source_name: str, source_url: str) -> CeqaRecord:
        """Convert one CEQAnet-like row into a normalized CEQA record."""

        sch_number = self._clean(row.get("sch_number"))
        title = self._clean(row.get("title")) or "Untitled CEQA Record"
        document_type = self._clean(row.get("document_type"))
        county = self._clean(row.get("county"))
        lead_agency = self._clean(row.get("lead_agency"))
        description = self._clean(row.get("description"))
        project_location = self._clean(row.get("project_location"))
        record_url = self._clean(row.get("record_url")) or source_url

        return CeqaRecord(
            ceqa_key=self._ceqa_key(sch_number, title),
            title=title,
            county=county,
            lead_agency=lead_agency,
            document_type=document_type,
            state_clearinghouse_number=sch_number,
            received_date=self._parse_date(row.get("received_date")),
            posted_date=self._parse_date(row.get("posted_date")),
            project_location=project_location,
            description=description,
            provenance=[
                Provenance(
                    source_name=source_name,
                    source_url=_validate_http_url(record_url),
                    adapter_family=PlatformFamily.CEQANET.value,
                    raw_reference=sch_number,
                    evidence_text=title,
                    confidence_score=85,
                    verified=False,
                    notes=(
                        "Fixture-backed CEQAnet normalization; live verification not yet "
                        "performed."
                    ),
                )
            ],
        )

    @staticmethod
    def _clean(value: Any) -> str | None:
        """Normalize optional string values."""

        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        """Parse an ISO date string when present."""

        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            return None
        return date.fromisoformat(cleaned)

    @staticmethod
    def _ceqa_key(sch_number: str | None, title: str) -> str:
        """Create a stable CEQA key from SCH number or title."""

        if sch_number:
            return f"ceqanet:sch:{sch_number}"
        slug = "-".join(title.lower().split())[:80]
        return f"ceqanet:title:{slug}"


class CeqanetLiveDiscovery:
    """Conservative live discovery for public CEQAnet search metadata."""

    def __init__(
        self, client: CeqanetHttpClient | None = None, timeout_seconds: float = 20.0
    ) -> None:
        self.client = client or httpx.Client(headers={"User-Agent": "ConstructionSight/0.1"})
        self.timeout_seconds = timeout_seconds

    def discover(self) -> CeqanetDiscoveryResult:
        """Fetch the public advanced-search page and detect stable search fields."""

        try:
            response = self.client.get(
                CEQANET_ADVANCED_SEARCH_URL,
                follow_redirects=True,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            return CeqanetDiscoveryResult(
                url=CEQANET_ADVANCED_SEARCH_URL,
                reachable=False,
                status_code=None,
                advanced_search_available=False,
                sch_number_field_detected=False,
                document_type_field_detected=False,
                date_field_detected=False,
                lead_agency_field_detected=False,
                notes=f"HTTP request failed: {exc.__class__.__name__}",
            )

        body = response.text[:50_000].lower()
        reachable = 200 <= response.status_code < 400
        return CeqanetDiscoveryResult(
            url=str(response.url),
            reachable=reachable,
            status_code=response.status_code,
            advanced_search_available=reachable and "advanced" in body and "search" in body,
            sch_number_field_detected="sch" in body and "number" in body,
            document_type_field_detected="document" in body and "type" in body,
            date_field_detected="date" in body,
            lead_agency_field_detected=("lead" in body or "public" in body) and "agency" in body,
            notes="Public CEQAnet advanced-search discovery completed.",
        )


class CeqanetAdapter(SourceAdapter[dict[str, Any], CeqaRecord]):
    """CEQAnet adapter with fixture-backed Phase 6 normalization."""

    platform_family = PlatformFamily.CEQANET

    def __init__(
        self, *args: Any, fixture_rows: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fixture_rows = fixture_rows or []
        self.parser = CeqanetFixtureParser()

    def verify_source(self) -> SourceVerificationResult:
        """Return adapter-level source capability metadata without live querying."""

        return SourceVerificationResult(
            source_name=self.source_name,
            public_url=self.source.public_url,
            url_reachable=False,
            portal_type_detected=PlatformFamily.CEQANET,
            public_search_available=True,
            login_required=False,
            pdfs_downloadable=None,
            confidence_score=40,
            notes=(
                "CEQAnet Phase 6 adapter is fixture-backed; live HTTP verification "
                "remains delegated to SourceVerifier."
            ),
        )

    def discover_live_public_search(self) -> CeqanetDiscoveryResult:
        """Run live public CEQAnet advanced-search discovery without collecting records."""

        access_result = self.preflight()
        if access_result.decision is not AccessDecision.ALLOWED:
            return CeqanetDiscoveryResult(
                url=CEQANET_ADVANCED_SEARCH_URL,
                reachable=False,
                status_code=None,
                advanced_search_available=False,
                sch_number_field_detected=False,
                document_type_field_detected=False,
                date_field_detected=False,
                lead_agency_field_detected=False,
                notes=access_result.reason,
            )
        return CeqanetLiveDiscovery(timeout_seconds=self.context.request_timeout_seconds).discover()

    def discover_search(self) -> list[AdapterSearchDescriptor]:
        """Describe known public CEQAnet search surface."""

        return [
            AdapterSearchDescriptor(
                source_name=self.source_name,
                search_name="CEQAnet Advanced Search",
                public_url=CEQANET_ADVANCED_SEARCH_URL,
                method="GET",
                record_types=["ceqa", "document"],
                notes=(
                    "Public advanced search surface; live query implementation follows "
                    "fixture-backed parser validation."
                ),
            )
        ]

    def list_records(self) -> Iterable[dict[str, Any]]:
        """Return fixture rows for deterministic parser validation."""

        return tuple(self.fixture_rows)

    def extract_record_detail(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return fixture row unchanged until live detail extraction is added."""

        return record

    def normalize(self, record: dict[str, Any]) -> CeqaRecord:
        """Normalize a CEQAnet fixture row into a CEQA record."""

        return self.parser.parse_row(
            record,
            source_name=self.source_name,
            source_url=str(self.source.public_url),
        )
