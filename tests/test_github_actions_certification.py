from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constructionsight.authority_certification import _reviewed_tree_digest
from constructionsight.github_actions_certification import (
    bound_run_ids,
    quality_source_payloads,
    verify_github_actions_bindings,
)
from tests.support.assurance import git, initialize_repository, write_assurance, write_json


def _valid_assurance(root: Path) -> dict[str, Any]:
    initialize_repository(root)
    reviewed_commit = git(root, "rev-parse", "HEAD")
    return write_assurance(
        root,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=_reviewed_tree_digest(root),
    )


def _api_sources(
    root: Path,
    report: dict[str, Any],
    source_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads = quality_source_payloads(root, report)
    run_id = int(payloads[0]["run_id"])
    reviewed_commit = str(report["reviewed_commit"])
    run = {
        "id": run_id,
        "name": "CI",
        "head_sha": reviewed_commit,
        "event": "pull_request",
        "repository": {"full_name": "TruSudo/Construction-Sight"},
        "pull_requests": [{"number": 117}],
    }
    jobs_by_id: dict[int, dict[str, Any]] = {}
    for payload in payloads:
        job_id = int(payload["job_id"])
        job_name = str(payload["job_name"])
        step_name = str(payload["step_name"])
        job = jobs_by_id.setdefault(
            job_id,
            {
                "id": job_id,
                "run_id": run_id,
                "name": job_name,
                "status": "completed",
                "conclusion": "failure" if "quality gate" in job_name else "success",
                "steps": [],
            },
        )
        steps = job["steps"]
        assert isinstance(steps, list)
        if not any(
            isinstance(step, dict) and step.get("name") == step_name for step in steps
        ):
            steps.append(
                {
                    "name": step_name,
                    "status": "completed",
                    "conclusion": "success",
                }
            )
    jobs = {"total_count": len(jobs_by_id), "jobs": list(jobs_by_id.values())}
    write_json(source_dir, f"run-{run_id}.json", run)
    write_json(source_dir, f"jobs-{run_id}.json", jobs)
    return run, jobs


def test_github_actions_provenance_accepts_exact_successful_steps(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    source_dir = tmp_path / "api"
    _api_sources(tmp_path, report, source_dir)

    findings = verify_github_actions_bindings(
        tmp_path,
        report,
        source_dir=source_dir,
        repository="TruSudo/Construction-Sight",
    )

    assert findings == ()
    assert bound_run_ids(tmp_path, report) == (9001,)


def test_github_actions_provenance_rejects_failed_bound_step(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    source_dir = tmp_path / "api"
    _run, jobs = _api_sources(tmp_path, report, source_dir)
    raw_jobs = jobs["jobs"]
    assert isinstance(raw_jobs, list)
    quality_job = next(
        job
        for job in raw_jobs
        if isinstance(job, dict) and job.get("name") == "Python 3.12 quality gate"
    )
    steps = quality_job["steps"]
    assert isinstance(steps, list)
    ruff = next(
        step for step in steps if isinstance(step, dict) and step.get("name") == "Ruff"
    )
    ruff["conclusion"] = "failure"
    write_json(source_dir, "jobs-9001.json", jobs)

    findings = verify_github_actions_bindings(
        tmp_path,
        report,
        source_dir=source_dir,
        repository="TruSudo/Construction-Sight",
    )

    assert any("authoritative GitHub step did not succeed" in value for value in findings)


def test_github_actions_provenance_rejects_wrong_run_commit(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    source_dir = tmp_path / "api"
    run, _jobs = _api_sources(tmp_path, report, source_dir)
    run["head_sha"] = "1" * 40
    write_json(source_dir, "run-9001.json", run)

    findings = verify_github_actions_bindings(
        tmp_path,
        report,
        source_dir=source_dir,
        repository="TruSudo/Construction-Sight",
    )

    assert any("workflow run does not match exact provenance" in value for value in findings)


def test_github_actions_provenance_rejects_wrong_repository(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    source_dir = tmp_path / "api"
    run, _jobs = _api_sources(tmp_path, report, source_dir)
    run["repository"] = {"full_name": "attacker/fork"}
    write_json(source_dir, "run-9001.json", run)

    findings = verify_github_actions_bindings(
        tmp_path,
        report,
        source_dir=source_dir,
        repository="TruSudo/Construction-Sight",
    )

    assert any("workflow run does not match exact provenance" in value for value in findings)


def test_github_actions_provenance_rejects_wrong_pull_request(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    source_dir = tmp_path / "api"
    run, _jobs = _api_sources(tmp_path, report, source_dir)
    run["pull_requests"] = [{"number": 999}]
    write_json(source_dir, "run-9001.json", run)

    findings = verify_github_actions_bindings(
        tmp_path,
        report,
        source_dir=source_dir,
        repository="TruSudo/Construction-Sight",
    )

    assert any("not bound to the claimed pull request" in value for value in findings)


def test_github_actions_provenance_rejects_noncanonical_local_binding(tmp_path: Path) -> None:
    report = _valid_assurance(tmp_path)
    first_gate = report["quality_gates"][0]
    assert isinstance(first_gate, dict)
    evidence_path = str(first_gate["artifact_path"])
    evidence = json.loads((tmp_path / evidence_path).read_text(encoding="utf-8"))
    assert isinstance(evidence, dict)
    first_result = evidence["gates"][0]
    assert isinstance(first_result, dict)
    source_path = str(first_result["source_artifact_path"])
    source = json.loads((tmp_path / source_path).read_text(encoding="utf-8"))
    assert isinstance(source, dict)
    payload = source["payload"]
    assert isinstance(payload, dict)
    payload["step_name"] = "Unrelated successful step"
    write_json(tmp_path, source_path, source)
    source_dir = tmp_path / "api"
    _api_sources(tmp_path, report, source_dir)

    findings = verify_github_actions_bindings(
        tmp_path,
        report,
        source_dir=source_dir,
        repository="TruSudo/Construction-Sight",
    )

    assert any("noncanonical job or step binding" in value for value in findings)
