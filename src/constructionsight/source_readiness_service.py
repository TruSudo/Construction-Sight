"""Conservative source-readiness workflow service."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable

import httpx

from constructionsight.adapters.specs import AdapterFamilySpec, AdapterImplementationStatus
from constructionsight.models import PlatformFamily, PublicSource, VerificationStatus
from constructionsight.source_readiness_models import (
    HttpReachabilityResult,
    SourceReadinessReport,
    SourceReadinessRow,
    SourceReadinessStatus,
)

HttpReachabilityChecker = Callable[[PublicSource], HttpReachabilityResult]


def build_source_readiness_report(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    check_http: bool = False,
    http_checker: HttpReachabilityChecker | None = None,
) -> SourceReadinessReport:
    """Build a conservative source-readiness report without mutating sources."""

    checker = http_checker or check_http_reachability
    rows = [
        _build_row(
            source,
            adapter_specs,
            checker(source) if check_http else HttpReachabilityResult(checked=False),
        )
        for source in sources
    ]
    return SourceReadinessReport(
        source_count=len(rows),
        status_counts=dict(Counter(row.readiness_status.value for row in rows)),
        rows=rows,
    )


def check_http_reachability(source: PublicSource) -> HttpReachabilityResult:
    """Perform a lightweight lawful public HTTP reachability check."""

    url = str(source.public_url)
    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.head(url)
            method = "HEAD"
            if response.status_code == 405:
                response = client.get(url)
                method = "GET"
        return HttpReachabilityResult(
            checked=True,
            reachable=200 <= response.status_code < 400,
            status_code=response.status_code,
            method=method,
            final_url=str(response.url),
        )
    except httpx.HTTPError as exc:
        return HttpReachabilityResult(
            checked=True,
            reachable=False,
            error=exc.__class__.__name__,
        )


def _build_row(
    source: PublicSource,
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    http_result: HttpReachabilityResult,
) -> SourceReadinessRow:
    """Build one source-readiness row."""

    spec = adapter_specs.get(source.platform_family)
    adapter_status = (
        spec.status if spec is not None else AdapterImplementationStatus.PLACEHOLDER
    )
    readiness_status, reason, limitations, next_action = _readiness_decision(
        source.verification_status,
        adapter_status,
        http_result,
    )
    return SourceReadinessRow(
        source_key=_source_key(source),
        source_name=source.source_name,
        platform_family=source.platform_family.value,
        public_url=str(source.public_url),
        lawful_access_boundary=_lawful_access_boundary(spec),
        verification_status=source.verification_status.value,
        adapter_status=adapter_status.value,
        readiness_status=readiness_status,
        http_reachability=http_result,
        reason=reason,
        limitations=limitations,
        next_action=next_action,
    )


def _readiness_decision(
    verification_status: VerificationStatus,
    adapter_status: AdapterImplementationStatus,
    http_result: HttpReachabilityResult,
) -> tuple[SourceReadinessStatus, str, list[str], str]:
    """Return readiness status, reason, limitations, and next action."""

    if verification_status == VerificationStatus.BLOCKED:
        return (
            SourceReadinessStatus.BLOCKED,
            "source registry status is blocked",
            ["manual review is required before further checks"],
            "review lawful access boundary and source terms",
        )
    if verification_status == VerificationStatus.FAILED:
        return (
            SourceReadinessStatus.FAILED,
            "source registry status is failed",
            ["previous verification attempt failed"],
            "repair source record or replace source target",
        )
    if http_result.checked and _http_blocked(http_result.status_code):
        return (
            SourceReadinessStatus.BLOCKED,
            "HTTP check reached an access-blocking response",
            ["HTTP status indicates blocked or unauthorized public access"],
            "do not proceed without lawful access review",
        )
    if http_result.checked and http_result.reachable is False:
        return (
            SourceReadinessStatus.FAILED,
            "HTTP reachability check failed",
            [http_result.error or "source URL was not reachable"],
            "retry later or repair source URL",
        )
    if not http_result.checked:
        return (
            SourceReadinessStatus.SEED_ONLY,
            "source record has not been HTTP-checked by this workflow",
            ["source remains a registry seed until reachability is checked"],
            "run source-readiness check with HTTP reachability enabled",
        )
    if verification_status == VerificationStatus.UNVERIFIED:
        return (
            SourceReadinessStatus.REACHABLE,
            "source URL is reachable but registry status remains unverified",
            ["reachability is not equivalent to verified source coverage"],
            "perform manual source verification before changing registry status",
        )
    if verification_status == VerificationStatus.PARTIAL:
        return (
            SourceReadinessStatus.PARTIAL,
            "source is only partially verified",
            ["partial verification cannot support full coverage claims"],
            "complete source verification checklist",
        )
    if adapter_status == AdapterImplementationStatus.PLACEHOLDER:
        return (
            SourceReadinessStatus.PARTIAL,
            "source is verified but adapter family remains placeholder-only",
            ["adapter maturity prevents verified usable coverage"],
            "implement and test adapter contract before coverage claims",
        )
    if adapter_status == AdapterImplementationStatus.CONTRACT_READY:
        return (
            SourceReadinessStatus.PARTIAL,
            "source is verified and adapter contract exists, but live read behavior is not established",
            ["contract-ready adapter is not production live coverage"],
            "add guarded live-read evidence before live coverage claims",
        )
    return (
        SourceReadinessStatus.VERIFIED_CANDIDATE,
        "source is verified and adapter family supports live read maturity",
        [],
        "review evidence and promote only through explicit registry update workflow",
    )


def _http_blocked(status_code: int | None) -> bool:
    """Return true for access-blocking status codes."""

    return status_code in {401, 403, 407, 429, 451}


def _lawful_access_boundary(spec: AdapterFamilySpec | None) -> str:
    """Return source lawful-access boundary text."""

    if spec is None:
        return "public URL only; adapter family is unknown"
    if spec.uses_public_http:
        return "public HTTP only; no bypass, credentials, captcha, or access-control evasion"
    return "non-public HTTP behavior is not enabled by this workflow"


def _source_key(source: PublicSource) -> str:
    """Build deterministic source key for report rows."""

    basis = "|".join(
        [
            source.source_name,
            source.platform_family.value,
            str(source.public_url),
        ]
    )
    return f"source:{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]}"
