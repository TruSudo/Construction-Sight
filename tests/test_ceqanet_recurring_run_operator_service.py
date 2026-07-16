from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import HttpUrl

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringQueryTemplate,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetWindowField,
)
from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
)
from constructionsight.models import (
    ExtractionDifficulty,
    Jurisdiction,
    PlatformFamily,
    PublicSource,
    RecordCategory,
    SourceType,
    VerificationStatus,
)
from constructionsight.operator_services.ceqanet_recurring_run_service import (
    execute_authorized_ceqanet_recurring_run,
)
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistReport,
    SourceVerificationChecklistRow,
    SourceVerificationChecklistStatus,
)

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def _source() -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="California State Clearinghouse",
            county="Statewide",
            state="CA",
            jurisdiction_type="state",
        ),
        source_name="CEQAnet State Clearinghouse",
        source_type=SourceType.STATE_REGISTRY,
        platform_family=PlatformFamily.CEQANET,
        public_url=HttpUrl("https://ceqanet.opr.ca.gov/"),
        record_categories=[
            RecordCategory.CEQA,
            RecordCategory.DOCUMENT,
            RecordCategory.PLANNING_CASE,
        ],
        search_method="Public CEQA search",
        extraction_difficulty=ExtractionDifficulty.LOW,
        update_frequency="daily",
        confidence_score=85,
        verification_status=VerificationStatus.VERIFIED,
        provenance_notes="Test source",
        last_checked_date=date(2026, 7, 11),
    )


def _checklist() -> SourceVerificationChecklistReport:
    observed = ChecklistItemStatus.OBSERVED
    row = SourceVerificationChecklistRow(
        source_key="source:ceqanet-state-clearinghouse",
        source_name="CEQAnet State Clearinghouse",
        platform_family="ceqanet",
        original_url="https://ceqanet.opr.ca.gov/",
        final_url="https://ceqanet.lci.ca.gov/",
        http_status_code=200,
        redirect_classification="cross_host_redirect",
        registry_status="verified",
        adapter_status="contract_ready",
        readiness_status="reachable",
        checklist_status=SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED,
        public_entry_page=observed,
        query_behavior=observed,
        result_list=observed,
        detail_page=observed,
        access_barrier=ChecklistItemStatus.NOT_OBSERVED,
        terms_review=observed,
        recommendation="review evidence",
        reasons=["operator observation file supplied"],
        limitations=[],
        next_action="review source evidence",
        observation_notes="Reviewed public search and detail behavior.",
        evidence_refs=["evidence/ceqanet-review-2026-07-11.json"],
        generated_at=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
    )
    return SourceVerificationChecklistReport.from_rows([row])


def _artifacts():
    sources = [_source()]
    checklist = _checklist()
    definition = build_ceqanet_recurring_run_definition(
        sources,
        checklist,
        source_key="source:ceqanet-state-clearinghouse",
        query_template=CeqanetRecurringQueryTemplate(
            counties=["Riverside", "San Bernardino"],
            document_types=["NOP - Notice of Preparation of a Draft EIR"],
            window_field=CeqanetWindowField.RECEIVED,
            page_size=25,
            max_pages=2,
        ),
        timeout_seconds=9.0,
        max_body_chars=100,
    )
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    return sources, checklist, definition, manifest


class _Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, bool]] = []

    def __call__(
        self,
        definition,
        manifest: CeqanetRecurringRunManifest,
        sources,
        checklist_report,
        *,
        attempt_sequence: int,
        execute_live: bool,
        client=None,
    ) -> CeqanetRecurringRunExecution:
        self.calls.append((manifest.run_id, attempt_sequence, execute_live))
        return CeqanetRecurringRunExecution(
            run_id=manifest.run_id,
            attempt_sequence=attempt_sequence,
            attempt_id="a" * 64,
            definition_digest=definition.definition_digest,
            manifest_digest=manifest.manifest_digest,
            source_key=manifest.source_key,
            execution_report={"metadata": {"executed_request_count": 0}},
            network_executed=False,
        )


def _execute(
    executor: _Executor,
    *,
    confirmation: bool = True,
    ledger: AuthorizationUseLedger | None = None,
):
    sources, checklist, definition, manifest = _artifacts()
    return execute_authorized_ceqanet_recurring_run(
        definition=definition,
        manifest=manifest,
        sources=sources,
        checklist_report=checklist,
        attempt_sequence=1,
        caller_confirmation=confirmation,
        authorization_reason="Execute one reviewed recurring-run attempt.",
        operator_id="operator:tyler",
        now=lambda: _NOW,
        ledger=ledger,
        executor=executor,
    )


def test_recurring_run_facade_binds_manual_attempt_and_negative_authority() -> None:
    executor = _Executor()

    result = _execute(executor)

    authorization = result.authorization.to_dict()
    assert authorization["action"] == "execute-ceqanet-recurring-run-attempt"
    assert "automatic recurrence" in authorization["denied_authority"]
    assert "background scheduling" in authorization["denied_authority"]
    assert result.execution.attempt_sequence == 1
    assert executor.calls == [(result.execution.run_id, 1, True)]


def test_boolean_confirmation_cannot_authorize_recurring_run() -> None:
    executor = _Executor()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _execute(executor, confirmation=False)

    assert executor.calls == []


def test_shared_ledger_rejects_repeated_recurring_attempt() -> None:
    executor = _Executor()
    ledger = AuthorizationUseLedger()

    first = _execute(executor, ledger=ledger)
    assert first.execution.attempt_sequence == 1
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _execute(executor, ledger=ledger)

    assert len(executor.calls) == 1
