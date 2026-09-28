"""Dry-run executor for CEQAnet read-only listing plans.

This module intentionally performs no network calls. It converts an approved or
blocked listing plan into auditable request-intent evidence so operators can
review exactly what would be requested before any live executor exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingPagePlan,
    CeqanetListingPlan,
)
from constructionsight.adapters.ceqanet_search_contract import (
    CEQANET_ADVANCED_SEARCH_ACTION_URL,
)


@dataclass(frozen=True)
class CeqanetDryRunRequest:
    """One planned request emitted by the dry-run executor."""

    page_number: int
    method: str
    url: str
    params: tuple[tuple[str, str], ...]
    downloads_documents: bool
    mutates_remote_state: bool
    executed: bool = False


@dataclass(frozen=True)
class CeqanetListingDryRunReport:
    """Auditable dry-run output for a CEQAnet listing plan."""

    allowed: bool
    reason: str
    planned_request_count: int
    maximum_records: int
    requests: tuple[CeqanetDryRunRequest, ...]

    @property
    def executed_request_count(self) -> int:
        """Return the number of network requests actually executed by this dry run."""

        return sum(1 for request in self.requests if request.executed)

    @property
    def downloads_documents(self) -> bool:
        """Return true if any planned request would download documents."""

        return any(request.downloads_documents for request in self.requests)

    @property
    def mutates_remote_state(self) -> bool:
        """Return true if any planned request would mutate remote state."""

        return any(request.mutates_remote_state for request in self.requests)


class CeqanetListingDryRunExecutor:
    """Emit request-intent evidence for CEQAnet listing plans without execution."""

    def run(self, plan: CeqanetListingPlan) -> CeqanetListingDryRunReport:
        """Return dry-run evidence for a CEQAnet listing plan."""

        if not plan.allowed:
            return CeqanetListingDryRunReport(
                allowed=False,
                reason=plan.reason,
                planned_request_count=0,
                maximum_records=0,
                requests=(),
            )
        requests = tuple(self._request_from_page(page) for page in plan.pages)
        return CeqanetListingDryRunReport(
            allowed=True,
            reason="CEQAnet listing dry run produced request-intent evidence only.",
            planned_request_count=len(requests),
            maximum_records=plan.maximum_records,
            requests=requests,
        )

    @staticmethod
    def _request_from_page(page: CeqanetListingPagePlan) -> CeqanetDryRunRequest:
        """Convert one page plan into a deterministic dry-run request record."""

        return CeqanetDryRunRequest(
            page_number=page.page_number,
            method=page.method,
            url=_url_with_params(page.search_url, page.params),
            params=page.params,
            downloads_documents=page.downloads_documents,
            mutates_remote_state=page.mutates_remote_state,
        )


def _url_with_params(base_url: str, params: tuple[tuple[str, str], ...]) -> str:
    """Return a deterministic URL preview with encoded query parameters."""

    if base_url != CEQANET_ADVANCED_SEARCH_ACTION_URL:
        raise ValueError("CEQAnet listing base URL is outside the canonical search contract")
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"
