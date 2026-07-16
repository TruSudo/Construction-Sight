"""Source checklist service."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.authorization_decision import AuthorizationUseLedger
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_readiness_service import HttpReachabilityChecker
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistReport,
    SourceVerificationChecklistRow,
    SourceVerificationChecklistStatus,
    SourceVerificationObservation,
    SourceVerificationObservationTemplate,
)
from constructionsight.source_verification_evidence_service import (
    build_source_verification_evidence_package,
)


def build_source_verification_checklist_report(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    check_http: bool = False,
    http_checker: HttpReachabilityChecker | None = None,
    observations: Iterable[SourceVerificationObservation] | None = None,
) -> SourceVerificationChecklistReport:
    """Build a report-only source checklist."""

    observation_index = _observation_index(observations or [])
    evidence_package = build_source_verification_evidence_package(
        sources,
        adapter_specs,
        check_http=check_http,
        http_checker=http_checker,
    )
    rows = []
    for row in evidence_package.rows:
        observation = observation_index.get(row.source_key) or observation_index.get(
            row.source_name
        )
        rows.append(
            _build_row(
                source_key=row.source_key,
                source_name=row.source_name,
                platform_family=row.platform_family,
                original_url=row.original_url,
                final_url=row.final_url,
                http_status_code=row.http_status_code,
                redirect_classification=row.redirect_classification.value,
                registry_status=row.verification_status,
                adapter_status=row.adapter_status,
                readiness_status=row.readiness_status,
                recommendation=row.recommendation.value,
                reasons=row.reasons,
                limitations=row.limitations,
                observation=observation,
            )
        )
    return SourceVerificationChecklistReport.from_rows(rows)


def build_authorized_source_verification_checklist_report(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    observations: Iterable[SourceVerificationObservation] | None,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    http_checker: HttpReachabilityChecker | None = None,
) -> SourceVerificationChecklistReport:
    """Authorize exact-source verification GET evidence before checklist building."""

    normalized_observations = tuple(observations or ())
    state_identity = authorization_digest(
        "source-verification-checklist-state",
        {
            "sources": [source.model_dump(mode="json") for source in sources],
            "adapter_specs": [
                {
                    "platform_family": family.value,
                    "status": spec.status.value,
                    "uses_public_http": spec.uses_public_http,
                }
                for family, spec in sorted(
                    adapter_specs.items(),
                    key=lambda item: item[0].value,
                )
            ],
            "observations": [
                observation.model_dump(mode="json") for observation in normalized_observations
            ],
            "policy_id": "CS-NET-008",
        },
    )
    resource_id = authorization_digest(
        "source-verification-checklist-resource",
        {
            "urls": [str(source.public_url) for source in sources],
            "source_names": [source.source_name for source in sources],
        },
    )
    exact_scope = tuple(
        sorted(
            {
                "concurrency:1",
                "max-attempts-per-source:1",
                "max-response-bytes:50000",
                "method:GET",
                f"observation-count:{len(normalized_observations)}",
                "policy:CS-NET-008",
                "redirects:denied",
                "retries:0",
                f"source-count:{len(sources)}",
                *(f"url:{source.public_url}" for source in sources),
            },
            key=str.casefold,
        )
    )
    authorize_local_operator_operation(
        action="build-source-verification-checklist-live-evidence",
        resource_type="public-source-verification-snapshot",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("perform one exact bounded verification GET for each declared source",),
        denied_authority=tuple(
            sorted(
                {
                    "access-control bypass",
                    "alternate-host fallback",
                    "credential use",
                    "document download",
                    "observation mutation",
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
                    "HTTP evidence does not complete manual query, list, detail, "
                    "barrier, or terms review",
                    "local operator identity is not authentication",
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
    return build_source_verification_checklist_report(
        sources,
        adapter_specs,
        check_http=True,
        http_checker=http_checker,
        observations=normalized_observations,
    )


def build_source_observation_templates(
    sources: list[PublicSource],
) -> list[SourceVerificationObservationTemplate]:
    """Build editable source observation templates without checking or mutating sources."""

    return [
        SourceVerificationObservationTemplate(
            source_key=_source_key(source),
            source_name=source.source_name,
            platform_family=source.platform_family.value,
            public_url=str(source.public_url),
            instructions=[
                "Set booleans only after manual lawful public review.",
                "Leave unknown fields null instead of guessing.",
                "Use evidence_refs for screenshots, archive paths, notes, or run IDs.",
            ],
        )
        for source in sources
    ]


def _source_key(source: PublicSource) -> str:
    evidence_package = build_source_verification_evidence_package(
        [source],
        {},
        check_http=False,
    )
    return evidence_package.rows[0].source_key


def _build_row(
    *,
    source_key: str,
    source_name: str,
    platform_family: str,
    original_url: str,
    final_url: str | None,
    http_status_code: int | None,
    redirect_classification: str,
    registry_status: str,
    adapter_status: str,
    readiness_status: str,
    recommendation: str,
    reasons: list[str],
    limitations: list[str],
    observation: SourceVerificationObservation | None,
) -> SourceVerificationChecklistRow:
    public_entry_page = _item_from_bool(
        observation.public_entry_observed if observation else None,
        default=ChecklistItemStatus.OBSERVED if readiness_status == "reachable" else None,
    )
    query_behavior = _item_from_bool(observation.query_behavior_observed if observation else None)
    result_list = _item_from_bool(observation.result_list_observed if observation else None)
    detail_page = _item_from_bool(observation.detail_page_observed if observation else None)
    access_barrier = _access_barrier_status(observation)
    terms_review = _item_from_bool(observation.terms_review_observed if observation else None)
    checklist_status = _checklist_status(
        public_entry_page,
        query_behavior,
        result_list,
        detail_page,
        access_barrier,
    )
    return SourceVerificationChecklistRow(
        source_key=source_key,
        source_name=source_name,
        platform_family=platform_family,
        original_url=original_url,
        final_url=final_url,
        http_status_code=http_status_code,
        redirect_classification=redirect_classification,
        registry_status=registry_status,
        adapter_status=adapter_status,
        readiness_status=readiness_status,
        checklist_status=checklist_status,
        public_entry_page=public_entry_page,
        query_behavior=query_behavior,
        result_list=result_list,
        detail_page=detail_page,
        access_barrier=access_barrier,
        terms_review=terms_review,
        recommendation=recommendation,
        reasons=_unique([*reasons, *_observation_reasons(observation)]),
        limitations=_unique([*limitations, *_checklist_limitations(checklist_status)]),
        next_action=_next_action(checklist_status),
        observation_notes=observation.notes if observation else None,
        evidence_refs=observation.evidence_refs if observation else [],
    )


def _item_from_bool(
    value: bool | None,
    *,
    default: ChecklistItemStatus | None = None,
) -> ChecklistItemStatus:
    if value is True:
        return ChecklistItemStatus.OBSERVED
    if value is False:
        return ChecklistItemStatus.NOT_OBSERVED
    return default or ChecklistItemStatus.NOT_CHECKED


def _access_barrier_status(
    observation: SourceVerificationObservation | None,
) -> ChecklistItemStatus:
    if observation is None or observation.access_barrier_observed is None:
        return ChecklistItemStatus.NOT_CHECKED
    if observation.access_barrier_observed:
        return ChecklistItemStatus.BLOCKED
    return ChecklistItemStatus.NOT_OBSERVED


def _checklist_status(
    public_entry_page: ChecklistItemStatus,
    query_behavior: ChecklistItemStatus,
    result_list: ChecklistItemStatus,
    detail_page: ChecklistItemStatus,
    access_barrier: ChecklistItemStatus,
) -> SourceVerificationChecklistStatus:
    if access_barrier == ChecklistItemStatus.BLOCKED:
        return SourceVerificationChecklistStatus.BLOCKED
    if detail_page == ChecklistItemStatus.OBSERVED:
        return SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED
    if (
        query_behavior == ChecklistItemStatus.OBSERVED
        and result_list == ChecklistItemStatus.OBSERVED
    ):
        return SourceVerificationChecklistStatus.QUERY_BEHAVIOR_OBSERVED
    if public_entry_page == ChecklistItemStatus.OBSERVED:
        return SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE
    if ChecklistItemStatus.FAILED in {
        public_entry_page,
        query_behavior,
        result_list,
        detail_page,
    }:
        return SourceVerificationChecklistStatus.FAILED
    return SourceVerificationChecklistStatus.NEEDS_MANUAL_REVIEW


def _next_action(status: SourceVerificationChecklistStatus) -> str:
    if status == SourceVerificationChecklistStatus.BLOCKED:
        return "review access boundary"
    if status == SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED:
        return "review source evidence"
    if status == SourceVerificationChecklistStatus.QUERY_BEHAVIOR_OBSERVED:
        return "inspect detail-page behavior"
    if status == SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE:
        return "inspect query, list, detail, barrier, and terms behavior"
    if status == SourceVerificationChecklistStatus.FAILED:
        return "repair or replace source target"
    return "complete manual source checklist"


def _checklist_limitations(status: SourceVerificationChecklistStatus) -> list[str]:
    if status == SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE:
        return ["entry reachability is not query/list/detail evidence"]
    if status in {
        SourceVerificationChecklistStatus.NEEDS_MANUAL_REVIEW,
        SourceVerificationChecklistStatus.NOT_CHECKED,
    }:
        return ["manual query/list/detail checklist is incomplete"]
    if status == SourceVerificationChecklistStatus.QUERY_BEHAVIOR_OBSERVED:
        return ["detail-page behavior remains unchecked"]
    return []


def _observation_reasons(
    observation: SourceVerificationObservation | None,
) -> list[str]:
    if observation is None:
        return ["no operator observation file was supplied"]
    return ["operator observation file supplied"]


def _observation_index(
    observations: Iterable[SourceVerificationObservation],
) -> dict[str, SourceVerificationObservation]:
    index: dict[str, SourceVerificationObservation] = {}
    for observation in observations:
        if observation.source_key:
            index[observation.source_key] = observation
        if observation.source_name:
            index[observation.source_name] = observation
    return index


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
