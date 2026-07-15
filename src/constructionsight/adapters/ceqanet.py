"""Pure CEQAnet parsing and normalization adapter.

Live network execution is intentionally excluded from this module and provided by
``constructionsight.ceqanet_discovery_http``. The imported live-discovery symbols
below are a compatibility re-export only; adapter methods never invoke transport.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from pydantic import HttpUrl, TypeAdapter

from constructionsight.adapters.base import AdapterSearchDescriptor, SourceAdapter
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.ceqanet_discovery_http import (
    CeqanetDiscoveryResult,
    CeqanetLiveDiscovery,
)
from constructionsight.ceqanet_endpoints import (
    CEQANET_ADVANCED_SEARCH_URL,
    CEQANET_SEARCH_URL,
)
from constructionsight.models import PlatformFamily, SourceVerificationResult
from constructionsight.provenance import Provenance


def _validate_http_url(value: str) -> HttpUrl:
    """Validate a string as a Pydantic HttpUrl."""

    return TypeAdapter(HttpUrl).validate_python(value)


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


class CeqanetAdapter(SourceAdapter[dict[str, Any], CeqaRecord]):
    """CEQAnet adapter with fixture-backed normalization and no network authority."""

    platform_family = PlatformFamily.CEQANET

    def __init__(
        self, *args: Any, fixture_rows: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fixture_rows = fixture_rows or []
        self.parser = CeqanetFixtureParser()

    def verify_source(self) -> SourceVerificationResult:
        """Return adapter-level capability metadata without live querying."""

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
                "CEQAnet adapter normalization is deterministic and fixture-backed; "
                "live HTTP verification requires an approved transport operation."
            ),
        )

    def discover_search(self) -> list[AdapterSearchDescriptor]:
        """Describe the known public CEQAnet search surface."""

        return [
            AdapterSearchDescriptor(
                source_name=self.source_name,
                search_name="CEQAnet Advanced Search",
                public_url=CEQANET_ADVANCED_SEARCH_URL,
                method="GET",
                record_types=["ceqa", "document"],
                notes=(
                    "Public advanced search surface; execution is delegated to an "
                    "approved bounded transport module."
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


__all__ = [
    "CEQANET_ADVANCED_SEARCH_URL",
    "CEQANET_SEARCH_URL",
    "CeqanetAdapter",
    "CeqanetDiscoveryResult",
    "CeqanetFixtureParser",
    "CeqanetLiveDiscovery",
]
