from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import HttpUrl

from constructionsight.ceqanet_recurring_run_models import (
    CeqanetAccessAssumptions,
    CeqanetRecurringQueryTemplate,
    CeqanetRecurringRunExecution,
    CeqanetRunReadiness,
    CeqanetWindowField,
)
from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
    execute_ceqanet_recurring_run,
    verify_ceqanet_recurring_run_execution,
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
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistReport,
    SourceVerificationChecklistRow,
    SourceVerificationChecklistStatus,
)


class _FakeResponse:
    status_code = 200
    text = "<html>" + ("x" * 200) + "</html>"
    url = "https://ceqanet.lci.ca.gov/Search?County=Riverside"
    headers = {"content-type": "text/html; charset=utf-8"}


class _FakeClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(
        self,
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
    ) -> _FakeResponse:
        assert follow_redirects is True
        assert timeout == 9.0
        self.urls.append(url)
        return _FakeResponse()


def _source(status: VerificationStatus) -> PublicSource:
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
        verification_status=status,
        provenance_notes="Test source",
        last_checked_date=date(2026, 7, 11),
    )


def _checklist_row(*, full: bool) -> SourceVerificationChecklistRow:
    observed = ChecklistItemStatus.OBSERVED
    return SourceVerificationChecklistRow(
        source_key="source:ceqanet-state-clearinghouse",
        source_name="CEQAnet State Clearinghouse",
        platform_family="ceqanet",
        original_url="https://ceqanet.opr.ca.gov/",
        final_url="https://ceqanet.lci.ca.gov/",
        http_status_code=200,
        redirect_classification="cross_host_redirect",
        registry_status="verified" if full else "unverified",
        adapter_status="contract_ready",
        readiness_status="reachable",
        checklist_status=SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED,
        public_entry_page=observed,
        query_behavior=observed,
        result_list=observed,
        detail_page=observed,
        access_barrier=(
            ChecklistItemStatus.NOT_OBSERVED if full else ChecklistItemStatus.NOT_CHECKED
        ),
        terms_review=observed if full else ChecklistItemStatus.NOT_CHECKED,
        recommendation="review evidence",
        reasons=["operator observation file supplied"],
        limitations=[],
        next_action="review source evidence",
        observation_notes="Reviewed public search and detail behavior.",
        evidence_refs=["evidence/ceqanet-review-2026-07-11.json"] if full else [],
        generated_at=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
    )


def _checklist(*, full: bool) -> SourceVerificationChecklistReport:
    return SourceVerificationChecklistReport.from_rows([_checklist_row(full=full)])


def _template() -> CeqanetRecurringQueryTemplate:
    return CeqanetRecurringQueryTemplate(
        counties=["Riverside", "San Bernardino"],
        document_types=["NOP - Notice of Preparation of a Draft EIR"],
        window_field=CeqanetWindowField.RECEIVED,
        page_size=25,
        max_pages=2,
    )


def _ready_definition() -> Any:
    return build_ceqanet_recurring_run_definition(
        [_source(VerificationStatus.VERIFIED)],
        _checklist(full=True),
        source_key="source:ceqanet-state-clearinghouse",
        query_template=_template(),
        timeout_seconds=9.0,
        max_body_chars=100,
    )


def test_unverified_definition_and_manifest_remain_blocked() -> None:
    definition = build_ceqanet_recurring_run_definition(
        [_source(VerificationStatus.UNVERIFIED)],
        _checklist(full=False),
        source_key="source:ceqanet-state-clearinghouse",
        query_template=_template(),
    )

    assert definition.readiness is CeqanetRunReadiness.BLOCKED
    assert "source registry status is not verified" in definition.blockers
    assert "source verification evidence references are missing" in definition.blockers
    assert (
        "registry public URL and execution host differ; both identities are preserved"
        in definition.limitations
    )
    definition.assert_integrity()

    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    assert manifest.readiness is CeqanetRunReadiness.BLOCKED
    assert manifest.persistence_authorized is False
    manifest.assert_integrity()


def test_ready_definition_and_manifest_are_deterministic() -> None:
    definition = _ready_definition()
    repeated = _ready_definition()

    assert definition.readiness is CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION
    assert definition.blockers == []
    assert definition.definition_digest == repeated.definition_digest
    assert definition.registry_public_url == "https://ceqanet.opr.ca.gov/"
    assert definition.execution_base_url == "https://ceqanet.lci.ca.gov/"

    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    repeated_manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )

    assert manifest.run_id == repeated_manifest.run_id
    assert manifest.manifest_digest == repeated_manifest.manifest_digest
    assert manifest.query["received_from"] == "2026-07-01"
    assert manifest.query["received_to"] == "2026-07-07"
    assert manifest.query["posted_from"] is None
    assert manifest.query["max_pages"] == 2


def test_manifest_rejects_tampered_definition_digest() -> None:
    definition = _ready_definition()
    tampered = definition.model_copy(update={"source_name": "Changed source"})

    try:
        build_ceqanet_recurring_run_manifest(
            tampered,
            window_start=date(2026, 7, 1),
            window_end=date(2026, 7, 7),
        )
    except ValueError as exc:
        assert str(exc) == "CEQAnet recurring-run definition digest mismatch"
    else:
        raise AssertionError("tampered definition was accepted")


def test_execution_requires_explicit_authorization() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )

    try:
        execute_ceqanet_recurring_run(
            definition,
            manifest,
            attempt_sequence=1,
            execute_live=False,
            client=_FakeClient(),
        )
    except ValueError as exc:
        assert str(exc) == "explicit live execution authorization is required"
    else:
        raise AssertionError("execution occurred without explicit authorization")


def test_ready_manifest_executes_through_bounded_existing_executor() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    client = _FakeClient()

    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        attempt_sequence=1,
        execute_live=True,
        client=client,
    )

    assert execution.network_executed is True
    assert execution.persistence_mutated is False
    assert len(client.urls) == 2
    metadata = execution.execution_report["metadata"]
    assert metadata["executed_request_count"] == 2
    assert metadata["query"] == manifest.query
    snapshots = execution.execution_report["snapshots"]
    assert len(snapshots) == 2
    assert all(snapshot["body_truncated"] is True for snapshot in snapshots)

    verification = verify_ceqanet_recurring_run_execution(
        definition,
        manifest,
        execution,
    )
    assert verification.passed is True
    assert verification.findings == []


def test_verification_detects_execution_query_and_host_drift() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        attempt_sequence=1,
        execute_live=True,
        client=_FakeClient(),
    )
    payload = execution.model_dump(mode="json")
    report = payload["execution_report"]
    report["metadata"]["query"]["counties"] = ["Orange"]
    report["snapshots"][0]["request_url"] = "https://example.com/Search"
    tampered = CeqanetRecurringRunExecution.model_validate(payload)

    verification = verify_ceqanet_recurring_run_execution(
        definition,
        manifest,
        tampered,
    )

    assert verification.passed is False
    assert "execution report query does not match manifest" in verification.findings
    assert "snapshots[0] request_url host is outside manifest" in verification.findings


def test_access_assumption_blocker_prevents_ready_definition() -> None:
    definition = build_ceqanet_recurring_run_definition(
        [_source(VerificationStatus.VERIFIED)],
        _checklist(full=True),
        source_key="source:ceqanet-state-clearinghouse",
        query_template=_template(),
        access_assumptions=CeqanetAccessAssumptions(has_captcha=True),
    )

    assert definition.readiness is CeqanetRunReadiness.BLOCKED
    assert "lawful-access assumptions contain a collection blocker" in definition.blockers
