from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringQueryTemplate,
    CeqanetRunReadiness,
    CeqanetWindowField,
)
from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
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


def test_ceqanet_verified_manual_read_maturity_is_fully_evidenced() -> None:
    registry_payload = _load_json(ROOT / "data/source_registry.seed.json")
    sources = [PublicSource.model_validate(item) for item in registry_payload]
    ceqanet_sources = [source for source in sources if source.platform_family.value == "ceqanet"]

    assert len(ceqanet_sources) == 1
    ceqanet = ceqanet_sources[0]
    assert ceqanet.verification_status is VerificationStatus.VERIFIED
    assert ceqanet.last_checked_date is None
    assert all(
        source.verification_status is VerificationStatus.UNVERIFIED
        for source in sources
        if source.platform_family.value != "ceqanet"
    )

    evidence_path = EVIDENCE_DIR / "ceqanet_public_access_2026-07-12.json"
    raw_checklist_path = EVIDENCE_DIR / "ceqanet_checklist_2026-07-12.json"
    terms_path = EVIDENCE_DIR / "ceqanet_terms_review_2026-07-12.json"
    observations_path = EVIDENCE_DIR / "ceqanet_observations_2026-07-12.json"
    reviewed_checklist_path = EVIDENCE_DIR / "ceqanet_verified_checklist_2026-07-12.json"
    plan_path = EVIDENCE_DIR / "ceqanet_verified_update_plan_2026-07-12.json"
    audit_path = EVIDENCE_DIR / "ceqanet_verified_apply_audit_2026-07-12.json"

    artifacts = (
        evidence_path,
        raw_checklist_path,
        terms_path,
        observations_path,
        reviewed_checklist_path,
        plan_path,
        audit_path,
    )
    for path in artifacts:
        assert path.is_file(), f"missing CEQAnet verification artifact: {path}"

    evidence = _load_json(evidence_path)
    assert evidence["schema_version"] == "ceqanet_source_verification_evidence.v1"
    assert evidence["bounded_search"]["document_downloads"] is False
    assert evidence["bounded_search"]["persistence_mutated"] is False
    assert evidence["public_detail"]["document_downloads"] is False
    assert evidence["public_detail"]["persistence_mutated"] is False
    assert {
        "sch_number",
        "project_info",
        "title",
        "description",
    }.issubset(evidence["public_detail"]["observed_field_markers"])
    assert len(evidence["public_detail"]["observed_field_markers"]) >= 5
    assert evidence["access_barrier_observation"] == {
        "captcha_observed": False,
        "login_required": False,
        "paywall_observed": False,
    }

    raw_checklist = SourceVerificationChecklistReport.model_validate(
        _load_json(raw_checklist_path)
    )
    assert len(raw_checklist.rows) == 1
    assert raw_checklist.rows[0].terms_review is ChecklistItemStatus.NOT_CHECKED

    terms = _load_json(terms_path)
    assert terms["schema_version"] == "ceqanet_terms_review.v1"
    assert (
        terms["conclusion"]
        == "no_explicit_restriction_observed_for_bounded_public_read_only_access"
    )
    assert set(terms["reviewed_pages"]) == {
        "accessibility",
        "conditions_of_use",
        "privacy_policy",
    }
    assert all(
        record["status_code"] == 200 and len(record["body_sha256"]) == 64
        for record in terms["reviewed_pages"].values()
    )

    reviewed_checklist = SourceVerificationChecklistReport.model_validate(
        _load_json(reviewed_checklist_path)
    )
    assert len(reviewed_checklist.rows) == 4
    reviewed_rows = [
        row for row in reviewed_checklist.rows if row.source_name == "CEQAnet State Clearinghouse"
    ]
    assert len(reviewed_rows) == 1
    row = reviewed_rows[0]
    assert row.registry_status == "verified"
    assert row.public_entry_page is ChecklistItemStatus.OBSERVED
    assert row.query_behavior is ChecklistItemStatus.OBSERVED
    assert row.result_list is ChecklistItemStatus.OBSERVED
    assert row.detail_page is ChecklistItemStatus.OBSERVED
    assert row.access_barrier is ChecklistItemStatus.NOT_OBSERVED
    assert row.terms_review is ChecklistItemStatus.OBSERVED
    assert set(row.evidence_refs) == {
        "evidence/source_verification/ceqanet_public_access_2026-07-12.json",
        "evidence/source_verification/ceqanet_terms_review_2026-07-12.json",
    }

    plan = _load_json(plan_path)
    assert plan["update_count"] == 1
    verified_rows = [
        item
        for item in plan["rows"]
        if item["source_name"] == "CEQAnet State Clearinghouse"
    ]
    assert len(verified_rows) == 1
    assert verified_rows[0]["proposed_verification_status"] == "verified"
    assert verified_rows[0]["planned_action"] == "verified_candidate_review"
    assert verified_rows[0]["update_required"] is True

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
    assert applied_rows[0]["resulting_verification_status"] == "verified"
    assert applied_rows[0]["applied"] is True

    definition = build_ceqanet_recurring_run_definition(
        sources,
        reviewed_checklist,
        source_key=row.source_key,
        query_template=CeqanetRecurringQueryTemplate(
            counties=["San Bernardino"],
            window_field=CeqanetWindowField.RECEIVED,
            page_size=25,
            max_pages=1,
        ),
    )
    assert definition.readiness is CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION
    assert definition.blockers == []
    definition.assert_integrity()

    manifest = build_ceqanet_recurring_run_manifest(
        definition,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 7),
    )
    assert manifest.readiness is CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION
    assert manifest.operator_live_authorization_required is True
    assert manifest.persistence_authorized is False
    manifest.assert_integrity()

    temporary_paths = (
        ROOT / ".github/workflows/ceqanet-source-evidence.yml",
        ROOT / "scripts/collect_ceqanet_source_evidence.py",
        ROOT / ".github/workflows/ceqanet-evidence-repair-partial.yml",
        ROOT / "scripts/repair_ceqanet_evidence_partial.py",
        ROOT / "scripts/repair_ceqanet_evidence_verified.py",
        ROOT / "scripts/patch_ceqanet_collector_current.py",
    )
    assert all(not path.exists() for path in temporary_paths)
