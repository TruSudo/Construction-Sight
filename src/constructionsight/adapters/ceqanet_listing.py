"""CEQAnet read-only listing planning primitives.

This module plans bounded public listing requests only. It does not execute HTTP
requests, submit forms, download documents, parse live HTML, or mutate storage.
It exists to keep the future live CEQAnet listing implementation narrow,
auditable, and gated by access policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from constructionsight.adapters.ceqanet_search_contract import (
    CEQANET_ADVANCED_SEARCH_ACTION_URL,
    build_ceqanet_advanced_search_params,
)
from constructionsight.legal import AccessDecision, AccessPolicyResult


@dataclass(frozen=True)
class CeqanetListingQuery:
    """Bounded query contract for future CEQAnet read-only listing."""

    counties: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    lead_agencies: tuple[str, ...] = ()
    text_terms: tuple[str, ...] = ()
    received_from: date | None = None
    received_to: date | None = None
    posted_from: date | None = None
    posted_to: date | None = None
    high_signal_only: bool = False
    page_size: int = 25
    max_pages: int = 1

    def __post_init__(self) -> None:
        """Validate safety bounds before a listing plan can be created."""

        if not 1 <= self.page_size <= 100:
            raise ValueError("CEQAnet listing page_size must be between 1 and 100")
        if not 1 <= self.max_pages <= 10:
            raise ValueError("CEQAnet listing max_pages must be between 1 and 10")
        if self.text_terms:
            raise ValueError(
                "CEQAnet listing text_terms are unsupported by the verified search contract"
            )
        if self.received_from and self.received_to and self.received_from > self.received_to:
            raise ValueError("received_from must be on or before received_to")
        if self.posted_from and self.posted_to and self.posted_from > self.posted_to:
            raise ValueError("posted_from must be on or before posted_to")
        if not self.has_bounding_filter:
            raise ValueError("CEQAnet listing requires at least one bounding query filter")

    @property
    def has_bounding_filter(self) -> bool:
        """Return true when the query is narrow enough for bounded read-only listing."""

        return any(
            (
                self.counties,
                self.document_types,
                self.lead_agencies,
                self.received_from,
                self.received_to,
                self.posted_from,
                self.posted_to,
                self.high_signal_only,
            )
        )

    @property
    def maximum_records(self) -> int:
        """Return the maximum records the plan may request."""

        return self.page_size * self.max_pages


@dataclass(frozen=True)
class CeqanetListingPagePlan:
    """One planned public listing page request."""

    method: Literal["GET"]
    search_url: str
    page_number: int
    page_size: int
    params: tuple[tuple[str, str], ...]
    downloads_documents: bool = False
    mutates_remote_state: bool = False


@dataclass(frozen=True)
class CeqanetListingPlan:
    """Access-gated CEQAnet listing plan."""

    query: CeqanetListingQuery
    access_result: AccessPolicyResult
    pages: tuple[CeqanetListingPagePlan, ...]
    reason: str

    @property
    def allowed(self) -> bool:
        """Return true when the plan is allowed to run."""

        return self.access_result.decision is AccessDecision.ALLOWED and bool(self.pages)

    @property
    def maximum_records(self) -> int:
        """Return the plan-level maximum record count."""

        return self.query.maximum_records if self.allowed else 0


class CeqanetReadOnlyListingPlanner:
    """Build conservative read-only CEQAnet listing plans."""

    def build_plan(
        self,
        query: CeqanetListingQuery,
        access_result: AccessPolicyResult,
    ) -> CeqanetListingPlan:
        """Build page plans only after lawful-access preflight allows collection."""

        if access_result.decision is not AccessDecision.ALLOWED:
            return CeqanetListingPlan(
                query=query,
                access_result=access_result,
                pages=(),
                reason=access_result.reason,
            )
        pages = tuple(
            CeqanetListingPagePlan(
                method="GET",
                search_url=CEQANET_ADVANCED_SEARCH_ACTION_URL,
                page_number=page_number,
                page_size=query.page_size,
                params=self._params_for_page(query, page_number),
            )
            for page_number in range(1, query.max_pages + 1)
        )
        return CeqanetListingPlan(
            query=query,
            access_result=access_result,
            pages=pages,
            reason="CEQAnet read-only listing plan approved by access preflight.",
        )

    def _params_for_page(
        self,
        query: CeqanetListingQuery,
        page_number: int,
    ) -> tuple[tuple[str, str], ...]:
        """Create deterministic query parameters for one planned listing page."""

        params = list(
            build_ceqanet_advanced_search_params(
                counties=query.counties,
                document_types=query.document_types,
                lead_agencies=query.lead_agencies,
                start_range=query.received_from,
                end_range=query.received_to,
                state_review_period_end=query.posted_from,
                public_review_period_end=query.posted_to,
                high_signal_only=query.high_signal_only,
            )
        )
        if query.max_pages > 1:
            params.append(("page", str(page_number)))
        return tuple(params)
