from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
EVIDENCE_PATH = ROOT / "docs/assurance/evidence/CS-SR-011-ci-1551.json"


def _cs_sr_011() -> dict[str, object]:
    payload = tomllib.loads(
        (ROOT / "governance/resolved_defects.toml").read_text(encoding="utf-8")
    )
    return next(
        defect for defect in payload["defects"] if defect["id"] == "CS-SR-011"
    )


def test_cs_sr_011_retains_exact_failed_ci_result() -> None:
    # Regression: CS-SR-092
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert evidence["run_id"] == 36193106181
    assert evidence["run_number"] == 1551
    assert evidence["head_sha"] == "381a64ecc4e35601453091ac880af0d6328d85a9"
    assert evidence["conclusion"] == "failure"
    assert {job["conclusion"] for job in evidence["quality_jobs"]} == {"failure"}
    assert {
        finding["code"]
        for finding in evidence["repository_certification"]["findings"]
    } == {"ASSURANCE-001", "DEFECT-ACTIVE-001"}


def test_cs_sr_011_summary_cannot_claim_repository_certification_passed() -> None:
    # Regression: CS-SR-092
    closure = _cs_sr_011()
    summary = str(closure["resolution_summary"]).lower()

    assert "workflow concluded failure" in summary
    assert "repository certification failed" in summary
    assert "does not claim repository/semantic certification" in summary
    assert "all passed" not in summary
    assert "all quality gates passed" not in summary
    assert "tests/test_cs_sr_011_closure_evidence.py" in closure["regression_tests"]
    assert (
        "docs/assurance/evidence/CS-SR-011-ci-1551.json"
        in closure["evidence_paths"]
    )


def test_cs_sr_011_narrative_distinguishes_subgates_from_aggregate_result() -> None:
    # Regression: CS-SR-092
    narrative = (
        ROOT / "docs/assurance/defect_closures/CS-SR-011.md"
    ).read_text(encoding="utf-8")

    assert "concluded failure" in narrative
    assert "2,134 / 2,134 tests passed" in narrative
    assert "164 / 164 focused mutants killed" in narrative
    assert "did **not** certify" in narrative
    assert "repository" in narrative
