"""Policy-bound CEQAnet advanced-search surface discovery."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pydantic import HttpUrl, TypeAdapter

from constructionsight.ceqanet_endpoints import CEQANET_ADVANCED_SEARCH_URL
from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import (
    BoundedHttpPolicy,
    HttpExecutor,
    HttpFailureKind,
)
from constructionsight.models import PlatformFamily, SourceVerificationResult

CEQANET_DISCOVERY_POLICY = BoundedHttpPolicy(
    policy_id="CS-NET-001",
    allowed_methods=("GET",),
    allowed_hosts=("ceqanet.lci.ca.gov",),
    allowed_path_prefixes=("/Search/Advanced",),
    connect_timeout_seconds=5.0,
    read_timeout_seconds=20.0,
    write_timeout_seconds=5.0,
    pool_timeout_seconds=5.0,
    max_response_bytes=50_000,
    accepted_media_types=("text/html",),
    accepted_encodings=("utf-8", "windows-1252"),
)


def _validate_http_url(value: str) -> HttpUrl:
    return TypeAdapter(HttpUrl).validate_python(value)


@dataclass(frozen=True)
class CeqanetDiscoveryResult:
    """Classified CEQAnet public search discovery result."""

    url: str
    reachable: bool
    status_code: int | None
    advanced_search_available: bool
    sch_number_field_detected: bool
    document_type_field_detected: bool
    date_field_detected: bool
    lead_agency_field_detected: bool
    failure_kind: HttpFailureKind = HttpFailureKind.NONE
    notes: str | None = None

    @property
    def confidence_score(self) -> int:
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
                f"url={self.url}; status_code={self.status_code}; "
                f"failure_kind={self.failure_kind.value}; "
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
                "failure_kind": self.failure_kind.value,
                "advanced_search_available": self.advanced_search_available,
                "sch_number_field_detected": self.sch_number_field_detected,
                "document_type_field_detected": self.document_type_field_detected,
                "date_field_detected": self.date_field_detected,
                "lead_agency_field_detected": self.lead_agency_field_detected,
                "confidence_score": self.confidence_score,
            },
        )


class CeqanetLiveDiscovery:
    """One-attempt, redirect-denying CEQAnet search-surface discovery."""

    def __init__(
        self,
        executor: HttpExecutor | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.executor = executor or execute_bounded_http
        self.policy = replace(
            CEQANET_DISCOVERY_POLICY,
            read_timeout_seconds=timeout_seconds,
        )

    def discover(self) -> CeqanetDiscoveryResult:
        observation = self.executor(
            CEQANET_ADVANCED_SEARCH_URL,
            "GET",
            self.policy,
        )
        if not observation.succeeded:
            return CeqanetDiscoveryResult(
                url=observation.final_url,
                reachable=observation.reachable,
                status_code=observation.status_code,
                advanced_search_available=False,
                sch_number_field_detected=False,
                document_type_field_detected=False,
                date_field_detected=False,
                lead_agency_field_detected=False,
                failure_kind=observation.failure_kind,
                notes=(
                    "CEQAnet discovery failed closed: "
                    f"{observation.failure_kind.value}"
                ),
            )
        body = observation.decode_text(self.policy.accepted_encodings).casefold()
        reachable = observation.status_code is not None and 200 <= observation.status_code < 300
        return CeqanetDiscoveryResult(
            url=observation.final_url,
            reachable=reachable,
            status_code=observation.status_code,
            advanced_search_available=reachable and "advanced" in body and "search" in body,
            sch_number_field_detected="sch" in body and "number" in body,
            document_type_field_detected="document" in body and "type" in body,
            date_field_detected="date" in body,
            lead_agency_field_detected=("lead" in body or "public" in body) and "agency" in body,
            failure_kind=HttpFailureKind.NONE,
            notes="Public CEQAnet advanced-search discovery completed.",
        )
