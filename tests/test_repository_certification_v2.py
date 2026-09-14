from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import constructionsight.repository_certification_v2 as certification_v2
from constructionsight.repository_certification import (
    CertificationFinding,
    CertificationReport,
)


def _base_report() -> CertificationReport:
    return CertificationReport(
        schema_version="constructionsight.repository_certification.v1",
        tracked_file_count=1,
        source_python_count=1,
        test_python_count=1,
        finding_count=0,
        findings=(),
    )


def _governance_report() -> SimpleNamespace:
    return SimpleNamespace(
        passed=True,
        finding_count=0,
        to_dict=lambda: {"passed": True, "finding_count": 0, "findings": []},
    )


def _isolate(monkeypatch) -> None:
    monkeypatch.setattr(
        certification_v2,
        "audit_repository",
        lambda root, require_clean_worktree: _base_report(),
    )
    monkeypatch.setattr(certification_v2, "audit_ci_permissions", lambda root: ())
    monkeypatch.setattr(certification_v2, "audit_vulnerability_job", lambda root: ())
    monkeypatch.setattr(certification_v2, "audit_ci_actions", lambda root: ())
    monkeypatch.setattr(
        certification_v2,
        "audit_governance",
        lambda root, tracked: _governance_report(),
    )
    monkeypatch.setattr(certification_v2, "_tracked_files", lambda root: ())


def test_v2_includes_semantic_ci_permission_findings(monkeypatch) -> None:
    permission_finding = CertificationFinding(
        code="CERT-CI-005",
        path=".github/workflows/ci.yml",
        line=None,
        message="write permission",
    )
    _isolate(monkeypatch)
    monkeypatch.setattr(
        certification_v2,
        "audit_ci_permissions",
        lambda root: (permission_finding,),
    )

    report = certification_v2.certify_repository(Path("."))

    assert report["passed"] is False
    assert report["finding_count"] == 1
    repository = report["repository"]
    assert repository["finding_count"] == 1
    assert repository["findings"][0]["code"] == "CERT-CI-005"


def test_v2_includes_action_runtime_findings(monkeypatch) -> None:
    action_finding = CertificationFinding(
        code="CERT-CI-006",
        path=".github/workflows/ci.yml",
        line=12,
        message="stale action runtime",
    )
    _isolate(monkeypatch)
    monkeypatch.setattr(
        certification_v2,
        "audit_ci_actions",
        lambda root: (action_finding,),
    )

    report = certification_v2.certify_repository(Path("."))

    assert report["passed"] is False
    assert report["finding_count"] == 1
    repository = report["repository"]
    assert repository["finding_count"] == 1
    assert repository["findings"][0]["code"] == "CERT-CI-006"


def test_v2_retains_native_vulnerability_job_findings(monkeypatch) -> None:
    _isolate(monkeypatch)
    finding = CertificationFinding(
        code="CERT-CI-007", path=".github/workflows/ci.yml", line=None, message="scanner disabled"
    )
    monkeypatch.setattr(certification_v2, "audit_vulnerability_job", lambda root: (finding,))
    report = certification_v2.certify_repository(Path("."))
    assert report["passed"] is False
    assert report["repository"]["findings"][0]["code"] == "CERT-CI-007"
