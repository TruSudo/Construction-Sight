import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from constructionsight.cli import app
from constructionsight.intelligence.artifact_identity import (
    IdentityArtifactType,
    ResolutionTargetKind,
    canonical_artifact_observation_id,
    canonical_identity_fingerprint_id,
    canonical_resolution_candidate_id,
    normalize_artifact_value,
)

runner = CliRunner()


def _observation(
    observation_id: str,
    artifact_type: str,
    value: str,
    *,
    source_family: str = "synthetic_source",
    evidence_record_id: str | None = None,
) -> dict[str, Any]:
    typed_artifact = IdentityArtifactType(artifact_type)
    normalized_value = normalize_artifact_value(typed_artifact, value)
    canonical_id = canonical_artifact_observation_id(
        artifact_type=typed_artifact,
        normalized_value=normalized_value,
        source_name="Synthetic Public Source",
        source_family=source_family,
        source_record_id=observation_id,
        jurisdiction=None,
        observed_field=None,
        evidence_record_id=evidence_record_id,
    )
    return {
        "observation_id": canonical_id,
        "artifact_type": artifact_type,
        "raw_value": value,
        "normalized_value": normalized_value,
        "source_name": "Synthetic Public Source",
        "source_family": source_family,
        "source_record_id": observation_id,
        "evidence_record_id": evidence_record_id,
        "confidence_score": 90,
    }


def _fingerprint(target_identity_id: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    observation_ids = [str(item["observation_id"]) for item in observations]
    return {
        "fingerprint_id": canonical_identity_fingerprint_id(
            target_identity_id=target_identity_id,
            target_kind=ResolutionTargetKind.PROJECT,
            observation_ids=observation_ids,
            evidence_record_ids=[],
        ),
        "target_identity_id": target_identity_id,
        "target_kind": "project",
        "artifact_observations": observations,
    }


def _write_preview_input(path: Path) -> None:
    payload = {
        "candidate_id": canonical_resolution_candidate_id(
            "project-left",
            "project-right",
            target_kind=ResolutionTargetKind.PROJECT,
        ),
        "left": _fingerprint(
            "project-left",
            [
                _observation(
                    "left-apn",
                    "apn",
                    "0292-123-45",
                    source_family="ceqanet",
                    evidence_record_id="ev-left-apn",
                ),
                _observation(
                    "left-address",
                    "exact_site_address",
                    "123 main st fontana ca",
                    source_family="agenda_packet",
                    evidence_record_id="ev-left-address",
                ),
            ],
        ),
        "right": _fingerprint(
            "project-right",
            [
                _observation(
                    "right-apn",
                    "apn",
                    "0292-123-45",
                    source_family="permit_portal",
                    evidence_record_id="ev-right-apn",
                ),
                _observation(
                    "right-address",
                    "exact_site_address",
                    "123 main st fontana ca",
                    source_family="permit_portal",
                    evidence_record_id="ev-right-address",
                ),
            ],
        ),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_cli_previews_artifact_resolution_as_json(tmp_path) -> None:
    input_path = tmp_path / "artifact_resolution_input.json"
    _write_preview_input(input_path)

    result = runner.invoke(
        app,
        [
            "preview-artifact-resolution",
            "--input",
            str(input_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["candidate_id"] == canonical_resolution_candidate_id(
        "project-left",
        "project-right",
        target_kind=ResolutionTargetKind.PROJECT,
    )
    assert payload["left_identity_id"] == "project-left"
    assert payload["right_identity_id"] == "project-right"
    assert payload["resolution_score"] == 85
    assert payload["recommended_decision"] == "needs_review"
    assert {match["artifact_type"] for match in payload["supporting_matches"]} == {
        "apn",
        "exact_site_address",
    }
    assert payload["conflicts"] == []


def test_cli_writes_artifact_resolution_json_file(tmp_path) -> None:
    input_path = tmp_path / "artifact_resolution_input.json"
    output_path = tmp_path / "artifact_resolution_output.json"
    _write_preview_input(input_path)

    result = runner.invoke(
        app,
        [
            "preview-artifact-resolution",
            "--input",
            str(input_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert f"Wrote artifact resolution JSON to {output_path}." in result.output
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == canonical_resolution_candidate_id(
        "project-left",
        "project-right",
        target_kind=ResolutionTargetKind.PROJECT,
    )
    assert payload["recommended_decision"] == "needs_review"


def test_cli_rejects_artifact_resolution_output_without_json(tmp_path) -> None:
    input_path = tmp_path / "artifact_resolution_input.json"
    output_path = tmp_path / "artifact_resolution_output.json"
    _write_preview_input(input_path)

    result = runner.invoke(
        app,
        [
            "preview-artifact-resolution",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
    assert not output_path.exists()


def test_cli_rejects_invalid_artifact_resolution_input(tmp_path) -> None:
    input_path = tmp_path / "artifact_resolution_input.json"
    input_path.write_text(json.dumps({"left": {}}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "preview-artifact-resolution",
            "--input",
            str(input_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "requires a right fingerprint" in result.output
