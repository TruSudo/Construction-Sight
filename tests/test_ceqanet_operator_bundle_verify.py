import hashlib
import json
from pathlib import Path

import pytest

from constructionsight.ceqanet_operator_bundle_verify import verify_ceqanet_operator_bundle


def _write_bundle_manifest(bundle_dir: Path) -> None:
    (bundle_dir / "operator-report.md").write_text("# CEQAnet Operator Report\n", encoding="utf-8")
    (bundle_dir / "write-plan.json").write_text("{\"ok\": true}\n", encoding="utf-8")
    report_bytes = (bundle_dir / "operator-report.md").read_bytes()
    plan_bytes = (bundle_dir / "write-plan.json").read_bytes()
    payload = {
        "metadata": {
            "schema_version": "ceqanet_operator_bundle.v1",
            "artifact_count": 2,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "artifacts": [
            {
                "filename": "operator-report.md",
                "artifact_type": "operator_report_markdown",
                "byte_count": len(report_bytes),
                "sha256": hashlib.sha256(report_bytes).hexdigest(),
            },
            {
                "filename": "write-plan.json",
                "artifact_type": "write_plan_json",
                "byte_count": len(plan_bytes),
                "sha256": hashlib.sha256(plan_bytes).hexdigest(),
            },
        ],
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_verify_ceqanet_operator_bundle_passes_for_matching_manifest(tmp_path: Path) -> None:
    _write_bundle_manifest(tmp_path)

    payload = verify_ceqanet_operator_bundle(bundle_dir=tmp_path).to_dict()

    assert payload["metadata"]["schema_version"] == "ceqanet_operator_bundle_verification.v1"
    assert payload["metadata"]["artifact_count"] == 2
    assert payload["metadata"]["verified_count"] == 2
    assert payload["metadata"]["missing_count"] == 0
    assert payload["metadata"]["mismatch_count"] == 0
    assert payload["metadata"]["malformed_artifact_count"] == 0
    assert payload["metadata"]["passed"] is True
    assert payload["metadata"]["network_executed"] is False
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False
    assert payload["artifacts"][0]["status"] == "verified"


def test_verify_ceqanet_operator_bundle_tracks_missing_and_mismatch(tmp_path: Path) -> None:
    _write_bundle_manifest(tmp_path)
    (tmp_path / "operator-report.md").write_text("changed\n", encoding="utf-8")
    (tmp_path / "write-plan.json").unlink()

    payload = verify_ceqanet_operator_bundle(bundle_dir=tmp_path).to_dict()

    assert payload["metadata"]["passed"] is False
    assert payload["metadata"]["verified_count"] == 0
    assert payload["metadata"]["missing_count"] == 1
    assert payload["metadata"]["mismatch_count"] == 1
    statuses = {artifact["filename"]: artifact["status"] for artifact in payload["artifacts"]}
    assert statuses == {
        "operator-report.md": "mismatch",
        "write-plan.json": "missing",
    }


def test_verify_ceqanet_operator_bundle_tracks_malformed_artifacts(tmp_path: Path) -> None:
    manifest = {
        "metadata": {"schema_version": "ceqanet_operator_bundle.v1"},
        "artifacts": ["bad", {"filename": "x"}],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    payload = verify_ceqanet_operator_bundle(bundle_dir=tmp_path).to_dict()

    assert payload["metadata"]["passed"] is False
    assert payload["metadata"]["artifact_count"] == 0
    assert payload["metadata"]["malformed_artifact_count"] == 2
    assert payload["malformed_artifacts"][0]["reason"] == "artifact is not an object"


def test_verify_ceqanet_operator_bundle_rejects_wrong_schema(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        json.dumps({"metadata": {"schema_version": "wrong.v1"}, "artifacts": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ceqanet_operator_bundle.v1"):
        verify_ceqanet_operator_bundle(bundle_dir=tmp_path)


def test_verify_ceqanet_operator_bundle_rejects_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Bundle manifest not found"):
        verify_ceqanet_operator_bundle(bundle_dir=tmp_path)


def test_verify_bundle_rejects_manifest_before_full_materialization(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="manifest exceeds inspection byte limit"):
        verify_ceqanet_operator_bundle(bundle_dir=tmp_path)


def test_verify_bundle_rejects_oversized_artifact_before_full_read(tmp_path: Path) -> None:
    _write_bundle_manifest(tmp_path)
    artifact_path = tmp_path / "operator-report.md"
    with artifact_path.open("wb") as artifact_file:
        artifact_file.truncate(16 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="artifact exceeds inspection byte limit"):
        verify_ceqanet_operator_bundle(bundle_dir=tmp_path)


def test_verify_bundle_rejects_excessive_manifest_entry_count(tmp_path: Path) -> None:
    manifest = {
        "metadata": {"schema_version": "ceqanet_operator_bundle.v1"},
        "artifacts": ["bad"] * 129,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact entry limit"):
        verify_ceqanet_operator_bundle(bundle_dir=tmp_path)


def test_verify_bundle_rejects_parent_traversal_artifact(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-operator-artifact"
    outside.write_bytes(b"outside")
    manifest = {
        "metadata": {"schema_version": "ceqanet_operator_bundle.v1"},
        "artifacts": [
            {
                "filename": "../outside-operator-artifact",
                "artifact_type": "unsafe",
                "byte_count": 7,
                "sha256": hashlib.sha256(b"outside").hexdigest(),
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="safe basename"):
        verify_ceqanet_operator_bundle(bundle_dir=tmp_path)
