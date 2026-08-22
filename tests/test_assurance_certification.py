from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from constructionsight.assurance_certification import audit_assurance_contract
from constructionsight.authority_certification import (
    _audit_defects_and_review,
    _reviewed_tree_digest,
)
from constructionsight.governance_certification_core import GovernanceFinding
from tests.support.assurance import (
    git,
    initialize_repository,
    rewrite_assurance,
    rewrite_candidate_union,
    write,
    write_assurance,
    write_json,
)


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def _valid_assurance(
    root: Path,
    *,
    mode: str = "native_maximum",
) -> dict[str, Any]:
    initialize_repository(root)
    reviewed_commit = git(root, "rev-parse", "HEAD")
    return write_assurance(
        root,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=_reviewed_tree_digest(root),
        mode=mode,
    )


def _audit(root: Path) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(root, findings)
    return findings


def _candidate_union(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    reference = report["candidate_union"]
    assert isinstance(reference, dict)
    payload = json.loads((root / str(reference["artifact_path"])).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_native_maximum_complete_evidence_passes(tmp_path: Path) -> None:
    _valid_assurance(tmp_path)

    assert _codes(_audit(tmp_path)) == set()


def test_assurance_rejects_non_fresh_pass(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["passes"][0]["fresh_context"] = False
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-009" in _codes(_audit(tmp_path))


def test_assurance_rejects_insufficient_deep_passes(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["passes"][0]["completed_reviews"] = 2
    report["passes"][1]["completed_reviews"] = 2
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-009" in _codes(_audit(tmp_path))


def test_assurance_rejects_deferred_candidate(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["passes"][1]["candidate_count"] = 1
    union = _candidate_union(tmp_path, report)
    union["candidates"] = [
        {
            "id": "CS-AC-001",
            "source_pass_ids": ["native-diff"],
            "severity": "P1",
            "disposition": "deferred",
            "rationale": "Requires later investigation.",
            "resolution_commit": None,
            "evidence_paths": ["src/constructionsight/reviewed.py"],
        }
    ]
    rewrite_candidate_union(tmp_path, report, union)

    assert "ASSURANCE-012" in _codes(_audit(tmp_path))


def test_assurance_rejects_evidence_digest_mismatch(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["passes"][0]["artifact_sha256"] = "0" * 64
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-010" in _codes(_audit(tmp_path))


def test_assurance_rejects_pass_evidence_disagreement(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    review_pass = report["passes"][0]
    path = str(review_pass["artifact_path"])
    payload = json.loads((tmp_path / path).read_text(encoding="utf-8"))
    payload["completed_reviews"] = 99
    review_pass["artifact_sha256"] = write_json(tmp_path, path, payload)
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-010" in _codes(_audit(tmp_path))


def test_assurance_rejects_candidate_union_coverage_gap(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    union = _candidate_union(tmp_path, report)
    union["coverage_complete"] = False
    union["coverage_gaps"] = ["src/constructionsight/reviewed.py"]
    rewrite_candidate_union(tmp_path, report, union)

    assert "ASSURANCE-012" in _codes(_audit(tmp_path))


def test_assurance_rejects_surviving_security_mutant(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["surviving_security_mutants"] = 1
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-015" in _codes(_audit(tmp_path))


def test_assurance_rejects_quality_gate_evidence_disagreement(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["quality_gates"][0]["status"] = "failed"
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-015" in _codes(_audit(tmp_path))


def test_external_model_mode_is_additive_and_not_human(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path, mode="independent_external_model")

    assert report["independence_claim"] == "independent_external_model_not_human"
    assert _codes(_audit(tmp_path)) == set()


def test_native_mode_rejects_external_independence_claim(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["independence_claim"] = "independent_external_model_not_human"
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-007" in _codes(_audit(tmp_path))


def test_assurance_rejects_unreferenced_evidence_file(tmp_path: Path) -> None:
    _valid_assurance(tmp_path)
    write(tmp_path, "governance/reviews/evidence/unreferenced.json", "{}\n")

    assert "ASSURANCE-022" in _codes(_audit(tmp_path))


def test_assurance_contract_rejects_weakened_policy() -> None:
    contract = tomllib.loads(
        Path("governance/assurance_contract.toml").read_text(encoding="utf-8")
    )
    contract["bypass_allowed"] = True
    contract["minimum_context_isolated_passes"] = 1
    findings: list[GovernanceFinding] = []

    audit_assurance_contract(contract, findings)

    assert {"ASSURANCE-POLICY-003", "ASSURANCE-POLICY-006"} <= _codes(findings)
