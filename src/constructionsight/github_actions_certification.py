"""Verify retained assurance quality gates against authoritative GitHub Actions API data."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

ASSURANCE_REVIEW_SCHEMA: Final = "constructionsight.assurance-review/v1"
ASSURANCE_SOURCE_PREFIX: Final = "governance/reviews/evidence/raw"
ASSURANCE_EVIDENCE_PREFIX: Final = "governance/reviews/evidence"
GITHUB_ACTIONS_SOURCE_PRODUCER: Final = "github-actions"
WORKFLOW_NAME: Final = "CI"
WORKFLOW_EVENT: Final = "pull_request"
QUALITY_GATE_SOURCE_FIELDS: Final = frozenset(
    {
        "gate_id",
        "status",
        "result",
        "run_id",
        "job_id",
        "job_name",
        "step_name",
        "head_sha",
        "workflow_name",
        "event",
        "pull_request_number",
    }
)
QUALITY_GATE_BINDINGS: Final = {
    "adapter-audit": ("Python 3.12 quality gate", "Adapter contract audit"),
    "architecture-certification": (
        "Python 3.12 quality gate",
        "Native assurance preflight certification",
    ),
    "capability-certification": (
        "Python 3.12 quality gate",
        "Native assurance preflight certification",
    ),
    "compileall-py311": ("Python 3.11 quality gate", "Compile source and tests"),
    "compileall-py312": ("Python 3.12 quality gate", "Compile source and tests"),
    "dependency-integrity-py311": ("Python 3.11 quality gate", "Dependency integrity"),
    "dependency-integrity-py312": ("Python 3.12 quality gate", "Dependency integrity"),
    "diff-hygiene": ("Python 3.12 quality gate", "Diff hygiene"),
    "exact-checkout-py311": ("Python 3.11 quality gate", "Verify exact checkout"),
    "exact-checkout-py312": ("Python 3.12 quality gate", "Verify exact checkout"),
    "governance-contract-certification": (
        "Python 3.12 quality gate",
        "Native assurance preflight certification",
    ),
    "lock-verification-py311": ("Python 3.11 quality gate", "Verify exact lock"),
    "lock-verification-py312": ("Python 3.12 quality gate", "Verify exact lock"),
    "mypy-strict": ("Python 3.12 quality gate", "Mypy"),
    "pytest-py311": ("Python 3.11 quality gate", "Pytest"),
    "pytest-py312": ("Python 3.12 quality gate", "Pytest"),
    "ruff": ("Python 3.12 quality gate", "Ruff"),
    "sbom-py311": ("Python 3.11 quality gate", "Generate deterministic SBOM"),
    "sbom-py312": ("Python 3.12 quality gate", "Generate deterministic SBOM"),
    "security-mutation": (
        "Python 3.12 quality gate",
        "Focused mutation certification",
    ),
    "semantic-authorization-certification": (
        "Python 3.12 quality gate",
        "Native assurance preflight certification",
    ),
    "source-coverage-audit": (
        "Python 3.12 quality gate",
        "Source adapter coverage audit",
    ),
    "vulnerability-audit-py311": (
        "Python 3.11 isolated vulnerability audit",
        "Vulnerability audit",
    ),
    "vulnerability-audit-py312": (
        "Python 3.12 isolated vulnerability audit",
        "Vulnerability audit",
    ),
}


def _positive_integer(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload at {path} must be an object")
    return payload


def _repository_json(root: Path, raw_path: object, *, prefix: str) -> dict[str, Any]:
    if not isinstance(raw_path, str):
        raise ValueError("assurance evidence path must be text")
    try:
        _canonical, path = resolve_repository_file(
            root,
            raw_path,
            required_prefix=prefix,
            required_suffix=".json",
        )
    except RepositoryPathError as exc:
        raise ValueError(f"unsafe or missing assurance evidence path: {raw_path}") from exc
    return _read_json_object(path)


def quality_gate_binding(gate_id: object) -> tuple[str, str] | None:
    """Return the canonical GitHub job/step binding for one required quality gate."""

    return QUALITY_GATE_BINDINGS.get(gate_id) if isinstance(gate_id, str) else None


def quality_source_payloads(
    root: Path,
    assurance_report: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Load each retained raw quality-gate payload exactly once."""

    raw_gates = assurance_report.get("quality_gates")
    if not isinstance(raw_gates, list) or not raw_gates:
        raise ValueError("assurance quality_gates must be a nonempty array")
    evidence_paths: set[str] = set()
    payloads: list[dict[str, Any]] = []
    seen_gate_ids: set[str] = set()
    for raw_gate in raw_gates:
        if not isinstance(raw_gate, dict):
            raise ValueError("assurance quality gate must be an object")
        evidence_path = raw_gate.get("artifact_path")
        if not isinstance(evidence_path, str):
            raise ValueError("quality gate artifact_path must be text")
        if evidence_path in evidence_paths:
            continue
        evidence_paths.add(evidence_path)
        evidence = _repository_json(root, evidence_path, prefix=ASSURANCE_EVIDENCE_PREFIX)
        results = evidence.get("gates")
        if not isinstance(results, list) or not results:
            raise ValueError("quality-gate evidence must contain gate results")
        for result in results:
            if not isinstance(result, dict):
                raise ValueError("quality-gate result must be an object")
            gate_id = result.get("gate_id")
            if not isinstance(gate_id, str) or gate_id in seen_gate_ids:
                raise ValueError("quality-gate source IDs must be unique text")
            seen_gate_ids.add(gate_id)
            source = _repository_json(
                root,
                result.get("source_artifact_path"),
                prefix=ASSURANCE_SOURCE_PREFIX,
            )
            if source.get("producer") != GITHUB_ACTIONS_SOURCE_PRODUCER:
                raise ValueError(f"quality gate {gate_id} source producer is not GitHub Actions")
            payload = source.get("payload")
            if not isinstance(payload, dict):
                raise ValueError(f"quality gate {gate_id} raw source payload must be an object")
            payloads.append(payload)
    return tuple(payloads)


def bound_run_ids(root: Path, assurance_report: Mapping[str, Any]) -> tuple[int, ...]:
    payloads = quality_source_payloads(root, assurance_report)
    run_ids = {payload.get("run_id") for payload in payloads}
    if not run_ids or not all(_positive_integer(value) for value in run_ids):
        raise ValueError("quality-gate source run IDs must be positive integers")
    if len(run_ids) != 1:
        raise ValueError("all quality-gate sources must bind one canonical GitHub Actions run")
    return tuple(sorted(int(value) for value in run_ids))


def _source_file(source_dir: Path, prefix: str, run_id: int) -> dict[str, Any]:
    return _read_json_object(source_dir / f"{prefix}-{run_id}.json")


def _pull_request_numbers(run: Mapping[str, Any]) -> set[int]:
    values = run.get("pull_requests")
    if not isinstance(values, list):
        return set()
    return {
        int(item["number"])
        for item in values
        if isinstance(item, dict) and _positive_integer(item.get("number"))
    }


def verify_github_actions_bindings(
    root: Path,
    assurance_report: Mapping[str, Any],
    *,
    source_dir: Path,
    repository: str,
) -> tuple[str, ...]:
    """Return deterministic findings for authoritative GitHub Actions provenance."""

    findings: list[str] = []
    if assurance_report.get("schema_version") != ASSURANCE_REVIEW_SCHEMA:
        findings.append("assurance report schema is unsupported")
    reviewed_commit = assurance_report.get("reviewed_commit")
    if not isinstance(reviewed_commit, str):
        findings.append("assurance reviewed_commit must be text")
        return tuple(findings)
    try:
        payloads = quality_source_payloads(root, assurance_report)
    except ValueError as exc:
        findings.append(str(exc))
        return tuple(findings)

    run_ids = {payload.get("run_id") for payload in payloads}
    pr_numbers = {payload.get("pull_request_number") for payload in payloads}
    if not run_ids or not all(_positive_integer(value) for value in run_ids):
        findings.append("quality-gate source run IDs must be positive integers")
        return tuple(findings)
    if len(run_ids) != 1:
        findings.append("all quality-gate sources must bind one canonical GitHub Actions run")
    if not pr_numbers or not all(_positive_integer(value) for value in pr_numbers):
        findings.append("quality-gate pull-request numbers must be positive integers")
    elif len(pr_numbers) != 1:
        findings.append("all quality-gate sources must bind one pull request")

    run_sources: dict[int, dict[str, Any]] = {}
    jobs_sources: dict[int, dict[str, Any]] = {}
    for raw_run_id in run_ids:
        if not _positive_integer(raw_run_id):
            continue
        run_id = int(raw_run_id)
        try:
            run_sources[run_id] = _source_file(source_dir, "run", run_id)
            jobs_sources[run_id] = _source_file(source_dir, "jobs", run_id)
        except ValueError as exc:
            findings.append(str(exc))

    for payload in payloads:
        gate_id = payload.get("gate_id")
        label = f"quality gate {gate_id}"
        missing = QUALITY_GATE_SOURCE_FIELDS - set(payload)
        unknown = set(payload) - QUALITY_GATE_SOURCE_FIELDS
        if missing or unknown:
            findings.append(
                f"{label} source fields disagree with schema; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        binding = quality_gate_binding(gate_id)
        if binding is None:
            findings.append(f"{label} has no canonical GitHub Actions binding")
            continue
        expected_job, expected_step = binding
        if payload.get("status") != "passed":
            findings.append(f"{label} raw status is not passed")
        if payload.get("head_sha") != reviewed_commit:
            findings.append(f"{label} does not bind reviewed_commit")
        if payload.get("workflow_name") != WORKFLOW_NAME:
            findings.append(f"{label} does not bind the canonical CI workflow")
        if payload.get("event") != WORKFLOW_EVENT:
            findings.append(f"{label} does not bind a pull_request workflow run")
        if payload.get("job_name") != expected_job or payload.get("step_name") != expected_step:
            findings.append(f"{label} uses a noncanonical job or step binding")
        run_id = payload.get("run_id")
        job_id = payload.get("job_id")
        pr_number = payload.get("pull_request_number")
        if not _positive_integer(run_id) or not _positive_integer(job_id):
            findings.append(f"{label} run_id and job_id must be positive integers")
            continue
        if not _positive_integer(pr_number):
            findings.append(f"{label} pull_request_number must be a positive integer")
            continue
        run = run_sources.get(int(run_id))
        jobs = jobs_sources.get(int(run_id))
        if run is None or jobs is None:
            continue
        repository_object = run.get("repository")
        run_repository = (
            repository_object.get("full_name")
            if isinstance(repository_object, Mapping)
            else None
        )
        if (
            run.get("id") != run_id
            or run.get("name") != WORKFLOW_NAME
            or run.get("head_sha") != reviewed_commit
            or run.get("event") != WORKFLOW_EVENT
            or run_repository != repository
        ):
            findings.append(f"{label} GitHub workflow run does not match exact provenance")
        if int(pr_number) not in _pull_request_numbers(run):
            findings.append(f"{label} GitHub workflow run is not bound to the claimed pull request")

        raw_jobs = jobs.get("jobs")
        if not isinstance(raw_jobs, list):
            findings.append(f"{label} GitHub jobs source is malformed")
            continue
        matching_jobs = [
            job
            for job in raw_jobs
            if isinstance(job, dict) and job.get("id") == job_id
        ]
        if len(matching_jobs) != 1:
            findings.append(f"{label} GitHub job ID is missing or duplicated")
            continue
        job = matching_jobs[0]
        if job.get("run_id") != run_id or job.get("name") != expected_job:
            findings.append(f"{label} GitHub job does not match the canonical binding")
        if job.get("status") != "completed":
            findings.append(f"{label} GitHub job was not completed")
        raw_steps = job.get("steps")
        if not isinstance(raw_steps, list):
            findings.append(f"{label} GitHub job steps are malformed")
            continue
        matching_steps = [
            step
            for step in raw_steps
            if isinstance(step, dict) and step.get("name") == expected_step
        ]
        if len(matching_steps) != 1:
            findings.append(f"{label} canonical GitHub step is missing or duplicated")
            continue
        step = matching_steps[0]
        if step.get("status") != "completed" or step.get("conclusion") != "success":
            findings.append(f"{label} authoritative GitHub step did not succeed")
    return tuple(findings)


def build_report(
    root: Path,
    assurance_report: Mapping[str, Any],
    *,
    source_dir: Path,
    repository: str,
) -> dict[str, Any]:
    findings = verify_github_actions_bindings(
        root,
        assurance_report,
        source_dir=source_dir,
        repository=repository,
    )
    return {
        "schema_version": "constructionsight.github-actions-certification/v1",
        "passed": not findings,
        "reviewed_commit": assurance_report.get("reviewed_commit"),
        "repository": repository,
        "findings": list(findings),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify ConstructionSight quality gates against GitHub Actions API evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_ids = subparsers.add_parser("run-ids")
    run_ids.add_argument("--root", type=Path, default=Path("."))
    run_ids.add_argument("--review-artifact", type=Path, required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", type=Path, default=Path("."))
    verify.add_argument("--review-artifact", type=Path, required=True)
    verify.add_argument("--source-dir", type=Path, required=True)
    verify.add_argument("--repository", required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        assurance = _read_json_object(args.review_artifact)
        if args.command == "run-ids":
            for run_id in bound_run_ids(args.root.resolve(), assurance):
                print(run_id)
            return 0
        report = build_report(
            args.root.resolve(),
            assurance,
            source_dir=args.source_dir,
            repository=args.repository,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except ValueError as exc:
        parser.exit(1, f"GitHub Actions certification failed: {exc}\n")
    if report["passed"]:
        print("GitHub Actions quality provenance certification passed.")
        return 0
    for finding in report["findings"]:
        print(f"- {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
