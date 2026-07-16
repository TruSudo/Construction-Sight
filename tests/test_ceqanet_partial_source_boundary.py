from __future__ import annotations

import json
from pathlib import Path

from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringQueryTemplate,
    CeqanetRunReadiness,
)
from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
)
from constructionsight.models import PublicSource, VerificationStatus
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data/source_registry.seed.json"
EVIDENCE_PATH = ROOT / "evidence/source_verification/ceqanet_public_access_2026-07-12.json"
CHECKLIST_PATH = ROOT / "evidence/source_verification/ceqanet_checklist_2026-07-12.json"


def _load_sources() -> list[PublicSource]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return [PublicSource.model_validate(row) for row in payload]


def test_canonical_registry_preserves_ceqanet_partial_maturity() -> None:
    sources = _load_sources()
    ceqanet_sources = [source for source in sources if source.platform_family.value == "ceqanet"]

    assert len(ceqanet_sources) == 1
    assert ceqanet_sources[0].verification_status is VerificationStatus.PARTIAL
    assert ceqanet_sources[0].last_checked_date is not None
    assert sum(source.verification_status is VerificationStatus.PARTIAL for source in sources) == 1
    assert (
        sum(source.verification_status is VerificationStatus.UNVERIFIED for source in sources) == 3
    )
    assert all(source.verification_status is not VerificationStatus.VERIFIED for source in sources)


def test_ceqanet_evidence_and_checklist_match_partial_boundary() -> None:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    checklist = SourceVerificationChecklistReport.model_validate_json(
        CHECKLIST_PATH.read_text(encoding="utf-8")
    )

    assert evidence["schema_version"] == "ceqanet_source_verification_evidence.v2"
    assert evidence["recommended_registry_status"] == "partial"
    assert evidence["verified_status_authorized"] is False
    assert evidence["access_assessment"]["automated_access_currently_reliable"] is False
    assert evidence["access_assessment"]["automation_blocker"] == (
        "HTTP 403 observed during bounded automated collection"
    )
    assert evidence["collection_actions"] == {
        "documents_downloaded": False,
        "persistence_mutated": False,
        "outreach_sent": False,
        "security_controls_bypassed": False,
    }

    assert checklist.source_count == 1
    row = checklist.rows[0]
    assert row.registry_status == "partial"
    assert row.terms_review.value == "observed"
    assert row.access_barrier.value == "needs_manual_review"
    assert row.recommendation == "retain_partial_and_prioritize_official_csv_access"


def test_partial_ceqanet_source_cannot_unlock_recurring_execution() -> None:
    sources = _load_sources()
    checklist = SourceVerificationChecklistReport.model_validate_json(
        CHECKLIST_PATH.read_text(encoding="utf-8")
    )

    definition = build_ceqanet_recurring_run_definition(
        sources,
        checklist,
        source_key="source:ceqanet-state-clearinghouse",
        query_template=CeqanetRecurringQueryTemplate(
            counties=["San Bernardino"],
            page_size=25,
            max_pages=1,
        ),
    )

    assert definition.readiness is CeqanetRunReadiness.BLOCKED
    assert "source registry status is not verified" in definition.blockers
    assert definition.registry_verification_status == "partial"
    definition.assert_integrity()
