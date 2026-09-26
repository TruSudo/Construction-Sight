from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
from pydantic import HttpUrl

import constructionsight.http_transport as http_transport_module
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetAccessAssumptions,
    CeqanetRecurringQueryTemplate,
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRunReadiness,
    CeqanetWindowField,
)
from constructionsight.ceqanet_recurring_run_service import (
    assert_ceqanet_definition_evidence_current,
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
    execute_ceqanet_recurring_run,
)
from constructionsight.ceqanet_recurring_run_verifier import (
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


class _FakeTransport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def build(self) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(self._handle_request),
            follow_redirects=False,
            trust_env=False,
        )

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        assert float(request.extensions["timeout"]["read"]) == 9.0
        self.urls.append(str(request.url))
        return httpx.Response(
            200,
            text="<html>" + ("x" * 200) + "</html>",
            headers={"content-type": "text/html; charset=utf-8"},
            request=request,
        )


def _install_transport(monkeypatch: pytest.MonkeyPatch) -> _FakeTransport:
    transport = _FakeTransport()
    monkeypatch.setattr(http_transport_module, "_build_http_client", transport.build)
    return transport


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


def _ready_sources() -> list[PublicSource]:
    return [_source(VerificationStatus.VERIFIED)]


def _ready_checklist() -> SourceVerificationChecklistReport:
    return _checklist(full=True)


def _ready_definition() -> CeqanetRecurringRunDefinition:
    return build_ceqanet_recurring_run_definition(
        _ready_sources(),
        _ready_checklist(),
        source_key="source:ceqanet-state-clearinghouse",
        query_template=_template(),
        timeout_seconds=9.0,
        max_body_chars=100,
    )


def _ready_manifest(definition: CeqanetRecurringRunDefinition) -> object:
    return build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
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
    assert any("attempt sequence uniqueness" in item for item in definition.limitations)

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

    with pytest.raises(
        ValueError,
        match="CEQAnet recurring-run definition digest mismatch",
    ):
        build_ceqanet_recurring_run_manifest(
            tampered,
            window_start=date(2026, 7, 1),
            window_end=date(2026, 7, 7),
        )


def test_current_registry_drift_blocks_execution_authority() -> None:
    definition = _ready_definition()

    with pytest.raises(
        ValueError,
        match="current source registry digest does not match definition",
    ):
        assert_ceqanet_definition_evidence_current(
            definition,
            [_source(VerificationStatus.UNVERIFIED)],
            _ready_checklist(),
        )


def test_current_checklist_drift_blocks_execution_authority() -> None:
    definition = _ready_definition()
    changed_row = _checklist_row(full=True).model_copy(
        update={"observation_notes": "Evidence was re-reviewed and changed."}
    )
    changed_checklist = SourceVerificationChecklistReport.from_rows([changed_row])

    with pytest.raises(
        ValueError,
        match="current checklist evidence digest does not match definition",
    ):
        assert_ceqanet_definition_evidence_current(
            definition,
            _ready_sources(),
            changed_checklist,
        )


def test_execution_requires_explicit_authorization() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )

    with pytest.raises(
        ValueError,
        match="explicit live execution authorization is required",
    ):
        execute_ceqanet_recurring_run(
            definition,
            manifest,
            _ready_sources(),
            _ready_checklist(),
            attempt_sequence=1,
            execute_live=False,
        )


def test_ready_manifest_executes_through_bounded_existing_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    transport = _install_transport(monkeypatch)

    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        _ready_sources(),
        _ready_checklist(),
        attempt_sequence=1,
        execute_live=True,
    )

    assert execution.network_executed is True
    assert execution.persistence_mutated is False
    assert len(execution.execution_digest) == 64
    execution.assert_integrity()
    assert len(transport.urls) == 2
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
        _ready_sources(),
        _ready_checklist(),
    )
    assert verification.passed is True
    assert verification.findings == []


def test_verification_detects_execution_query_and_host_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    _install_transport(monkeypatch)
    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        _ready_sources(),
        _ready_checklist(),
        attempt_sequence=1,
        execute_live=True,
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
        _ready_sources(),
        _ready_checklist(),
    )

    assert verification.passed is False
    assert "CEQAnet recurring-run execution digest mismatch" in verification.findings
    assert "execution report query does not match manifest" in verification.findings
    assert "snapshots[0] request_url host is outside manifest" in verification.findings


def test_verification_detects_retained_body_tampering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    _install_transport(monkeypatch)
    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        _ready_sources(),
        _ready_checklist(),
        attempt_sequence=1,
        execute_live=True,
    )
    payload = execution.model_dump(mode="json")
    payload["execution_report"]["snapshots"][0]["body_text"] = "altered"
    tampered = CeqanetRecurringRunExecution.model_validate(payload)

    verification = verify_ceqanet_recurring_run_execution(
        definition,
        manifest,
        tampered,
        _ready_sources(),
        _ready_checklist(),
    )

    assert verification.passed is False
    assert verification.findings[0] == "CEQAnet recurring-run execution digest mismatch"


def test_verification_detects_network_execution_flag_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    _install_transport(monkeypatch)
    execution = execute_ceqanet_recurring_run(
        definition,
        manifest,
        _ready_sources(),
        _ready_checklist(),
        attempt_sequence=1,
        execute_live=True,
    ).model_copy(update={"network_executed": False})

    verification = verify_ceqanet_recurring_run_execution(
        definition,
        manifest,
        execution,
        _ready_sources(),
        _ready_checklist(),
    )

    assert verification.passed is False
    assert "CEQAnet recurring-run execution digest mismatch" in verification.findings
    assert "network_executed does not match executed request count" in verification.findings


def test_manifest_semantic_drift_is_detected_even_with_recomputed_digest() -> None:
    definition = _ready_definition()
    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    tampered = manifest.model_copy(
        update={
            "readiness": CeqanetRunReadiness.BLOCKED,
            "blockers": ["tampered blocker"],
        }
    )
    tampered = tampered.model_copy(update={"manifest_digest": tampered.computed_digest()})
    execution = CeqanetRecurringRunExecution(
        run_id=tampered.run_id,
        attempt_sequence=1,
        attempt_id="0" * 64,
        definition_digest=definition.definition_digest,
        manifest_digest=tampered.manifest_digest,
        source_key=definition.source_key,
        execution_report={},
        network_executed=False,
    )

    verification = verify_ceqanet_recurring_run_execution(
        definition,
        tampered,
        execution,
        _ready_sources(),
        _ready_checklist(),
    )

    assert verification.passed is False
    assert "manifest readiness does not match definition" in verification.findings


def test_access_assumption_blocker_prevents_ready_definition() -> None:
    definition = build_ceqanet_recurring_run_definition(
        _ready_sources(),
        _ready_checklist(),
        source_key="source:ceqanet-state-clearinghouse",
        query_template=_template(),
        access_assumptions=CeqanetAccessAssumptions(has_captcha=True),
    )

    assert definition.readiness is CeqanetRunReadiness.BLOCKED
    assert "lawful-access assumptions contain a collection blocker" in definition.blockers
