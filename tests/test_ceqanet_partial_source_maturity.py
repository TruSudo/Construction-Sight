from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringQueryTemplate,
    CeqanetRunReadiness,
    CeqanetWindowField,
)
from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
)
from constructionsight.models import PublicSource, VerificationStatus
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistReport,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence/source_verification"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ceqanet_partial_maturity_is_evidenced_but_execution_blocked() -> None:
    registry_payload = _load_json(ROOT / "data/source_registry.seed.json")
    sources = [PublicSource.model_validate(item) for item in registry_payload]
    ceqanet_sources = [source for source in sources if source.platform_family.value == "ceqanet"]

    assert len(ceqanet_sources) == 1
    ceqanet = ceqanet_sources[0]
    assert ceqanet.verification_status is VerificationStatus.PARTIAL
    assert ceqanet.last_checked_date is None

    evidence_path = EVIDENCE_DIR / "ceqanet_public_access_2026-07-12.json"
    checklist_path = EVIDENCE_DIR / "ceqanet_checklist_2026-07-12.json"
    observations_path = EVIDENCE_DIR / "ceqanet_observations_2026-07-12.json"
    plan_path = EVIDENCE_DIR / "ceqanet_partial_update_plan_2026-07-12.json"
    audit_path = EVIDENCE_DIR / "ceqanet_partial_apply_audit_2026-07-12.json"

    for path in (evidence_path, checklist_path, observations_path, plan_path, audit_path):
        assert path.is_file(), f"missing CEQAnet maturity evidence artifact: {path}"

    evidence = _load_json(evidence_path)
    assert evidence["schema_version"] == "ceqanet_source_verification_evidence.v1"
    assert evidence["bounded_search"]["document_downloads"] is False
    assert evidence["bounded_search"]["persistence_mutated"] is False
    assert evidence["access_barrier_observation"] == {
        "captcha_observed": False,
        "login_required": False,
        "paywall_observed": False,
    }

    checklist = SourceVerificationChecklistReport.model_validate(_load_json(checklist_path))
    assert len(checklist.rows) == 1
    row = checklist.rows[0]
    assert row.public_entry_page is ChecklistItemStatus.OBSERVED
    assert row.query_behavior is ChecklistItemStatus.OBSERVED
    assert row.result_list is ChecklistItemStatus.OBSERVED
    assert row.detail_page is ChecklistItemStatus.OBSERVED
    assert row.access_barrier is ChecklistItemStatus.NOT_OBSERVED
    assert row.terms_review is ChecklistItemStatus.NOT_CHECKED
    assert row.evidence_refs == [
        "evidence/source_verification/ceqanet_public_access_2026-07-12.json"
    ]

    plan = _load_json(plan_path)
    assert plan["update_count"] == 1
    partial_rows = [
        item
        for item in plan["rows"]
        if item["source_name"] == "CEQAnet State Clearinghouse"
    ]
    assert len(partial_rows) == 1
    assert partial_rows[0]["proposed_verification_status"] == "partial"
    assert partial_rows[0]["update_required"] is True

    audit = _load_json(audit_path)
    assert audit["applied_count"] == 1
    assert audit["registry_changed"] is True
    applied_rows = [
        item
        for item in audit["rows"]
        if item["source_name"] == "CEQAnet State Clearinghouse"
    ]
    assert len(applied_rows) == 1
    assert applied_rows[0]["previous_verification_status"] == "unverified"
    assert applied_rows[0]["resulting_verification_status"] == "partial"
    assert applied_rows[0]["applied"] is True

    definition = build_ceqanet_recurring_run_definition(
        sources,
        checklist,
        source_key=row.source_key,
        query_template=CeqanetRecurringQueryTemplate(
            counties=["San Bernardino"],
            window_field=CeqanetWindowField.RECEIVED,
            page_size=25,
            max_pages=1,
        ),
    )
    assert definition.readiness is CeqanetRunReadiness.BLOCKED
    assert "source registry status is not verified" in definition.blockers
    assert "terms review evidence is not observed" in definition.blockers
    assert "source verification evidence references are missing" not in definition.blockers

    assert not (ROOT / ".github/workflows/ceqanet-source-evidence.yml").exists()
    assert not (ROOT / "scripts/collect_ceqanet_source_evidence.py").exists()
