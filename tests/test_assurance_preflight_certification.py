from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import constructionsight.assurance_preflight_certification as preflight
from constructionsight.governance_certification_core import _finding
from constructionsight.repository_certification import CertificationFinding


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

    assert preflight.preflight_findings(findings) == ()


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

    blockers = preflight.preflight_findings(findings)

    assert len(blockers) == 1
    assert blockers[0].code == "ARCH-CAP-001"


def test_preflight_retains_repository_findings(monkeypatch) -> None:
    repository_finding = CertificationFinding(
        code="CERT-CI-003",
        path=".github/workflows/ci.yml",
        line=None,
        message="CI permissions must remain read-only",
    )
    monkeypatch.setattr(
        preflight,
        "audit_repository",
        lambda root, require_clean_worktree: SimpleNamespace(
            findings=(repository_finding,),
            finding_count=1,
        ),
    )
    monkeypatch.setattr(preflight, "audit_ci_permissions", lambda root: ())
    monkeypatch.setattr(
        preflight,
        "audit_governance",
        lambda root, tracked: SimpleNamespace(findings=(), finding_count=0),
    )
    monkeypatch.setattr(preflight, "_tracked_files", lambda root: ())

    report = preflight.build_report(Path("."))

    assert report["passed"] is False
    findings = report["findings"]
    assert isinstance(findings, list)
    assert findings[0]["code"] == "CERT-CI-003"


def test_preflight_retains_semantic_permission_findings(monkeypatch) -> None:
    permission_finding = CertificationFinding(
        code="CERT-CI-005",
        path=".github/workflows/ci.yml",
        line=None,
        message="write permission",
    )
    monkeypatch.setattr(
        preflight,
        "audit_repository",
        lambda root, require_clean_worktree: SimpleNamespace(
            findings=(),
            finding_count=0,
        ),
    )
    monkeypatch.setattr(
        preflight,
        "audit_ci_permissions",
        lambda root: (permission_finding,),
    )
    monkeypatch.setattr(
        preflight,
        "audit_governance",
        lambda root, tracked: SimpleNamespace(findings=(), finding_count=0),
    )
    monkeypatch.setattr(preflight, "_tracked_files", lambda root: ())

    report = preflight.build_report(Path("."))

    assert report["passed"] is False
    findings = report["findings"]
    assert isinstance(findings, list)
    assert findings[0]["code"] == "CERT-CI-005"
