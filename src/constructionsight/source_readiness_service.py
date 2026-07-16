"""Conservative source-readiness workflow service."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from datetime import datetime

from constructionsight.adapters.specs import AdapterFamilySpec, AdapterImplementationStatus
from constructionsight.authorization_decision import AuthorizationUseLedger
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)
from constructionsight.models import PlatformFamily, PublicSource, VerificationStatus
from constructionsight.source_readiness_http import check_source_http_reachability
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


def build_authorized_source_readiness_report(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    http_checker: HttpReachabilityChecker | None = None,
) -> SourceReadinessReport:
    """Authorize bounded HEAD/405-GET reachability for the exact source set."""

    source_payload = [source.model_dump(mode="json") for source in sources]
    adapter_payload = [
        {
            "platform_family": family.value,
            "status": spec.status.value,
            "uses_public_http": spec.uses_public_http,
            "lawful_access_boundary": _lawful_access_boundary(spec),
        }
        for family, spec in sorted(adapter_specs.items(), key=lambda item: item[0].value)
    ]
    state_identity = authorization_digest(
        "source-readiness-state",
        {
            "sources": source_payload,
            "adapter_specs": adapter_payload,
            "policy_id": "CS-NET-007",
            "method_sequence": ["HEAD", "GET only after 405"],
            "max_response_bytes": 4096,
        },
    )
    resource_id = authorization_digest(
        "source-readiness-resource",
        {
            "source_keys": [_source_key(source) for source in sources],
            "urls": [str(source.public_url) for source in sources],
        },
    )
    exact_scope = tuple(
        sorted(
            {
                "fallback:GET-only-after-405",
                "max-attempts-per-source:2",
                "max-response-bytes:4096",
                "method:HEAD",
                "policy:CS-NET-007",
                "redirects:denied",
                "retries:0",
                f"source-count:{len(sources)}",
                *(f"url:{source.public_url}" for source in sources),
            },
            key=str.casefold,
        )
    )
    authorize_local_operator_operation(
        action="check-source-http-readiness",
        resource_type="public-source-registry-snapshot",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("perform bounded public HEAD checks with 405-only GET fallback",),
        denied_authority=tuple(
            sorted(
                {
                    "access-control bypass",
                    "credential use",
                    "document download",
                    "persistence mutation",
                    "production recurrence",
                    "redirect following",
                    "registry mutation",
                    "retry",
                    "source promotion",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=tuple(
            sorted(
                {
                    "local operator identity is not authentication",
                    "reachability does not establish source completeness or maturity",
                    "single local-process use only",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
        now=now,
        ledger=ledger,
    )
    return build_source_readiness_report(
        sources,
        adapter_specs,
        check_http=True,
        http_checker=http_checker,
    )


def check_http_reachability(source: PublicSource) -> HttpReachabilityResult:
    """Delegate lawful reachability to the exact-host bounded transport."""

    return check_source_http_reachability(source)


def _build_row(
    source: PublicSource,
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    http_result: HttpReachabilityResult,
) -> SourceReadinessRow:
    """Build one source-readiness row."""

    spec = adapter_specs.get(source.platform_family)
    adapter_status = spec.status if spec is not None else AdapterImplementationStatus.PLACEHOLDER
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
            "source is verified and adapter contract exists, but live reads are not proven",
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
