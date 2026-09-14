from __future__ import annotations

from pathlib import Path

from constructionsight.authority_certification import _reviewed_tree_digest
from constructionsight.governance_certification import (
    _audit_assurance_reviewed_tree_binding,
)
from constructionsight.governance_certification_core import GovernanceFinding
from tests.support.assurance import (
    active_ledger,
    git,
    initialize_repository,
    rewrite_assurance,
    write,
    write_assurance,
)


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_assurance_rejects_rebinding_old_review_to_newer_covered_tree(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    reviewed_commit = git(tmp_path, "rev-parse", "HEAD")
    report = write_assurance(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=_reviewed_tree_digest(tmp_path),
    )

    write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'changed-after-review'\n")
    git(tmp_path, "add", "src/constructionsight/reviewed.py")
    git(tmp_path, "commit", "-m", "change covered implementation after review")

    # Reproduce the pre-fix attack: keep every analytical artifact bound to the
    # older reviewed commit, but replace only the report digest with the newer
    # implementation tree digest.
    report["reviewed_tree_digest"] = _reviewed_tree_digest(tmp_path)
    rewrite_assurance(tmp_path, report)

    findings: list[GovernanceFinding] = []
    _audit_assurance_reviewed_tree_binding(tmp_path, findings)

    assert "ASSURANCE-026" in _codes(findings)


def test_assurance_allows_only_permitted_finalization_tree_drift(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    reviewed_commit = git(tmp_path, "rev-parse", "HEAD")
    write_assurance(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=_reviewed_tree_digest(tmp_path),
    )

    write(
        tmp_path,
        "governance/active_defects.toml",
        active_ledger(
            [
                {
                    "id": "CS-SR-999",
                    "severity": "P3",
                    "area": "test-finalization",
                    "root_cause": "Test-only finalization ledger change.",
                    "discovered_against": reviewed_commit,
                    "required_resolution": "Test-only finalization proof.",
                }
            ]
        ),
    )
    git(tmp_path, "add", "governance/active_defects.toml")
    git(tmp_path, "commit", "-m", "permitted finalization ledger change")

    findings: list[GovernanceFinding] = []
    _audit_assurance_reviewed_tree_binding(tmp_path, findings)

    assert "ASSURANCE-026" not in _codes(findings)
