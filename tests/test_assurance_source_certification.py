from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constructionsight.authority_certification import (
    _audit_defects_and_review,
    _reviewed_tree_digest,
)
from constructionsight.governance_certification_core import GovernanceFinding
from tests.support.assurance import (
    git,
    initialize_repository,
    rewrite_assurance,
    write_assurance,
    write_json,
)


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def _valid_assurance(root: Path) -> dict[str, Any]:
    initialize_repository(root)
    reviewed_commit = git(root, "rev-parse", "HEAD")
    return write_assurance(
        root,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=_reviewed_tree_digest(root),
    )


def _audit(root: Path) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(root, findings)
    return findings


def _pass_evidence(
    root: Path,
    report: dict[str, Any],
    index: int = 0,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    review_pass = report["passes"][index]
    assert isinstance(review_pass, dict)
    path = str(review_pass["artifact_path"])
    payload = json.loads((root / path).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return review_pass, payload, path


def _load_source(root: Path, evidence: dict[str, Any]) -> tuple[dict[str, Any], str]:
    source_path = str(evidence["source_artifact_path"])
    source = json.loads((root / source_path).read_text(encoding="utf-8"))
    assert isinstance(source, dict)
    return source, source_path


def _rewrite_pass_source(
    root: Path,
    report: dict[str, Any],
    review_pass: dict[str, Any],
    evidence: dict[str, Any],
    evidence_path: str,
    source: dict[str, Any],
    source_path: str,
) -> None:
    evidence["source_artifact_sha256"] = write_json(root, source_path, source)
    review_pass["artifact_sha256"] = write_json(root, evidence_path, evidence)
    rewrite_assurance(root, report)


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


def _rewrite_quality_source(
    root: Path,
    report: dict[str, Any],
    evidence: dict[str, Any],
    evidence_path: str,
    source: dict[str, Any],
    source_path: str,
) -> None:
    first_result = evidence["gates"][0]
    assert isinstance(first_result, dict)
    first_result["source_artifact_sha256"] = write_json(root, source_path, source)
    evidence_digest = write_json(root, evidence_path, evidence)
    for gate in report["quality_gates"]:
        assert isinstance(gate, dict)
        if gate.get("artifact_path") == evidence_path:
            gate["artifact_sha256"] = evidence_digest
    rewrite_assurance(root, report)


def test_assurance_rejects_raw_provider_mismatch(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    review_pass, evidence, evidence_path = _pass_evidence(tmp_path, report)
    source, source_path = _load_source(tmp_path, evidence)
    payload = source["payload"]
    assert isinstance(payload, dict)
    payload["provider"] = "forged-provider"
    _rewrite_pass_source(
        tmp_path,
        report,
        review_pass,
        evidence,
        evidence_path,
        source,
        source_path,
    )

    assert "ASSURANCE-028" in _codes(_audit(tmp_path))


def test_assurance_rejects_raw_candidate_count_mismatch(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    review_pass, evidence, evidence_path = _pass_evidence(tmp_path, report)
    source, source_path = _load_source(tmp_path, evidence)
    payload = source["payload"]
    assert isinstance(payload, dict)
    payload["candidate_count"] = 99
    _rewrite_pass_source(
        tmp_path,
        report,
        review_pass,
        evidence,
        evidence_path,
        source,
        source_path,
    )

    assert "ASSURANCE-028" in _codes(_audit(tmp_path))


def test_assurance_rejects_raw_source_producer_mismatch(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    review_pass, evidence, evidence_path = _pass_evidence(tmp_path, report)
    source, source_path = _load_source(tmp_path, evidence)
    source["producer"] = "forged-tool"
    _rewrite_pass_source(
        tmp_path,
        report,
        review_pass,
        evidence,
        evidence_path,
        source,
        source_path,
    )

    assert "ASSURANCE-028" in _codes(_audit(tmp_path))


def test_assurance_rejects_nonobject_raw_payload(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    review_pass, evidence, evidence_path = _pass_evidence(tmp_path, report)
    source, source_path = _load_source(tmp_path, evidence)
    source["payload"] = "forged-nonobject-payload"
    _rewrite_pass_source(
        tmp_path,
        report,
        review_pass,
        evidence,
        evidence_path,
        source,
        source_path,
    )

    assert "ASSURANCE-028" in _codes(_audit(tmp_path))


def test_assurance_rejects_raw_quality_gate_failure(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    evidence, evidence_path = _quality_gate_evidence(tmp_path, report)
    first_result = evidence["gates"][0]
    assert isinstance(first_result, dict)
    source, source_path = _load_source(tmp_path, first_result)
    payload = source["payload"]
    assert isinstance(payload, dict)
    payload["status"] = "failed"
    _rewrite_quality_source(
        tmp_path,
        report,
        evidence,
        evidence_path,
        source,
        source_path,
    )

    assert "ASSURANCE-028" in _codes(_audit(tmp_path))


def test_assurance_rejects_raw_quality_gate_producer_mismatch(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    evidence, evidence_path = _quality_gate_evidence(tmp_path, report)
    first_result = evidence["gates"][0]
    assert isinstance(first_result, dict)
    source, source_path = _load_source(tmp_path, first_result)
    source["producer"] = "local-shell"
    _rewrite_quality_source(
        tmp_path,
        report,
        evidence,
        evidence_path,
        source,
        source_path,
    )

    assert "ASSURANCE-028" in _codes(_audit(tmp_path))
