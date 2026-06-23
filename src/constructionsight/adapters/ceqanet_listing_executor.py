"""Live read-only executor contract for CEQAnet listing plans.

This module is intentionally narrow. It can execute bounded GET-only listing
plans through an injectable HTTP client, but it does not submit forms, download
CEQA documents, parse live HTML into records, or mutate persistence. Tests use
fake clients so CI performs no live network collection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from constructionsight.adapters.ceqanet_listing import CeqanetListingPlan
from constructionsight.adapters.ceqanet_listing_dry_run import CeqanetListingDryRunExecutor


class CeqanetListingHttpResponse(Protocol):
    """Minimal HTTP response contract needed by the CEQAnet listing executor."""

    status_code: int
    text: str
    url: Any
    headers: Mapping[str, str]


class CeqanetListingHttpClient(Protocol):
    """Minimal HTTP client contract for bounded CEQAnet listing execution."""

    def get(
        self,
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
    ) -> CeqanetListingHttpResponse:
        """Fetch one public read-only URL."""


@dataclass(frozen=True)
class CeqanetListingResponseSnapshot:
    """One bounded response snapshot from a read-only CEQAnet listing request."""

    page_number: int
    method: str
    request_url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    body_text: str
    body_length: int
    body_truncated: bool
    executed: bool
    error: str | None = None

    @property
    def reachable(self) -> bool:
        """Return true when the request received an HTTP success-like response."""

        return self.status_code is not None and 200 <= self.status_code < 400


@dataclass(frozen=True)
class CeqanetListingExecutionReport:
    """Auditable execution report for a bounded CEQAnet listing plan."""

    allowed: bool
    reason: str
    planned_request_count: int
    executed_request_count: int
    successful_response_count: int
    maximum_records: int
    snapshots: tuple[CeqanetListingResponseSnapshot, ...]

    @property
    def failed_response_count(self) -> int:
        """Return the number of executed requests that did not reach a success response."""

        return self.executed_request_count - self.successful_response_count


class CeqanetListingReadOnlyExecutor:
    """Execute CEQAnet listing plans through bounded read-only GET requests."""

    def __init__(
        self,
        client: CeqanetListingHttpClient | None = None,
        *,
        timeout_seconds: float = 20.0,
        max_body_chars: int = 50_000,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("CEQAnet listing executor timeout_seconds must be greater than 0")
        if max_body_chars < 1:
            raise ValueError("CEQAnet listing executor max_body_chars must be at least 1")
        self.client = client or httpx.Client(headers={"User-Agent": "ConstructionSight/0.1"})
        self.timeout_seconds = timeout_seconds
        self.max_body_chars = max_body_chars

    def run(self, plan: CeqanetListingPlan) -> CeqanetListingExecutionReport:
        """Execute a bounded, access-approved CEQAnet listing plan."""

        if not plan.allowed:
            return CeqanetListingExecutionReport(
                allowed=False,
                reason=plan.reason,
                planned_request_count=0,
                executed_request_count=0,
                successful_response_count=0,
                maximum_records=0,
                snapshots=(),
            )
        dry_run_report = CeqanetListingDryRunExecutor().run(plan)
        if dry_run_report.downloads_documents:
            raise ValueError("CEQAnet listing executor refuses document-download plans")
        if dry_run_report.mutates_remote_state:
            raise ValueError("CEQAnet listing executor refuses remote-mutating plans")

        snapshots = tuple(
            self._execute_request(
                page_number=request.page_number,
                method=request.method,
                url=request.url,
            )
            for request in dry_run_report.requests
        )
        successful_count = sum(1 for snapshot in snapshots if snapshot.reachable)
        return CeqanetListingExecutionReport(
            allowed=True,
            reason="CEQAnet listing executor completed bounded read-only GET requests.",
            planned_request_count=dry_run_report.planned_request_count,
            executed_request_count=len(snapshots),
            successful_response_count=successful_count,
            maximum_records=plan.maximum_records,
            snapshots=snapshots,
        )

    def _execute_request(
        self,
        *,
        page_number: int,
        method: str,
        url: str,
    ) -> CeqanetListingResponseSnapshot:
        """Execute one GET request and convert the response into a bounded snapshot."""

        if method != "GET":
            raise ValueError("CEQAnet listing executor only permits GET requests")
        try:
            response = self.client.get(
                url,
                follow_redirects=True,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            return CeqanetListingResponseSnapshot(
                page_number=page_number,
                method=method,
                request_url=url,
                final_url=url,
                status_code=None,
                content_type=None,
                body_text="",
                body_length=0,
                body_truncated=False,
                executed=True,
                error=exc.__class__.__name__,
            )

        body_text = response.text
        body_length = len(body_text)
        return CeqanetListingResponseSnapshot(
            page_number=page_number,
            method=method,
            request_url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            body_text=body_text[: self.max_body_chars],
            body_length=body_length,
            body_truncated=body_length > self.max_body_chars,
            executed=True,
        )
