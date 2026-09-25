"""Governed CEQAnet recurring-run definition, manifest, and execution services."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any
from urllib.parse import urlparse

from constructionsight.adapters.ceqanet import CEQANET_SEARCH_URL
from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionReport,
    CeqanetListingReadOnlyExecutor,
    CeqanetListingResponseSnapshot,
)
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetAccessAssumptions,
    CeqanetRecurringQueryTemplate,
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetRecurringRunVerification,
    CeqanetRunReadiness,
    CeqanetWindowField,
    canonical_digest,
)
from constructionsight.legal import SourceAccessProfile, evaluate_access
from constructionsight.models import PlatformFamily, PublicSource, VerificationStatus
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistReport,
    SourceVerificationChecklistRow,
)

_OFFICIAL_REGISTRY_HOSTS = {"ceqanet.opr.ca.gov", "ceqanet.lci.ca.gov"}
_EXECUTION_HOST = "ceqanet.lci.ca.gov"
_MANIFEST_LIMITATION = "manifest authorizes no persistence and no background scheduling"


def build_ceqanet_recurring_run_definition(
    sources: list[PublicSource],
    checklist_report: SourceVerificationChecklistReport,
    *,
    source_key: str,
    query_template: CeqanetRecurringQueryTemplate,
    access_assumptions: CeqanetAccessAssumptions | None = None,
    execution_base_url: str = "https://ceqanet.lci.ca.gov/",
    timeout_seconds: float = 20.0,
    max_body_chars: int = 50_000,
) -> CeqanetRecurringRunDefinition:
    """Build one immutable CEQAnet recurring-run definition."""

    source_row = _checklist_row(checklist_report, source_key)
    source = _registry_source(sources, source_row)
    if source.platform_family is not PlatformFamily.CEQANET:
        raise ValueError("selected source is not a CEQAnet source")
    _validate_registry_public_url(str(source.public_url))
    normalized_execution_url = _normalize_execution_base_url(execution_base_url)
    assumptions = access_assumptions or CeqanetAccessAssumptions()
    blockers = _definition_blockers(source, source_row, assumptions)
    readiness = (
        CeqanetRunReadiness.BLOCKED
        if blockers
        else CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION
    )
    limitations = [
        "definition creation performs no network execution or persistence mutation",
        "each exact run window requires a separate immutable manifest",
        "source or checklist evidence changes require a new definition digest",
        "live execution still requires an explicit per-attempt operator authorization",
        (
            "attempt sequence uniqueness is operator-controlled until a persisted "
            "attempt ledger exists"
        ),
    ]
    if urlparse(str(source.public_url)).netloc.lower() != _EXECUTION_HOST:
        limitations.append(
            "registry public URL and execution host differ; both identities are preserved"
        )

    payload: dict[str, Any] = {
        "source_key": source_row.source_key,
        "source_name": source.source_name,
        "registry_public_url": str(source.public_url),
        "execution_base_url": normalized_execution_url,
        "source_registry_digest": _source_registry_digest(sources),
        "checklist_evidence_digest": _checklist_row_digest(source_row),
        "registry_verification_status": source.verification_status.value,
        "checklist_status": source_row.checklist_status.value,
        "evidence_refs": list(source_row.evidence_refs),
        "access_assumptions": assumptions,
        "query_template": query_template,
        "timeout_seconds": timeout_seconds,
        "max_body_chars": max_body_chars,
        "readiness": readiness,
        "blockers": blockers,
        "limitations": limitations,
    }
    digest = canonical_digest(_jsonable_definition_payload(payload))
    definition = CeqanetRecurringRunDefinition(
        **payload,
        definition_digest=digest,
    )
    definition.assert_integrity()
    return definition


def build_ceqanet_recurring_run_manifest(
    definition: CeqanetRecurringRunDefinition,
    *,
    window_start: date,
    window_end: date,
) -> CeqanetRecurringRunManifest:
    """Build one immutable exact-window manifest from a reviewed definition."""

    definition.assert_integrity()
    if window_start > window_end:
        raise ValueError("window_start must be on or before window_end")
    query = _query_payload(
        definition.query_template,
        window_start=window_start,
        window_end=window_end,
    )
    _listing_query_from_payload(query)
    run_id = _expected_run_id(
        definition,
        window_start=window_start,
        window_end=window_end,
        query=query,
    )
    payload: dict[str, Any] = {
        "run_id": run_id,
        "definition_digest": definition.definition_digest,
        "source_key": definition.source_key,
        "source_name": definition.source_name,
        "execution_base_url": definition.execution_base_url,
        "window_field": definition.query_template.window_field,
        "window_start": window_start,
        "window_end": window_end,
        "query": query,
        "timeout_seconds": definition.timeout_seconds,
        "max_body_chars": definition.max_body_chars,
        "access_assumptions": definition.access_assumptions,
        "readiness": definition.readiness,
        "blockers": list(definition.blockers),
        "limitations": [*definition.limitations, _MANIFEST_LIMITATION],
    }
    digest = canonical_digest(_jsonable_manifest_payload(payload))
    manifest = CeqanetRecurringRunManifest(
        **payload,
        manifest_digest=digest,
    )
    manifest.assert_integrity()
    return manifest


def assert_ceqanet_definition_evidence_current(
    definition: CeqanetRecurringRunDefinition,
    sources: list[PublicSource],
    checklist_report: SourceVerificationChecklistReport,
) -> None:
    """Reject a definition whose current registry or checklist evidence has drifted."""

    definition.assert_integrity()
    current_registry_digest = _source_registry_digest(sources)
    if current_registry_digest != definition.source_registry_digest:
        raise ValueError("current source registry digest does not match definition")

    row = _checklist_row(checklist_report, definition.source_key)
    source = _registry_source(sources, row)
    if source.platform_family is not PlatformFamily.CEQANET:
        raise ValueError("current source is no longer a CEQAnet source")
    _validate_registry_public_url(str(source.public_url))

    comparisons = (
        (
            source.source_name,
            definition.source_name,
            "current source name does not match definition",
        ),
        (
            str(source.public_url),
            definition.registry_public_url,
            "current source URL does not match definition",
        ),
        (
            source.verification_status.value,
            definition.registry_verification_status,
            "current registry verification status does not match definition",
        ),
        (
            row.checklist_status.value,
            definition.checklist_status,
            "current checklist status does not match definition",
        ),
        (
            row.evidence_refs,
            definition.evidence_refs,
            "current checklist evidence references do not match definition",
        ),
    )
    for current, expected, message in comparisons:
        if current != expected:
            raise ValueError(message)

    if _checklist_row_digest(row) != definition.checklist_evidence_digest:
        raise ValueError("current checklist evidence digest does not match definition")

    blockers = _definition_blockers(source, row, definition.access_assumptions)
    if blockers:
        raise ValueError(
            "current source evidence no longer permits execution: " + "; ".join(blockers)
        )


def execute_ceqanet_recurring_run(
    definition: CeqanetRecurringRunDefinition,
    manifest: CeqanetRecurringRunManifest,
    sources: list[PublicSource],
    checklist_report: SourceVerificationChecklistReport,
    *,
    attempt_sequence: int,
    execute_live: bool,
) -> CeqanetRecurringRunExecution:
    """Execute one manifest through the existing bounded listing executor."""

    _validate_definition_manifest_pair(definition, manifest)
    assert_ceqanet_definition_evidence_current(definition, sources, checklist_report)
    if not execute_live:
        raise ValueError("explicit live execution authorization is required")
    if manifest.readiness is not CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION:
        raise ValueError("CEQAnet recurring-run manifest is blocked")
    if attempt_sequence < 1:
        raise ValueError("attempt_sequence must be at least 1")

    access_result = evaluate_access(
        SourceAccessProfile(
            public_url=manifest.execution_base_url,
            requires_login=manifest.access_assumptions.requires_login,
            has_captcha=manifest.access_assumptions.has_captcha,
            robots_disallows_collection=(
                manifest.access_assumptions.robots_disallows_collection
            ),
            terms_disallow_collection=(
                manifest.access_assumptions.terms_disallow_collection
            ),
            paywalled=manifest.access_assumptions.paywalled,
        )
    )
    query = _listing_query_from_payload(manifest.query)
    search_url = f"{manifest.execution_base_url.rstrip('/')}/Search"
    if search_url != CEQANET_SEARCH_URL:
        raise ValueError("manifest execution base does not resolve to the CEQAnet search contract")
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, access_result)
    report = CeqanetListingReadOnlyExecutor(
        timeout_seconds=manifest.timeout_seconds,
        max_body_chars=manifest.max_body_chars,
    ).run(plan)
    attempt_id = _expected_attempt_id(manifest, attempt_sequence)
    return CeqanetRecurringRunExecution(
        run_id=manifest.run_id,
        attempt_sequence=attempt_sequence,
        attempt_id=attempt_id,
        definition_digest=definition.definition_digest,
        manifest_digest=manifest.manifest_digest,
        source_key=definition.source_key,
        execution_report=_execution_report_to_dict(report, query),
        network_executed=report.executed_request_count > 0,
        persistence_mutated=False,
    )


def bind_authorized_recurring_listing_evidence(
    execution: CeqanetRecurringRunExecution,
    manifest: CeqanetRecurringRunManifest,
    *,
    authorization: Mapping[str, Any],
) -> CeqanetRecurringRunExecution:
    """Bind a manual recurring attempt to queue-compatible v2 listing evidence."""

    execution.assert_integrity()
    manifest.assert_integrity()
    if execution.run_id != manifest.run_id or execution.manifest_digest != manifest.manifest_digest:
        raise ValueError("recurring execution does not match the manifest being bound")
    decision_id = authorization.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("recurring authorization decision identity is missing")
    if authorization.get("action") != "execute-ceqanet-recurring-run-attempt":
        raise ValueError("recurring authorization action is not the expected manual attempt")

    report = execution.execution_report
    metadata = report.get("metadata")
    snapshots = report.get("snapshots")
    if not isinstance(metadata, dict) or not isinstance(snapshots, list):
        raise ValueError("recurring execution report is incomplete")
    if metadata.get("schema_version") not in {
        "ceqanet_listing_execution.v1",
        "ceqanet_listing_execution.v2",
    }:
        raise ValueError("recurring execution report schema is unsupported")

    bound_metadata = dict(metadata)
    bound_metadata.update(
        {
            "schema_version": "ceqanet_listing_execution.v2",
            "plan_id": _recurring_listing_plan_id(manifest, execution.attempt_sequence),
            "attempt_sequence": execution.attempt_sequence,
            "access": {
                "decision": "allowed",
                "reason": "Reviewed recurring-run access assumptions permit this manual attempt.",
                "state_identity": canonical_digest(
                    {
                        "manifest_digest": manifest.manifest_digest,
                        "access_assumptions": manifest.access_assumptions.model_dump(mode="json"),
                    }
                ),
            },
            "authorization": dict(authorization),
        }
    )
    bound_report = {
        "metadata": bound_metadata,
        "snapshots": [
            dict(snapshot) if isinstance(snapshot, dict) else snapshot
            for snapshot in snapshots
        ],
    }
    payload = execution.model_dump(
        mode="json",
        exclude={"execution_report", "execution_digest"},
    )
    rebound = CeqanetRecurringRunExecution(
        **payload,
        execution_report=bound_report,
        execution_digest="",
    )
    rebound.assert_integrity()
    return rebound


def verify_ceqanet_recurring_run_execution(
    definition: CeqanetRecurringRunDefinition,
    manifest: CeqanetRecurringRunManifest,
    execution: CeqanetRecurringRunExecution,
    sources: list[PublicSource] | None = None,
    checklist_report: SourceVerificationChecklistReport | None = None,
) -> CeqanetRecurringRunVerification:
    """Verify immutable binding, current evidence, and bounded execution invariants."""

    findings: list[str] = []
    try:
        _validate_definition_manifest_pair(definition, manifest)
    except ValueError as exc:
        findings.append(str(exc))

    if (sources is None) != (checklist_report is None):
        findings.append("current registry and checklist must be supplied together")
    elif sources is not None and checklist_report is not None:
        try:
            assert_ceqanet_definition_evidence_current(
                definition,
                sources,
                checklist_report,
            )
        except ValueError as exc:
            findings.append(str(exc))

    expected_attempt_id = _expected_attempt_id(manifest, execution.attempt_sequence)
    _compare(findings, execution.run_id, manifest.run_id, "execution run_id mismatch")
    _compare(
        findings,
        execution.definition_digest,
        definition.definition_digest,
        "execution definition_digest mismatch",
    )
    _compare(
        findings,
        execution.manifest_digest,
        manifest.manifest_digest,
        "execution manifest_digest mismatch",
    )
    _compare(
        findings,
        execution.source_key,
        definition.source_key,
        "execution source_key mismatch",
    )
    _compare(
        findings,
        execution.attempt_id,
        expected_attempt_id,
        "execution attempt_id mismatch",
    )
    if execution.persistence_mutated:
        findings.append("execution reports persistence mutation")
    executed_count = _verify_execution_report(
        manifest,
        execution.execution_report,
        findings,
        attempt_sequence=execution.attempt_sequence,
    )
    if executed_count is not None:
        expected_network_executed = executed_count > 0
        if execution.network_executed != expected_network_executed:
            findings.append("network_executed does not match executed request count")

    return CeqanetRecurringRunVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        run_id=manifest.run_id,
        definition_digest=definition.definition_digest,
        manifest_digest=manifest.manifest_digest,
    )


def _definition_blockers(
    source: PublicSource,
    row: SourceVerificationChecklistRow,
    assumptions: CeqanetAccessAssumptions,
) -> list[str]:
    blockers: list[str] = []
    if source.verification_status is not VerificationStatus.VERIFIED:
        blockers.append("source registry status is not verified")
    required_items = {
        "public entry": row.public_entry_page,
        "query behavior": row.query_behavior,
        "result list": row.result_list,
        "detail page": row.detail_page,
        "terms review": row.terms_review,
    }
    for label, status in required_items.items():
        if status is not ChecklistItemStatus.OBSERVED:
            blockers.append(f"{label} evidence is not observed")
    if row.access_barrier is not ChecklistItemStatus.NOT_OBSERVED:
        blockers.append("access-barrier review does not affirm no barrier")
    if not row.evidence_refs:
        blockers.append("source verification evidence references are missing")
    if assumptions.has_blocker:
        blockers.append("lawful-access assumptions contain a collection blocker")
    return blockers


def _checklist_row(
    report: SourceVerificationChecklistReport,
    source_key: str,
) -> SourceVerificationChecklistRow:
    matches = [row for row in report.rows if row.source_key == source_key]
    if len(matches) != 1:
        raise ValueError("source_key must identify exactly one checklist row")
    return matches[0]


def _registry_source(
    sources: list[PublicSource],
    row: SourceVerificationChecklistRow,
) -> PublicSource:
    matches = [
        source
        for source in sources
        if source.source_name == row.source_name
        and source.platform_family.value == row.platform_family
        and str(source.public_url) == row.original_url
    ]
    if len(matches) != 1:
        raise ValueError("checklist row does not bind to exactly one registry source")
    return matches[0]


def _validate_registry_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in _OFFICIAL_REGISTRY_HOSTS:
        raise ValueError("CEQAnet registry URL must use an approved official HTTPS host")


def _normalize_execution_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != _EXECUTION_HOST:
        raise ValueError("CEQAnet execution base URL must use https://ceqanet.lci.ca.gov")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("CEQAnet execution base URL cannot contain params, query, or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("CEQAnet execution base URL must identify the host root")
    return "https://ceqanet.lci.ca.gov/"


def _source_registry_digest(sources: Iterable[PublicSource]) -> str:
    return canonical_digest([source.model_dump(mode="json") for source in sources])


def _checklist_row_digest(row: SourceVerificationChecklistRow) -> str:
    return canonical_digest(row.model_dump(mode="json", exclude={"generated_at"}))


def _jsonable_definition_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return CeqanetRecurringRunDefinition.model_construct(
        **payload,
        definition_digest="0" * 64,
    ).approval_payload()


def _jsonable_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return CeqanetRecurringRunManifest.model_construct(
        **payload,
        manifest_digest="0" * 64,
    ).approval_payload()


def _query_payload(
    template: CeqanetRecurringQueryTemplate,
    *,
    window_start: date,
    window_end: date,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "counties": list(template.counties),
        "document_types": list(template.document_types),
        "lead_agencies": list(template.lead_agencies),
        "text_terms": list(template.text_terms),
        "received_from": None,
        "received_to": None,
        "posted_from": None,
        "posted_to": None,
        "high_signal_only": template.high_signal_only,
        "page_size": template.page_size,
        "max_pages": template.max_pages,
    }
    if template.window_field is CeqanetWindowField.RECEIVED:
        payload["received_from"] = window_start.isoformat()
        payload["received_to"] = window_end.isoformat()
    else:
        payload["posted_from"] = window_start.isoformat()
        payload["posted_to"] = window_end.isoformat()
    return payload


def _listing_query_from_payload(payload: dict[str, Any]) -> CeqanetListingQuery:
    return CeqanetListingQuery(
        counties=tuple(_string_list(payload, "counties")),
        document_types=tuple(_string_list(payload, "document_types")),
        lead_agencies=tuple(_string_list(payload, "lead_agencies")),
        text_terms=tuple(_string_list(payload, "text_terms")),
        received_from=_optional_date(payload.get("received_from"), "received_from"),
        received_to=_optional_date(payload.get("received_to"), "received_to"),
        posted_from=_optional_date(payload.get("posted_from"), "posted_from"),
        posted_to=_optional_date(payload.get("posted_to"), "posted_to"),
        high_signal_only=_bool_value(payload, "high_signal_only"),
        page_size=_int_value(payload, "page_size"),
        max_pages=_int_value(payload, "max_pages"),
    )


def _string_list(payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return value


def _optional_date(value: object, field_name: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO date string or null")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date string") from exc


def _bool_value(payload: dict[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _int_value(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _execution_report_to_dict(
    report: CeqanetListingExecutionReport,
    query: CeqanetListingQuery,
) -> dict[str, Any]:
    return {
        "metadata": {
            "schema_version": "ceqanet_listing_execution.v1",
            "allowed": report.allowed,
            "reason": report.reason,
            "planned_request_count": report.planned_request_count,
            "executed_request_count": report.executed_request_count,
            "successful_response_count": report.successful_response_count,
            "failed_response_count": report.failed_response_count,
            "maximum_records": report.maximum_records,
            "query": _query_to_dict(query),
        },
        "snapshots": [_snapshot_to_dict(snapshot) for snapshot in report.snapshots],
    }


def _query_to_dict(query: CeqanetListingQuery) -> dict[str, Any]:
    return {
        "counties": list(query.counties),
        "document_types": list(query.document_types),
        "lead_agencies": list(query.lead_agencies),
        "text_terms": list(query.text_terms),
        "received_from": query.received_from.isoformat() if query.received_from else None,
        "received_to": query.received_to.isoformat() if query.received_to else None,
        "posted_from": query.posted_from.isoformat() if query.posted_from else None,
        "posted_to": query.posted_to.isoformat() if query.posted_to else None,
        "high_signal_only": query.high_signal_only,
        "page_size": query.page_size,
        "max_pages": query.max_pages,
    }


def _snapshot_to_dict(snapshot: CeqanetListingResponseSnapshot) -> dict[str, Any]:
    return {
        "page_number": snapshot.page_number,
        "method": snapshot.method,
        "request_url": snapshot.request_url,
        "final_url": snapshot.final_url,
        "status_code": snapshot.status_code,
        "content_type": snapshot.content_type,
        "body_text": snapshot.body_text,
        "body_length": snapshot.body_length,
        "body_truncated": snapshot.body_truncated,
        "executed": snapshot.executed,
        "error": snapshot.error,
        "failure_kind": snapshot.failure_kind,
        "reachable": snapshot.reachable,
    }


def _expected_run_id(
    definition: CeqanetRecurringRunDefinition,
    *,
    window_start: date,
    window_end: date,
    query: dict[str, Any],
) -> str:
    return canonical_digest(
        {
            "definition_digest": definition.definition_digest,
            "source_key": definition.source_key,
            "window_field": definition.query_template.window_field.value,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "query": query,
        }
    )


def _expected_attempt_id(
    manifest: CeqanetRecurringRunManifest,
    attempt_sequence: int,
) -> str:
    return canonical_digest(
        {
            "run_id": manifest.run_id,
            "manifest_digest": manifest.manifest_digest,
            "attempt_sequence": attempt_sequence,
        }
    )


def _validate_definition_manifest_pair(
    definition: CeqanetRecurringRunDefinition,
    manifest: CeqanetRecurringRunManifest,
) -> None:
    definition.assert_integrity()
    manifest.assert_integrity()
    comparisons = (
        (
            manifest.definition_digest,
            definition.definition_digest,
            "manifest definition_digest does not match definition",
        ),
        (
            manifest.source_key,
            definition.source_key,
            "manifest source_key does not match definition",
        ),
        (
            manifest.source_name,
            definition.source_name,
            "manifest source_name does not match definition",
        ),
        (
            manifest.execution_base_url,
            definition.execution_base_url,
            "manifest execution_base_url does not match definition",
        ),
        (
            manifest.window_field,
            definition.query_template.window_field,
            "manifest window_field does not match definition",
        ),
        (
            manifest.timeout_seconds,
            definition.timeout_seconds,
            "manifest timeout_seconds does not match definition",
        ),
        (
            manifest.max_body_chars,
            definition.max_body_chars,
            "manifest max_body_chars does not match definition",
        ),
        (
            manifest.access_assumptions,
            definition.access_assumptions,
            "manifest access assumptions do not match definition",
        ),
        (
            manifest.readiness,
            definition.readiness,
            "manifest readiness does not match definition",
        ),
        (
            manifest.blockers,
            definition.blockers,
            "manifest blockers do not match definition",
        ),
        (
            manifest.limitations,
            [*definition.limitations, _MANIFEST_LIMITATION],
            "manifest limitations do not match definition",
        ),
    )
    for actual, expected, message in comparisons:
        if actual != expected:
            raise ValueError(message)

    expected_query = _query_payload(
        definition.query_template,
        window_start=manifest.window_start,
        window_end=manifest.window_end,
    )
    if manifest.query != expected_query:
        raise ValueError("manifest query does not match definition and window")
    expected_run_id = _expected_run_id(
        definition,
        window_start=manifest.window_start,
        window_end=manifest.window_end,
        query=expected_query,
    )
    if manifest.run_id != expected_run_id:
        raise ValueError("manifest run_id does not match definition and window")


def _compare(findings: list[str], actual: object, expected: object, message: str) -> None:
    if actual != expected:
        findings.append(message)


def _recurring_listing_plan_id(
    manifest: CeqanetRecurringRunManifest,
    attempt_sequence: int,
) -> str:
    """Return a stable identity for one exact manifest listing attempt."""

    return canonical_digest(
        {
            "kind": "ceqanet-recurring-listing-attempt",
            "run_id": manifest.run_id,
            "manifest_digest": manifest.manifest_digest,
            "attempt_sequence": attempt_sequence,
        }
    )


def _verify_execution_report(
    manifest: CeqanetRecurringRunManifest,
    report: dict[str, Any],
    findings: list[str],
    *,
    attempt_sequence: int,
) -> int | None:
    metadata = report.get("metadata")
    snapshots = report.get("snapshots")
    if not isinstance(metadata, dict):
        findings.append("execution report metadata is missing")
        return None
    if not isinstance(snapshots, list):
        findings.append("execution report snapshots are missing")
        return None

    schema_version = metadata.get("schema_version")
    if schema_version not in {
        "ceqanet_listing_execution.v1",
        "ceqanet_listing_execution.v2",
    }:
        findings.append("execution report schema_version mismatch")
    if schema_version == "ceqanet_listing_execution.v2":
        metadata_attempt = metadata.get("attempt_sequence")
        if isinstance(metadata_attempt, bool) or not isinstance(metadata_attempt, int):
            findings.append("execution report attempt_sequence is not an integer")
        else:
            _compare(
                findings,
                metadata_attempt,
                attempt_sequence,
                "execution report attempt_sequence does not match execution",
            )
        _compare(
            findings,
            metadata.get("plan_id"),
            _recurring_listing_plan_id(manifest, attempt_sequence),
            "execution report plan_id does not match manifest attempt",
        )
        _compare(
            findings,
            metadata.get("allowed"),
            True,
            "execution report allowed flag is not true",
        )
        access = metadata.get("access")
        authorization = metadata.get("authorization")
        if not isinstance(access, dict) or access.get("decision") != "allowed":
            findings.append("execution report access decision is not allowed")
        if (
            not isinstance(authorization, dict)
            or not isinstance(authorization.get("decision_id"), str)
            or not authorization.get("decision_id")
            or authorization.get("action") != "execute-ceqanet-recurring-run-attempt"
        ):
            findings.append("execution report authorization identity is invalid")
    _compare(
        findings,
        metadata.get("query"),
        manifest.query,
        "execution report query does not match manifest",
    )
    _compare(
        findings,
        metadata.get("maximum_records"),
        _int_value(manifest.query, "page_size") * _int_value(manifest.query, "max_pages"),
        "execution report maximum_records does not match manifest",
    )

    planned = _report_int(metadata, "planned_request_count", findings)
    executed = _report_int(metadata, "executed_request_count", findings)
    successful = _report_int(metadata, "successful_response_count", findings)
    failed = _report_int(metadata, "failed_response_count", findings)
    max_pages = _int_value(manifest.query, "max_pages")
    if planned is not None and planned > max_pages:
        findings.append("planned_request_count exceeds manifest max_pages")
    if executed is not None and executed != len(snapshots):
        findings.append("executed_request_count does not match snapshots")
    if None not in {executed, successful, failed}:
        assert executed is not None
        assert successful is not None
        assert failed is not None
        if successful + failed != executed:
            findings.append("successful and failed response counts do not equal executed count")

    expected_host = urlparse(manifest.execution_base_url).netloc.lower()
    page_numbers: set[int] = set()
    for index, snapshot in enumerate(snapshots):
        _verify_snapshot(
            snapshot,
            index=index,
            expected_host=expected_host,
            max_pages=max_pages,
            max_body_chars=manifest.max_body_chars,
            page_numbers=page_numbers,
            findings=findings,
        )
    return executed


def _report_int(
    metadata: dict[str, Any],
    field_name: str,
    findings: list[str],
) -> int | None:
    value = metadata.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        findings.append(f"{field_name} is not an integer")
        return None
    return value


def _verify_snapshot(
    snapshot: object,
    *,
    index: int,
    expected_host: str,
    max_pages: int,
    max_body_chars: int,
    page_numbers: set[int],
    findings: list[str],
) -> None:
    if not isinstance(snapshot, dict):
        findings.append(f"snapshots[{index}] is not an object")
        return

    page_number = snapshot.get("page_number")
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        findings.append(f"snapshots[{index}] page_number is not an integer")
    elif not 1 <= page_number <= max_pages:
        findings.append(f"snapshots[{index}] page_number exceeds manifest bounds")
    elif page_number in page_numbers:
        findings.append(f"snapshots[{index}] page_number is duplicated")
    else:
        page_numbers.add(page_number)

    if snapshot.get("method") != "GET":
        findings.append(f"snapshots[{index}] method is not GET")
    if snapshot.get("executed") is not True:
        findings.append(f"snapshots[{index}] executed flag is not true")

    request_url = snapshot.get("request_url")
    if not isinstance(request_url, str):
        findings.append(f"snapshots[{index}] request_url is missing")
    else:
        _verify_snapshot_url(
            request_url,
            index=index,
            label="request_url",
            expected_host=expected_host,
            require_search_path=True,
            findings=findings,
        )

    final_url = snapshot.get("final_url")
    if not isinstance(final_url, str):
        findings.append(f"snapshots[{index}] final_url is missing")
    else:
        _verify_snapshot_url(
            final_url,
            index=index,
            label="final_url",
            expected_host=expected_host,
            require_search_path=False,
            findings=findings,
        )

    body_text = snapshot.get("body_text")
    body_length = snapshot.get("body_length")
    body_truncated = snapshot.get("body_truncated")
    if not isinstance(body_text, str):
        findings.append(f"snapshots[{index}] body_text is not a string")
    elif len(body_text) > max_body_chars:
        findings.append(f"snapshots[{index}] retained body exceeds manifest limit")
    if isinstance(body_length, bool) or not isinstance(body_length, int):
        findings.append(f"snapshots[{index}] body_length is not an integer")
    elif isinstance(body_text, str) and body_length < len(body_text):
        findings.append(f"snapshots[{index}] body_length is smaller than retained body")
    if not isinstance(body_truncated, bool):
        findings.append(f"snapshots[{index}] body_truncated is not a boolean")
    elif (
        isinstance(body_length, int)
        and not isinstance(body_length, bool)
        and body_truncated != (body_length > max_body_chars)
    ):
        findings.append(f"snapshots[{index}] body_truncated is inconsistent")


def _verify_snapshot_url(
    url: str,
    *,
    index: int,
    label: str,
    expected_host: str,
    require_search_path: bool,
    findings: list[str],
) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != expected_host:
        findings.append(f"snapshots[{index}] {label} host is outside manifest")
    if require_search_path and parsed.path != "/Search":
        findings.append(f"snapshots[{index}] {label} path is not /Search")
