"""Semantic provenance checks for retained Native Maximum Assurance source artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from constructionsight.governance_certification_core import (
    GovernanceFinding,
    _finding,
)
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

_CANONICAL_ASSURANCE_ARTIFACT: Final = "governance/reviews/assurance_review.json"
_ASSURANCE_EVIDENCE_PREFIX: Final = "governance/reviews/evidence"
_ASSURANCE_SOURCE_PREFIX: Final = "governance/reviews/evidence/raw"
_QUALITY_GATE_SOURCE_PRODUCER: Final = "github-actions"
_ANALYTICAL_SOURCE_FIELDS: Final = frozenset(
    {
        "reviewer",
        "provider",
        "model",
        "status",
        "fresh_context",
        "completed_reviews",
        "candidate_count",
        "coverage_complete",
        "coverage_gap_count",
        "unresolved_candidate_count",
        "deferred_candidate_count",
        "result",
    }
)
_QUALITY_GATE_SOURCE_FIELDS: Final = frozenset({"gate_id", "status", "result"})
_ANALYTICAL_BOUND_FIELDS: Final = tuple(
    field for field in sorted(_ANALYTICAL_SOURCE_FIELDS) if field != "result"
)
_QUALITY_GATE_BOUND_FIELDS: Final = ("gate_id", "status")


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _record(findings: list[GovernanceFinding], message: str) -> None:
    findings.append(
        _finding(
            "ASSURANCE-028",
            _CANONICAL_ASSURANCE_ARTIFACT,
            message,
        )
    )


def _read_json_reference(
    root: Path,
    raw_path: object,
    *,
    required_prefix: str,
) -> dict[str, Any] | None:
    if not isinstance(raw_path, str):
        return None
    try:
        _canonical, path = resolve_repository_file(
            root,
            raw_path,
            required_prefix=required_prefix,
            required_suffix=".json",
        )
    except RepositoryPathError:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _audit_source_payload(
    source: Mapping[str, Any],
    *,
    expected_producer: object,
    expected_fields: frozenset[str],
    expected_values: Mapping[str, object],
    label: str,
    findings: list[GovernanceFinding],
) -> None:
    if source.get("producer") != expected_producer:
        _record(
            findings,
            f"{label} raw source producer disagrees with normalized provenance",
        )

    source_payload = source.get("payload")
    if not isinstance(source_payload, dict):
        _record(findings, f"{label} raw source payload must be an object")
        return

    missing = expected_fields - set(source_payload)
    unknown = set(source_payload) - expected_fields
    if missing or unknown:
        _record(
            findings,
            f"{label} raw source payload fields disagree with semantic schema; "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}",
        )

    mismatched = [
        field
        for field, expected in expected_values.items()
        if source_payload.get(field) != expected
    ]
    if mismatched:
        _record(
            findings,
            f"{label} raw source payload disagrees with normalized claims: "
            f"{sorted(mismatched)}",
        )
    if not _nonblank(source_payload.get("result")):
        _record(findings, f"{label} raw source result must be nonblank retained evidence")


def _audit_analytical_sources(
    root: Path,
    report: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    raw_passes = report.get("passes")
    if not isinstance(raw_passes, list):
        return
    for raw_pass in raw_passes:
        if not isinstance(raw_pass, dict):
            continue
        pass_id = raw_pass.get("pass_id")
        evidence = _read_json_reference(
            root,
            raw_pass.get("artifact_path"),
            required_prefix=_ASSURANCE_EVIDENCE_PREFIX,
        )
        if evidence is None:
            continue
        source = _read_json_reference(
            root,
            evidence.get("source_artifact_path"),
            required_prefix=_ASSURANCE_SOURCE_PREFIX,
        )
        if source is None:
            continue
        expected_values = {
            field: raw_pass.get(field) for field in _ANALYTICAL_BOUND_FIELDS
        }
        _audit_source_payload(
            source,
            expected_producer=evidence.get("tool"),
            expected_fields=_ANALYTICAL_SOURCE_FIELDS,
            expected_values=expected_values,
            label=f"analytical pass {pass_id}",
            findings=findings,
        )


def _audit_quality_gate_sources(
    root: Path,
    report: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    raw_gates = report.get("quality_gates")
    if not isinstance(raw_gates, list):
        return
    seen_evidence: set[str] = set()
    for raw_gate in raw_gates:
        if not isinstance(raw_gate, dict):
            continue
        evidence_path = raw_gate.get("artifact_path")
        if not isinstance(evidence_path, str) or evidence_path in seen_evidence:
            continue
        seen_evidence.add(evidence_path)
        evidence = _read_json_reference(
            root,
            evidence_path,
            required_prefix=_ASSURANCE_EVIDENCE_PREFIX,
        )
        if evidence is None:
            continue
        raw_results = evidence.get("gates")
        if not isinstance(raw_results, list):
            continue
        for raw_result in raw_results:
            if not isinstance(raw_result, dict):
                continue
            gate_id = raw_result.get("gate_id")
            source = _read_json_reference(
                root,
                raw_result.get("source_artifact_path"),
                required_prefix=_ASSURANCE_SOURCE_PREFIX,
            )
            if source is None:
                continue
            expected_values = {
                field: raw_result.get(field) for field in _QUALITY_GATE_BOUND_FIELDS
            }
            _audit_source_payload(
                source,
                expected_producer=_QUALITY_GATE_SOURCE_PRODUCER,
                expected_fields=_QUALITY_GATE_SOURCE_FIELDS,
                expected_values=expected_values,
                label=f"quality gate {gate_id}",
                findings=findings,
            )


def audit_assurance_source_semantics(
    root: Path,
    findings: list[GovernanceFinding],
) -> None:
    """Reject raw assurance sources that contradict their normalized evidence."""

    report = _read_json_reference(
        root,
        _CANONICAL_ASSURANCE_ARTIFACT,
        required_prefix="governance/reviews",
    )
    if report is None:
        return
    _audit_analytical_sources(root, report, findings)
    _audit_quality_gate_sources(root, report, findings)
