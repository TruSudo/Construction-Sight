"""Policy-bound live executor for immutable CEQAnet listing plans.

Every production and deterministic-test execution uses the shared streamed HTTP
engine and denies redirects at request time.
"""

from __future__ import annotations

from dataclasses import dataclass

from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingPlan,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_dry_run import (
    CeqanetDryRunRequest,
    CeqanetListingDryRunExecutor,
)
from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
)


class CeqanetListingExecutionError(RuntimeError):
    """Raised when the listing operation contract is invalid before execution."""


@dataclass(frozen=True)
class CeqanetListingExecutionPolicy:
    """Exact runtime bounds for CS-NET-002."""

    timeout_seconds: float = 20.0
    max_response_bytes: int = 50_000
    max_attempts: int = 1
    retry_delays_seconds: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.timeout_seconds > 20.0:
            raise ValueError("listing timeout must be between 0 and 20 seconds")
        if self.max_response_bytes < 1 or self.max_response_bytes > 50_000:
            raise ValueError("listing response bound must be between 1 and 50000 bytes")
        if self.max_attempts != 1 or self.retry_delays_seconds:
            raise ValueError("CS-NET-002 permits exactly one attempt and no retry delay")

    def http_policy(self, request_url: str) -> BoundedHttpPolicy:
        """Return the complete immutable policy consumed by the shared HTTP engine."""

        return BoundedHttpPolicy(
            policy_id="CS-NET-002",
            allowed_methods=("GET",),
            allowed_hosts=("ceqanet.lci.ca.gov",),
            allowed_path_prefixes=("/Search",),
            connect_timeout_seconds=5.0,
            read_timeout_seconds=self.timeout_seconds,
            write_timeout_seconds=5.0,
            pool_timeout_seconds=5.0,
            max_response_bytes=self.max_response_bytes,
            accepted_media_types=("text/html",),
            accepted_encodings=("utf-8", "windows-1252"),
            user_agent="ConstructionSight-CEQAnetListing/1.0",
            allowed_request_urls=(request_url,),
        )


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
    failure_kind: str = "none"

    @property
    def reachable(self) -> bool:
        """Return true only for a classified, non-error 2xx response."""

        return (
            self.error is None
            and self.status_code is not None
            and 200 <= self.status_code < 300
        )


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
        return self.executed_request_count - self.successful_response_count


class CeqanetListingReadOnlyExecutor:
    """Execute CEQAnet listing plans under one exact CS-NET-002 policy."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_body_chars: int = 50_000,
        policy: CeqanetListingExecutionPolicy | None = None,
    ) -> None:
        if policy is not None and (
            timeout_seconds != 20.0 or max_body_chars != 50_000
        ):
            raise ValueError("provide either a policy or explicit legacy bounds, not both")
        self.policy = policy or CeqanetListingExecutionPolicy(
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_body_chars,
        )

    def run(self, plan: CeqanetListingPlan) -> CeqanetListingExecutionReport:
        """Execute a bounded, access-approved CEQAnet listing plan."""

        canonical_plan = CeqanetReadOnlyListingPlanner().build_plan(
            plan.query,
            plan.access_result,
        )
        if plan != canonical_plan:
            raise CeqanetListingExecutionError(
                "CEQAnet listing plan differs from the canonical planner output"
            )
        dry_run_report = CeqanetListingDryRunExecutor().run(plan)
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
        if dry_run_report.downloads_documents:
            raise CeqanetListingExecutionError(
                "CEQAnet listing executor refuses document-download plans"
            )
        if dry_run_report.mutates_remote_state:
            raise CeqanetListingExecutionError(
                "CEQAnet listing executor refuses remote-mutating plans"
            )
        snapshots = tuple(
            self._execute_request(request) for request in dry_run_report.requests
        )
        successful_count = sum(snapshot.reachable for snapshot in snapshots)
        return CeqanetListingExecutionReport(
            allowed=True,
            reason="CEQAnet listing executor completed policy-bound read-only GET requests.",
            planned_request_count=dry_run_report.planned_request_count,
            executed_request_count=len(snapshots),
            successful_response_count=successful_count,
            maximum_records=plan.maximum_records,
            snapshots=snapshots,
        )

    def _execute_request(
        self,
        request: CeqanetDryRunRequest,
    ) -> CeqanetListingResponseSnapshot:
        if request.method != "GET":
            raise CeqanetListingExecutionError(
                "CEQAnet listing executor only permits GET requests"
            )
        observation = execute_bounded_http(
            request.url,
            request.method,
            self.policy.http_policy(request.url),
        )
        return _snapshot_from_observation(request, observation)


def _snapshot_from_observation(
    request: CeqanetDryRunRequest,
    observation: BoundedHttpObservation,
) -> CeqanetListingResponseSnapshot:
    if (
        observation.body_truncated
        or observation.failure_kind is HttpFailureKind.OVERSIZED_RESPONSE
    ):
        body_text = ""
    else:
        try:
            body_text = observation.decode_text(("utf-8", "windows-1252"))
        except UnicodeError:
            body_text = ""
    error = observation.error_type
    return CeqanetListingResponseSnapshot(
        page_number=request.page_number,
        method=request.method,
        request_url=request.url,
        final_url=observation.final_url,
        status_code=observation.status_code,
        content_type=observation.content_type,
        body_text=body_text,
        body_length=observation.response_size,
        body_truncated=observation.body_truncated,
        executed=True,
        error=error,
        failure_kind=observation.failure_kind.value,
    )


def execute_ceqanet_listing_plan(
    plan: CeqanetListingPlan,
    *,
    policy: CeqanetListingExecutionPolicy,
) -> CeqanetListingExecutionReport:
    """Execute one immutable plan through the approved production transport."""

    return CeqanetListingReadOnlyExecutor(policy=policy).run(plan)
