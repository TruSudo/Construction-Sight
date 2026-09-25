from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import HttpUrl
from typer.testing import CliRunner

from constructionsight.ceqanet_recurring_run_cli import app
from constructionsight.ceqanet_capture_queue import build_reviewed_ceqanet_capture_queue
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetRunReadiness,
)
from constructionsight.ceqanet_recurring_run_service import (
    bind_authorized_recurring_listing_evidence,
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

runner = CliRunner()
_SOURCE_KEY = "source:ceqanet-state-clearinghouse"


def _source(status: VerificationStatus = VerificationStatus.VERIFIED) -> PublicSource:
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
        record_categories=[RecordCategory.CEQA, RecordCategory.DOCUMENT],
        search_method="Public CEQA search",
        extraction_difficulty=ExtractionDifficulty.LOW,
        update_frequency="daily",
        confidence_score=85,
        verification_status=status,
        provenance_notes="CLI test source",
        last_checked_date=date(2026, 7, 11),
    )


def _checklist() -> SourceVerificationChecklistReport:
    observed = ChecklistItemStatus.OBSERVED
    return SourceVerificationChecklistReport.from_rows(
        [
            SourceVerificationChecklistRow(
                source_key=_SOURCE_KEY,
                source_name="CEQAnet State Clearinghouse",
                platform_family="ceqanet",
                original_url="https://ceqanet.opr.ca.gov/",
                final_url="https://ceqanet.lci.ca.gov/",
                http_status_code=200,
                redirect_classification="cross_host_redirect",
                registry_status="verified",
                adapter_status="contract_ready",
                readiness_status="reachable",
                checklist_status=(
                    SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED
                ),
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
                evidence_refs=["evidence/ceqanet-review.json"],
                generated_at=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
            )
        ]
    )


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    registry_path = tmp_path / "registry.json"
    checklist_path = tmp_path / "checklist.json"
    registry_path.write_text(
        json.dumps([_source().model_dump(mode="json")], indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    checklist_path.write_text(
        json.dumps(_checklist().model_dump(mode="json"), indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return registry_path, checklist_path


def _build_cli_artifacts(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    registry_path, checklist_path = _write_inputs(tmp_path)
    definition_path = tmp_path / "definition.json"
    manifest_path = tmp_path / "manifest.json"

    definition_result = runner.invoke(
        app,
        [
            "build-definition",
            "--registry",
            str(registry_path),
            "--checklist",
            str(checklist_path),
            "--source-key",
            _SOURCE_KEY,
            "--output",
            str(definition_path),
            "--county",
            "Riverside",
            "--high-signal-only",
            "--page-size",
            "25",
            "--max-pages",
            "2",
        ],
    )
    assert definition_result.exit_code == 0, definition_result.output

    manifest_result = runner.invoke(
        app,
        [
            "build-manifest",
            "--definition",
            str(definition_path),
            "--window-start",
            "2026-07-01",
            "--window-end",
            "2026-07-07",
            "--output",
            str(manifest_path),
        ],
    )
    assert manifest_result.exit_code == 0, manifest_result.output
    return registry_path, checklist_path, definition_path, manifest_path


def test_cli_builds_ready_definition_and_exact_window_manifest(tmp_path: Path) -> None:
    _, _, definition_path, manifest_path = _build_cli_artifacts(tmp_path)

    definition = CeqanetRecurringRunDefinition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )
    manifest = CeqanetRecurringRunManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )

    assert definition.readiness is CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION
    assert definition.blockers == []
    assert manifest.definition_digest == definition.definition_digest
    assert manifest.query["received_from"] == "2026-07-01"
    assert manifest.query["received_to"] == "2026-07-07"
    assert manifest.query["max_pages"] == 2


def test_cli_execute_refuses_without_explicit_live_authorization(tmp_path: Path) -> None:
    registry_path, checklist_path, definition_path, manifest_path = _build_cli_artifacts(
        tmp_path
    )
    execution_path = tmp_path / "execution.json"

    result = runner.invoke(
        app,
        [
            "execute",
            "--definition",
            str(definition_path),
            "--manifest",
            str(manifest_path),
            "--registry",
            str(registry_path),
            "--checklist",
            str(checklist_path),
            "--output",
            str(execution_path),
        ],
    )

    assert result.exit_code == 1
    assert "explicit live execution authorization is required" in result.output
    assert not execution_path.exists()



def test_cli_exports_verified_authorized_recurring_attempt_for_discovery_queue(
    tmp_path: Path,
) -> None:
    """Recurring discovery can feed the exact same reviewed SCH queue without another GET."""

    registry_path, checklist_path, definition_path, manifest_path = _build_cli_artifacts(
        tmp_path
    )
    definition = CeqanetRecurringRunDefinition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )
    manifest = CeqanetRecurringRunManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    html = (
        '<div class="search-result">'
        '<a href="/Project/2026030377">Cabazon Infrastructure Plan</a>'
        '<span>SCH Number</span><span>2026030377</span>'
        '<span>County</span><span>Riverside</span>'
        '</div>'
    )
    low_level = CeqanetRecurringRunExecution(
        run_id=manifest.run_id,
        attempt_sequence=1,
        attempt_id="a" * 64,
        definition_digest=definition.definition_digest,
        manifest_digest=manifest.manifest_digest,
        source_key=manifest.source_key,
        execution_report={
            "metadata": {
                "schema_version": "ceqanet_listing_execution.v1",
                "allowed": True,
                "reason": "Synthetic complete bounded listing execution.",
                "planned_request_count": 1,
                "executed_request_count": 1,
                "successful_response_count": 1,
                "failed_response_count": 0,
                "maximum_records": 50,
                "query": manifest.query,
            },
            "snapshots": [
                {
                    "page_number": 1,
                    "method": "GET",
                    "request_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
                    "final_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
                    "status_code": 200,
                    "content_type": "text/html; charset=utf-8",
                    "body_text": html,
                    "body_length": len(html),
                    "body_truncated": False,
                    "executed": True,
                    "error": None,
                    "failure_kind": "none",
                    "reachable": True,
                }
            ],
        },
        network_executed=True,
    )
    execution = bind_authorized_recurring_listing_evidence(
        low_level,
        manifest,
        authorization={
            "action": "execute-ceqanet-recurring-run-attempt",
            "decision_id": "recurring-export-test-decision",
        },
    )
    execution_path = tmp_path / "execution.json"
    execution_path.write_text(
        json.dumps(execution.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    listing_path = tmp_path / "listing-v2.json"
    exported = runner.invoke(
        app,
        [
            "export-listing-evidence",
            "--definition",
            str(definition_path),
            "--manifest",
            str(manifest_path),
            "--execution",
            str(execution_path),
            "--registry",
            str(registry_path),
            "--checklist",
            str(checklist_path),
            "--output",
            str(listing_path),
        ],
    )
    assert exported.exit_code == 0, exported.output
    raw = listing_path.read_bytes()
    listing = json.loads(raw)
    assert listing["metadata"]["schema_version"] == "ceqanet_listing_execution.v2"
    assert listing["metadata"]["authorization"]["decision_id"] == (
        "recurring-export-test-decision"
    )
    queue = build_reviewed_ceqanet_capture_queue(listing, original_bytes=raw)
    assert queue["candidate_count"] == 1
    assert queue["candidates"][0]["sch_number"] == "2026030377"
    assert queue["candidates"][0]["source_claimed_county"] == "Riverside"
    assert queue["network_executed"] is False
    assert queue["persistence_mutated"] is False
