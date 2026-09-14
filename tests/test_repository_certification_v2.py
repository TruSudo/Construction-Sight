from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import constructionsight.repository_certification_v2 as certification_v2
from constructionsight.repository_certification import (
    CertificationFinding,
    CertificationReport,
)


def test_v2_includes_semantic_ci_permission_findings(monkeypatch) -> None:
    base_report = CertificationReport(
        schema_version="constructionsight.repository_certification.v1",
        tracked_file_count=1,
        source_python_count=1,
        test_python_count=1,
        finding_count=0,
        findings=(),
    )
    permission_finding = CertificationFinding(
        code="CERT-CI-005",
        path=".github/workflows/ci.yml",
        line=None,
        message="write permission",
    )
    governance_report = SimpleNamespace(
        passed=True,
        finding_count=0,
        to_dict=lambda: {"passed": True, "finding_count": 0, "findings": []},
    )

    monkeypatch.setattr(
        certification_v2,
        "audit_repository",
        lambda root, require_clean_worktree: base_report,
    )
    monkeypatch.setattr(
        certification_v2,
        "audit_ci_permissions",
        lambda root: (permission_finding,),
    )
    monkeypatch.setattr(
        certification_v2,
        "audit_governance",
        lambda root, tracked: governance_report,
    )
    monkeypatch.setattr(certification_v2, "_tracked_files", lambda root: ())

    report = certification_v2.certify_repository(Path("."))

    assert report["passed"] is False
    assert report["finding_count"] == 1
    repository = report["repository"]
    assert repository["finding_count"] == 1
    assert repository["findings"][0]["code"] == "CERT-CI-005"
