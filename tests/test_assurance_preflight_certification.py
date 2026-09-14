from __future__ import annotations

from constructionsight.assurance_preflight_certification import preflight_findings
from constructionsight.governance_certification_core import _finding


def test_preflight_allows_only_assurance_transaction_blockers() -> None:
    findings = (
        _finding(
            "ASSURANCE-001",
            "governance/reviews/assurance_review.json",
            "missing assurance",
        ),
        _finding(
            "DEFECT-ACTIVE-001",
            "governance/active_defects.toml",
            "active defect",
        ),
    )

    assert preflight_findings(findings) == ()


def test_preflight_retains_any_other_governance_finding() -> None:
    findings = (
        _finding(
            "DEFECT-ACTIVE-001",
            "governance/active_defects.toml",
            "active defect",
        ),
        _finding(
            "ARCH-CAP-001",
            "src/constructionsight/example.py",
            "network authority drift",
        ),
    )

    blockers = preflight_findings(findings)

    assert len(blockers) == 1
    assert blockers[0].code == "ARCH-CAP-001"
