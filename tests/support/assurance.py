from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from constructionsight.defect_closure_certification import (
    reviewed_active_defects_digest,
)
from constructionsight.github_actions_certification import quality_gate_binding
from constructionsight.owner_acceptance_certification import expected_review_method

QUALITY_GATES = (
    "adapter-audit",
    "architecture-certification",
    "capability-certification",
    "compileall-py311",
    "compileall-py312",
    "dependency-integrity-py311",
    "dependency-integrity-py312",
    "diff-hygiene",
    "exact-checkout-py311",
    "exact-checkout-py312",
    "governance-contract-certification",
    "lock-verification-py311",
    "lock-verification-py312",
    "mypy-strict",
    "pytest-py311",
    "pytest-py312",
    "ruff",
    "sbom-py311",
    "sbom-py312",
    "security-mutation",
    "semantic-authorization-certification",
    "source-coverage-audit",
    "vulnerability-audit-py311",
    "vulnerability-audit-py312",
)


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(root: Path, relative: str, payload: object) -> str:
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def active_ledger(defects: list[dict[str, str]]) -> str:
    lines = [
        'schema_version = "constructionsight.active-defects/v1"',
        "certification_requires_zero = true",
    ]
    if not defects:
        lines.append("defects = []")
    for defect in defects:
        lines.extend(
            [
                "",
                "[[defects]]",
                *(f"{field} = {json.dumps(value)}" for field, value in defect.items()),
            ]
        )
    return "\n".join(lines) + "\n"


def resolved_ledger(defects: list[dict[str, object]]) -> str:
    lines = ['schema_version = "constructionsight.resolved-defects/v1"']
    if not defects:
        lines.append("defects = []")
    for defect in defects:
        lines.extend(["", "[[defects]]"])
        for field, value in defect.items():
            lines.append(f"{field} = {json.dumps(value)}")
    return "\n".join(lines) + "\n"


def initialize_repository(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "ConstructionSight Assurance Test")
    git(root, "config", "user.email", "assurance-test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    contract_source = Path(__file__).parents[2] / "governance/assurance_contract.toml"
    write(
        root,
        "governance/assurance_contract.toml",
        contract_source.read_text(encoding="utf-8"),
    )
    write(root, "governance/active_defects.toml", active_ledger([]))
    write(root, "governance/resolved_defects.toml", resolved_ledger([]))
    write(root, "src/constructionsight/reviewed.py", "VALUE = 'base'\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")


def _raw_source(
    root: Path,
    *,
    reviewed_commit: str,
    kind: str,
    context_id: str,
    producer: str,
    payload: object,
) -> tuple[str, str]:
    artifact_path = f"governance/reviews/evidence/raw/{context_id}.json"
    digest = write_json(
        root,
        artifact_path,
        {
            "schema_version": "constructionsight.assurance-source-artifact/v1",
            "reviewed_commit": reviewed_commit,
            "kind": kind,
            "context_id": context_id,
            "producer": producer,
            "payload": payload,
        },
    )
    return artifact_path, digest


def _pass(
    root: Path,
    *,
    reviewed_commit: str,
    pass_id: str,
    kind: str,
    reviewer: str,
    provider: str,
    model: str,
    candidate_count: int,
) -> dict[str, object]:
    source_path, source_digest = _raw_source(
        root,
        reviewed_commit=reviewed_commit,
        kind=kind,
        context_id=pass_id,
        producer="codex-security",
        payload={
            "reviewer": reviewer,
            "provider": provider,
            "model": model,
            "status": "passed",
            "fresh_context": True,
            "completed_reviews": 1,
            "candidate_count": candidate_count,
            "coverage_complete": True,
            "coverage_gap_count": 0,
            "unresolved_candidate_count": 0,
            "deferred_candidate_count": 0,
            "result": "test raw analytical evidence",
        },
    )
    artifact_path = f"governance/reviews/evidence/{pass_id}.json"
    digest = write_json(
        root,
        artifact_path,
        {
            "schema_version": "constructionsight.assurance-pass-evidence/v2",
            "pass_id": pass_id,
            "kind": kind,
            "reviewed_commit": reviewed_commit,
            "status": "passed",
            "fresh_context": True,
            "completed_reviews": 1,
            "candidate_count": candidate_count,
            "coverage_complete": True,
            "coverage_gap_count": 0,
            "unresolved_candidate_count": 0,
            "deferred_candidate_count": 0,
            "tool": "codex-security",
            "source_artifact_path": source_path,
            "source_artifact_sha256": source_digest,
        },
    )
    return {
        "pass_id": pass_id,
        "kind": kind,
        "reviewer": reviewer,
        "provider": provider,
        "model": model,
        "fresh_context": True,
        "completed_reviews": 1,
        "status": "passed",
        "artifact_path": artifact_path,
        "artifact_sha256": digest,
        "candidate_count": candidate_count,
        "coverage_complete": True,
        "coverage_gap_count": 0,
        "unresolved_candidate_count": 0,
        "deferred_candidate_count": 0,
    }


def _quality_job_id(job_name: str) -> int:
    return {
        "Python 3.11 quality gate": 11001,
        "Python 3.12 quality gate": 11002,
        "Python 3.11 isolated vulnerability audit": 11003,
        "Python 3.12 isolated vulnerability audit": 11004,
    }[job_name]


def write_assurance(
    root: Path,
    *,
    reviewed_commit: str,
    reviewed_tree_digest: str,
    mode: str = "native_maximum",
    candidates: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    candidate_entries = candidates or []
    pass_sources: dict[str, int] = {}
    for candidate in candidate_entries:
        for pass_id in candidate["source_pass_ids"]:
            pass_sources[str(pass_id)] = pass_sources.get(str(pass_id), 0) + 1

    owner = "github:TestOwner@pr-117#5151"
    reviewer = owner
    passes = [
        _pass(
            root,
            reviewed_commit=reviewed_commit,
            pass_id="native-deep-1",
            kind="deep_repository",
            reviewer="codex-security:deep-1",
            provider="openai",
            model="codex-security",
            candidate_count=pass_sources.get("native-deep-1", 0),
        ),
        _pass(
            root,
            reviewed_commit=reviewed_commit,
            pass_id="native-deep-2",
            kind="deep_repository",
            reviewer="codex-security:deep-2",
            provider="openai",
            model="codex-security",
            candidate_count=pass_sources.get("native-deep-2", 0),
        ),
        _pass(
            root,
            reviewed_commit=reviewed_commit,
            pass_id="native-deep-3",
            kind="deep_repository",
            reviewer="codex-security:deep-3",
            provider="openai",
            model="codex-security",
            candidate_count=pass_sources.get("native-deep-3", 0),
        ),
        _pass(
            root,
            reviewed_commit=reviewed_commit,
            pass_id="native-diff",
            kind="exact_diff",
            reviewer="codex-security:diff",
            provider="openai",
            model="codex-security",
            candidate_count=pass_sources.get("native-diff", 0),
        ),
        _pass(
            root,
            reviewed_commit=reviewed_commit,
            pass_id="native-invariant",
            kind="adversarial_invariant",
            reviewer="codex-security:invariant",
            provider="openai",
            model="codex-security",
            candidate_count=pass_sources.get("native-invariant", 0),
        ),
    ]
    pull_request_number: int | None = None
    independence_claim = "native_context_isolated_not_independent"
    limitation = "no_independent_external_model_or_human_review"
    if mode == "independent_external_model":
        reviewer = "model:anthropic:claude"
        passes.append(
            _pass(
                root,
                reviewed_commit=reviewed_commit,
                pass_id="external-model",
                kind="external_model",
                reviewer=reviewer,
                provider="anthropic",
                model="claude",
                candidate_count=pass_sources.get("external-model", 0),
            )
        )
        independence_claim = "independent_external_model_not_human"
        limitation = "external_model_review_is_not_human_approval"
    elif mode == "independent_human":
        reviewer = "github:IndependentReviewer#4242"
        pull_request_number = 117
        passes.append(
            _pass(
                root,
                reviewed_commit=reviewed_commit,
                pass_id="human-review",
                kind="independent_human",
                reviewer=reviewer,
                provider="github",
                model="not-applicable",
                candidate_count=pass_sources.get("human-review", 0),
            )
        )
        independence_claim = "independent_human"
        limitation = "human_review_does_not_replace_native_assurance"

    pass_ids = sorted(str(value["pass_id"]) for value in passes)
    union_path = "governance/reviews/evidence/candidate-union.json"
    union_digest = write_json(
        root,
        union_path,
        {
            "schema_version": "constructionsight.assurance-candidate-union/v1",
            "reviewed_commit": reviewed_commit,
            "blind_union": True,
            "source_pass_ids": pass_ids,
            "coverage_complete": True,
            "coverage_gaps": [],
            "candidates": candidate_entries,
        },
    )

    gate_results: list[dict[str, object]] = []
    for gate_id in QUALITY_GATES:
        binding = quality_gate_binding(gate_id)
        if binding is None:
            raise AssertionError(f"missing test quality-gate binding: {gate_id}")
        job_name, step_name = binding
        source_path, source_digest = _raw_source(
            root,
            reviewed_commit=reviewed_commit,
            kind="quality_gate",
            context_id=gate_id,
            producer="github-actions",
            payload={
                "gate_id": gate_id,
                "status": "passed",
                "result": "test retained quality-gate source evidence",
                "run_id": 9001,
                "job_id": _quality_job_id(job_name),
                "job_name": job_name,
                "step_name": step_name,
                "head_sha": reviewed_commit,
                "workflow_name": "CI",
                "event": "pull_request",
                "pull_request_number": 117,
            },
        )
        gate_results.append(
            {
                "gate_id": gate_id,
                "status": "passed",
                "source_artifact_path": source_path,
                "source_artifact_sha256": source_digest,
            }
        )

    gate_path = "governance/reviews/evidence/quality-gates.json"
    gate_digest = write_json(
        root,
        gate_path,
        {
            "schema_version": "constructionsight.assurance-quality-gates/v2",
            "reviewed_commit": reviewed_commit,
            "gates": gate_results,
        },
    )
    report: dict[str, Any] = {
        "schema_version": "constructionsight.assurance-review/v1",
        "status": "passed",
        "assurance_mode": mode,
        "independence_claim": independence_claim,
        "owner": owner,
        "owner_acceptance": True,
        "reviewer": reviewer,
        "review_method": "pending evidence digest",
        "reviewed_commit": reviewed_commit,
        "reviewed_active_defects_digest": reviewed_active_defects_digest(
            root,
            reviewed_commit,
        ),
        "reviewed_tree_digest": reviewed_tree_digest,
        "pull_request_number": pull_request_number,
        "surviving_security_mutants": 0,
        "passes": passes,
        "candidate_union": {
            "artifact_path": union_path,
            "artifact_sha256": union_digest,
        },
        "quality_gates": [
            {
                "gate_id": gate_id,
                "status": "passed",
                "artifact_path": gate_path,
                "artifact_sha256": gate_digest,
            }
            for gate_id in QUALITY_GATES
        ],
        "limitations": [limitation],
    }
    report["review_method"] = expected_review_method(report)
    write_json(root, "governance/reviews/assurance_review.json", report)
    return report


def rewrite_assurance(root: Path, report: dict[str, Any]) -> None:
    write_json(root, "governance/reviews/assurance_review.json", report)


def rewrite_candidate_union(
    root: Path,
    report: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    reference = report["candidate_union"]
    assert isinstance(reference, dict)
    path = str(reference["artifact_path"])
    reference["artifact_sha256"] = write_json(root, path, payload)
    report["review_method"] = expected_review_method(report)
    rewrite_assurance(root, report)
