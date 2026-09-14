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


def _pass_evidence(
    root: Path,
    report: dict[str, Any],
    index: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    review_pass = report["passes"][index]
    assert isinstance(review_pass, dict)
    path = str(review_pass["artifact_path"])
    payload = json.loads((root / path).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return review_pass, payload, path


def _quality_gate_evidence(
    root: Path,
    report: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    gate = report["quality_gates"][0]
    assert isinstance(gate, dict)
    path = str(gate["artifact_path"])
    payload = json.loads((root / path).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload, path


def test_native_maximum_complete_evidence_passes(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)

    assert len(report["passes"]) == 5
    assert sum(value["kind"] == "deep_repository" for value in report["passes"]) == 3
    assert all(value["completed_reviews"] == 1 for value in report["passes"])
    assert _codes(_audit(tmp_path)) == set()


def test_assurance_rejects_non_fresh_pass(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["passes"][0]["fresh_context"] = False
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-009" in _codes(_audit(tmp_path))


def test_assurance_rejects_aggregated_completed_reviews(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["passes"][0]["completed_reviews"] = 3
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-009" in _codes(_audit(tmp_path))


def test_assurance_rejects_insufficient_deep_passes(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    report["passes"] = [
        value for value in report["passes"] if value["pass_id"] != "native-deep-3"
    ]
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-009" in _codes(_audit(tmp_path))


def test_assurance_rejects_deferred_candidate(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    for review_pass in report["passes"]:
        if review_pass["pass_id"] == "native-diff":
            review_pass["candidate_count"] = 1
            break
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
    review_pass, payload, path = _pass_evidence(tmp_path, report, 0)
    payload["completed_reviews"] = 99
    review_pass["artifact_sha256"] = write_json(tmp_path, path, payload)
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-010" in _codes(_audit(tmp_path))


def test_assurance_rejects_placeholder_source_hash(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    review_pass, payload, path = _pass_evidence(tmp_path, report, 0)
    payload["source_artifact_sha256"] = "0" * 64
    review_pass["artifact_sha256"] = write_json(tmp_path, path, payload)
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-027" in _codes(_audit(tmp_path))


def test_assurance_rejects_missing_source_artifact(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    _review_pass, payload, _path = _pass_evidence(tmp_path, report, 0)
    (tmp_path / str(payload["source_artifact_path"])).unlink()

    assert "ASSURANCE-027" in _codes(_audit(tmp_path))


def test_assurance_rejects_source_digest_mismatch(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    _review_pass, payload, _path = _pass_evidence(tmp_path, report, 0)
    write(tmp_path, str(payload["source_artifact_path"]), "{}\n")

    assert "ASSURANCE-027" in _codes(_audit(tmp_path))


def test_assurance_rejects_cross_commit_source_artifact(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    review_pass, payload, path = _pass_evidence(tmp_path, report, 0)
    source_path = str(payload["source_artifact_path"])
    source = json.loads((tmp_path / source_path).read_text(encoding="utf-8"))
    source["reviewed_commit"] = "1" * 40
    payload["source_artifact_sha256"] = write_json(tmp_path, source_path, source)
    review_pass["artifact_sha256"] = write_json(tmp_path, path, payload)
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-027" in _codes(_audit(tmp_path))


def test_assurance_rejects_reused_source_artifact(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    _first_pass, first_payload, _first_path = _pass_evidence(tmp_path, report, 0)
    second_pass, second_payload, second_path = _pass_evidence(tmp_path, report, 1)
    second_payload["source_artifact_path"] = first_payload["source_artifact_path"]
    second_payload["source_artifact_sha256"] = first_payload["source_artifact_sha256"]
    second_pass["artifact_sha256"] = write_json(tmp_path, second_path, second_payload)
    rewrite_assurance(tmp_path, report)

    assert "ASSURANCE-027" in _codes(_audit(tmp_path))


def test_assurance_rejects_quality_gate_source_digest_mismatch(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    payload, _path = _quality_gate_evidence(tmp_path, report)
    first_result = payload["gates"][0]
    write(tmp_path, str(first_result["source_artifact_path"]), "{}\n")

    assert "ASSURANCE-027" in _codes(_audit(tmp_path))


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
