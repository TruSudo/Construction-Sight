import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from constructionsight.cli import app  # type: ignore[import-untyped]

runner = CliRunner()
EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "artifact_resolution"


def _run_preview(example_name: str) -> Any:
    return runner.invoke(
        app,
        [
            "preview-artifact-resolution",
            "--input",
            str(EXAMPLE_DIR / example_name),
            "--json-output",
        ],
    )


def test_commerce_center_match_example_is_valid_preview_input() -> None:
    result = _run_preview("commerce_center_match.json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["candidate_id"] == "fixture-commerce-center-match"
    assert payload["resolution_score"] == 80
    assert payload["recommended_decision"] == "needs_review"
    assert payload["has_near_unique_support"] is True
    assert payload["conflicts"] == []
    assert {match["artifact_type"] for match in payload["supporting_matches"]} == {
        "apn",
        "exact_site_address",
    }


def test_conflicting_ceqa_sch_example_is_valid_preview_input() -> None:
    result = _run_preview("conflicting_ceqa_sch.json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["candidate_id"] == "fixture-conflicting-ceqa-sch"
    assert payload["recommended_decision"] == "reject_match"
    assert payload["has_near_unique_conflict"] is True
    assert {match["artifact_type"] for match in payload["supporting_matches"]} == {
        "project_title"
    }
    assert {conflict["artifact_type"] for conflict in payload["conflicts"]} == {
        "ceqa_sch_number"
    }


def test_artifact_resolution_examples_are_valid_json_objects() -> None:
    for example_path in sorted(EXAMPLE_DIR.glob("*.json")):
        payload = json.loads(example_path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert "left" in payload
        assert "right" in payload
