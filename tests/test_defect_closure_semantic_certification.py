from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

from constructionsight.defect_closure_certification import (
    _canonical_semantic_summary,
    audit_defect_closure,
)
from constructionsight.governance_certification_core import GovernanceFinding
from tests.support.assurance import (
    active_ledger,
    git,
    initialize_repository,
    resolved_ledger,
    write,
    write_json,
)

DEFECT_ID = "CS-SR-093"
CONTRACT = (
    'schema_version = "constructionsight.defect-closure-semantic-contract/v1"\n'
    "semantic_proof_required = true\n"
)


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def _prepare(
    root: Path,
    *,
    digest_override: str | None = None,
    assertion_value: str = "VALUE = 'corrected'",
    summary_override: str | None = None,
) -> None:
    initialize_repository(root)
    discovery_commit = git(root, "rev-parse", "HEAD")
    required_resolution = (
        "Require deterministic semantic closure evidence that rejects unsupported "
        "or contradictory closure claims."
    )
    defect = {
        "id": DEFECT_ID,
        "severity": "P1",
        "area": "defect-closure-semantic-certification",
        "root_cause": "Closure could rely on self-asserted prose alone.",
        "discovered_against": discovery_commit,
        "required_resolution": required_resolution,
    }
    write(root, "governance/active_defects.toml", active_ledger([defect]))
    git(root, "add", "governance/active_defects.toml")
    git(root, "commit", "-m", "register semantic closure defect")

    write(root, "governance/defect_closure_semantic_contract.toml", CONTRACT)
    write(root, "src/constructionsight/reviewed.py", "VALUE = 'corrected'\n")
    write(
        root,
        "tests/test_resolution.py",
        "# Regression: CS-SR-093\n"
        "def test_resolution() -> None:\n"
        "    assert True\n",
    )
    closure_evidence = "docs/assurance/defect_closures/CS-SR-093.md"
    proof_path = "docs/assurance/defect_closures/CS-SR-093.proof.json"
    write(
        root,
        closure_evidence,
        "# CS-SR-093 closure\n\nMachine-verifiable semantic proof retained.\n",
    )
    digest = hashlib.sha256(required_resolution.encode("utf-8")).hexdigest()
    write_json(
        root,
        proof_path,
        {
            "schema_version": "constructionsight.defect-closure-proof/v1",
            "defect_id": DEFECT_ID,
            "required_resolution_sha256": digest_override or digest,
            "implementation_assertions": [
                {
                    "path": "src/constructionsight/reviewed.py",
                    "operator": "contains",
                    "value": assertion_value,
                },
                {
                    "path": "src/constructionsight/reviewed.py",
                    "operator": "not_contains",
                    "value": "VALUE = 'unsafe'",
                },
            ],
            "regression_assertions": [
                {
                    "path": "tests/test_resolution.py",
                    "operator": "contains",
                    "value": "CS-SR-093",
                }
            ],
        },
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "implement semantic closure proof")
    resolution_commit = git(root, "rev-parse", "HEAD")
    resolution_tree = git(root, "rev-parse", f"{resolution_commit}^{{tree}}")

    evidence_paths = [
        "src/constructionsight/reviewed.py",
        closure_evidence,
        proof_path,
    ]
    regression_tests = ["tests/test_resolution.py"]
    summary = _canonical_semantic_summary(
        DEFECT_ID,
        digest,
        {"src/constructionsight/reviewed.py"},
        {"tests/test_resolution.py"},
    )
    closure: dict[str, Any] = {
        **defect,
        "resolution_summary": summary_override or summary,
        "resolution_commit": resolution_commit,
        "resolution_tree": resolution_tree,
        "last_active_commit": resolution_commit,
        "evidence_paths": evidence_paths,
        "regression_tests": regression_tests,
        "closure_evidence": closure_evidence,
    }
    write(root, "governance/active_defects.toml", active_ledger([]))
    write(root, "governance/resolved_defects.toml", resolved_ledger([closure]))


def _audit(root: Path) -> list[GovernanceFinding]:
    active = tomllib.loads(
        (root / "governance/active_defects.toml").read_text(encoding="utf-8")
    )
    resolved = tomllib.loads(
        (root / "governance/resolved_defects.toml").read_text(encoding="utf-8")
    )
    findings: list[GovernanceFinding] = []
    audit_defect_closure(root, active, resolved, findings)
    return findings


def test_semantic_closure_accepts_changed_code_and_tagged_regression(
    tmp_path: Path,
) -> None:
    _prepare(tmp_path)

    assert _audit(tmp_path) == []


def test_semantic_closure_rejects_wrong_required_resolution_digest(
    tmp_path: Path,
) -> None:
    _prepare(tmp_path, digest_override="0" * 64)

    assert "DEFECT-CLOSURE-012" in _codes(_audit(tmp_path))


def test_semantic_closure_rejects_false_content_assertion(tmp_path: Path) -> None:
    _prepare(tmp_path, assertion_value="VALUE = 'not-present'")

    assert "DEFECT-CLOSURE-012" in _codes(_audit(tmp_path))


def test_semantic_closure_rejects_freeform_or_contradictory_summary(
    tmp_path: Path,
) -> None:
    _prepare(tmp_path, summary_override="Everything passed with no blockers.")

    assert "DEFECT-CLOSURE-012" in _codes(_audit(tmp_path))
