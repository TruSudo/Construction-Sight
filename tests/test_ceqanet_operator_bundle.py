import hashlib
import json
import os
from pathlib import Path

import pytest

import constructionsight.ceqanet_operator_bundle as bundle_writer
from constructionsight.ceqanet_operator_bundle import (
    _write_json_artifact,
    _write_text_artifact,
    build_ceqanet_operator_bundle,
)
from constructionsight.ceqanet_operator_bundle_verify import (
    verify_ceqanet_operator_bundle,
)


@pytest.mark.parametrize("attack", ("ancestor", "final", "swap"))
def test_bundle_publication_rejects_unsafe_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "bundle"
    if attack == "ancestor":
        output.symlink_to(outside, target_is_directory=True)
        output = output / "nested"
    else:
        output.mkdir()
    original = outside / "original.json"
    original.write_bytes(b"prior evidence")
    if attack == "final":
        (output / "operator-package.json").symlink_to(original)
    if attack == "swap":
        opened = os.open
        swapped = False

        def swap(path, flags, *args, **kwargs):
            nonlocal swapped
            if not swapped and flags & os.O_CREAT:
                swapped = True
                output.rename(tmp_path / "parked")
                output.symlink_to(outside, target_is_directory=True)
            return opened(path, flags, *args, **kwargs)

        monkeypatch.setattr(os, "open", swap)
    with pytest.raises((OSError, ValueError)):
        build_ceqanet_operator_bundle(_operator_package(), output_dir=output)
    assert original.read_bytes() == b"prior evidence"
    assert list(outside.iterdir()) == [original]


def _operator_package() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_operator_package.v1",
            "result_record_count": 1,
            "ceqa_record_count": 1,
            "site_count": 1,
            "entity_count": 0,
            "operation_count": 2,
            "warning_count": 0,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "persistence_preview": {
            "metadata": {"schema_version": "ceqanet_persistence_preview.v1"},
            "ceqa_records": [
                {
                    "ceqa_key": "ceqa:ceqanet:2017101033",
                    "title": "Countywide Plan",
                    "state_clearinghouse_number": "2017101033",
                    "county": "San Bernardino",
                    "lead_agency": "County Agency",
                }
            ],
        },
        "write_plan": {
            "metadata": {"schema_version": "ceqanet_write_plan.v1"},
            "operations": [
                {
                    "operation_id": "ceqa_records:ceqa:ceqanet:2017101033",
                    "action": "upsert_preview",
                    "target_collection": "ceqa_records",
                    "target_key": "ceqa:ceqanet:2017101033",
                },
                {
                    "operation_id": "sites:site:ceqanet:2017101033",
                    "action": "upsert_preview",
                    "target_collection": "sites",
                    "target_key": "site:ceqanet:2017101033",
                },
            ],
        },
        "warnings": [],
    }


def test_build_ceqanet_operator_bundle_writes_review_artifacts(tmp_path: Path) -> None:
    bundle = build_ceqanet_operator_bundle(_operator_package(), output_dir=tmp_path)
    manifest = bundle.to_dict()

    assert manifest["metadata"]["schema_version"] == "ceqanet_operator_bundle.v1"
    assert manifest["metadata"]["artifact_count"] == 6
    assert manifest["metadata"]["network_executed"] is False
    assert manifest["metadata"]["database_opened"] is False
    assert manifest["metadata"]["persistence_mutated"] is False

    assert (tmp_path / "operator-package.json").exists()
    assert (tmp_path / "persistence-preview.json").exists()
    assert (tmp_path / "write-plan.json").exists()
    assert (tmp_path / "operator-report.json").exists()
    assert (tmp_path / "operator-report.md").exists()
    assert (tmp_path / "manifest.json").exists()

    preview = json.loads((tmp_path / "persistence-preview.json").read_text(encoding="utf-8"))
    plan = json.loads((tmp_path / "write-plan.json").read_text(encoding="utf-8"))
    assert preview["metadata"]["schema_version"] == "ceqanet_persistence_preview.v1"
    assert plan["metadata"]["schema_version"] == "ceqanet_write_plan.v1"

    report_markdown = (tmp_path / "operator-report.md").read_text(encoding="utf-8")
    assert "# CEQAnet Operator Report" in report_markdown
    assert "Countywide Plan" in report_markdown

    manifest_json = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_json["metadata"]["artifact_count"] == 5
    assert len(manifest["artifacts"]) == 6
    artifact_names = {artifact["filename"] for artifact in manifest["artifacts"]}
    assert artifact_names == {
        "operator-package.json",
        "persistence-preview.json",
        "write-plan.json",
        "operator-report.json",
        "operator-report.md",
        "manifest.json",
    }
    assert all(artifact["sha256"] for artifact in manifest["artifacts"])


def test_build_ceqanet_operator_bundle_rejects_invalid_package(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ceqanet_operator_package.v1"):
        build_ceqanet_operator_bundle(
            {"metadata": {"schema_version": "wrong.v1"}},
            output_dir=tmp_path,
        )


def test_build_ceqanet_operator_bundle_rejects_missing_component(tmp_path: Path) -> None:
    package = _operator_package()
    del package["write_plan"]

    with pytest.raises(ValueError, match="write_plan object"):
        build_ceqanet_operator_bundle(package, output_dir=tmp_path)


def test_bundle_artifact_rejects_oversize_before_touching_existing_file(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "operator-report.md"
    existing.write_bytes(b"keep the previous artifact")
    with pytest.raises(ValueError, match="exceeds the byte limit"):
        _write_text_artifact(
            existing,
            "x" * (16 * 1024 * 1024 + 1),
            artifact_type="operator_report_markdown",
        )
    assert existing.read_bytes() == b"keep the previous artifact"
    assert list(tmp_path.glob(".ceqanet-bundle-*.tmp")) == []


def test_bundle_artifact_rejects_symlink_without_writing_external_file(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "external-artifact.txt"
    outside.write_bytes(b"external evidence must not be overwritten")
    output = tmp_path / "operator-report.md"
    output.symlink_to(outside)
    with pytest.raises(ValueError, match="regular file"):
        _write_text_artifact(
            output, "new verified artifact", artifact_type="operator_report_markdown"
        )
    assert output.is_symlink()
    assert outside.read_bytes() == b"external evidence must not be overwritten"


def test_bundle_artifact_failed_replace_preserves_old_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = tmp_path / "operator-report.md"
    existing.write_bytes(b"retain previous artifact")

    def fail_replace(_source: str, _target: str, **_kwargs: int) -> None:
        raise OSError("synthetic artifact publication failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="publication failure"):
        _write_text_artifact(
            existing, "new artifact", artifact_type="operator_report_markdown"
        )
    assert existing.read_bytes() == b"retain previous artifact"
    assert list(tmp_path.iterdir()) == [existing]


def test_bundle_output_rejects_symlinked_root(tmp_path: Path) -> None:
    real = tmp_path / "real-output"
    real.mkdir()
    linked = tmp_path / "linked-output"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinked directory"):
        build_ceqanet_operator_bundle(_operator_package(), output_dir=linked)
    assert list(real.iterdir()) == []


def test_bundle_json_matches_canonical_indented_encoding(tmp_path: Path) -> None:
    payload = {"z": ["Ω", {"b": 2, "a": 1}], "a": {"empty": None}}
    destination = tmp_path / "operator-package.json"
    result = _write_json_artifact(
        destination, payload, artifact_type="operator_package_json"
    )
    expected = (json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n").encode(
        "utf-8"
    )
    assert destination.read_bytes() == expected
    assert result.byte_count == len(expected)
    assert result.sha256 == hashlib.sha256(expected).hexdigest()


def test_bundle_json_streams_without_full_json_dumps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid_full_materialization(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("json.dumps must not materialize the artifact")

    monkeypatch.setattr(bundle_writer.json, "dumps", forbid_full_materialization)
    result = _write_json_artifact(
        tmp_path / "operator-package.json",
        {"a": ["value", "other"], "z": 1},
        artifact_type="operator_package_json",
    )
    assert result.byte_count > 0
    assert result.sha256


def test_bundle_oversized_json_preserves_previous_artifact(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "operator-package.json"
    destination.write_bytes(b"old output must remain")
    with pytest.raises(ValueError, match="exceeds the byte limit"):
        _write_json_artifact(
            destination,
            {"payload": "x" * (16 * 1024 * 1024 + 1)},
            artifact_type="operator_package_json",
        )
    assert destination.read_bytes() == b"old output must remain"
    assert list(tmp_path.glob(".ceqanet-bundle-*.tmp")) == []



@pytest.mark.parametrize("failure_point", ("operator-report.json", "manifest.json"))
def test_bundle_transaction_withholds_success_manifest_until_complete_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    output = tmp_path / "bundle"
    output.mkdir()
    build_ceqanet_operator_bundle(_operator_package(), output_dir=output)
    assert verify_ceqanet_operator_bundle(bundle_dir=output).passed

    package = _operator_package()
    package["warnings"] = ["replacement generation"]
    original_publish = bundle_writer._publish_staged_artifact

    def fail_late_publish(staged_path, output_path, *, artifact, parent):
        if artifact.filename == failure_point:
            raise OSError("injected coupled publication failure")
        return original_publish(
            staged_path,
            output_path,
            artifact=artifact,
            parent=parent,
        )

    with monkeypatch.context() as patch:
        patch.setattr(bundle_writer, "_publish_staged_artifact", fail_late_publish)
        with pytest.raises(OSError, match="coupled publication failure"):
            build_ceqanet_operator_bundle(package, output_dir=output)

    assert not (output / "manifest.json").exists()
    assert (output / bundle_writer._BUNDLE_PENDING_MANIFEST).is_file()

    recovered = build_ceqanet_operator_bundle(package, output_dir=output)
    assert recovered.artifact_count == 6
    assert verify_ceqanet_operator_bundle(bundle_dir=output).passed
    assert not (output / bundle_writer._BUNDLE_PENDING_MANIFEST).exists()


def test_bundle_transaction_recovers_cleanup_failure_after_success_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "bundle"
    output.mkdir()
    build_ceqanet_operator_bundle(_operator_package(), output_dir=output)

    package = _operator_package()
    package["warnings"] = ["new complete generation"]
    original_cleanup = bundle_writer._clear_pending_bundle_manifest

    def fail_cleanup(_parent: int) -> None:
        raise OSError("injected pending-marker cleanup failure")

    with monkeypatch.context() as patch:
        patch.setattr(bundle_writer, "_clear_pending_bundle_manifest", fail_cleanup)
        with pytest.raises(OSError, match="cleanup failure"):
            build_ceqanet_operator_bundle(package, output_dir=output)

    # The success manifest is published only after all payloads are durable, so
    # a cleanup interruption may leave a redundant recovery marker but never a
    # false success claim.
    assert (output / "manifest.json").is_file()
    assert (output / bundle_writer._BUNDLE_PENDING_MANIFEST).is_file()
    assert verify_ceqanet_operator_bundle(bundle_dir=output).passed

    monkeypatch.setattr(
        bundle_writer,
        "_clear_pending_bundle_manifest",
        original_cleanup,
    )
    build_ceqanet_operator_bundle(package, output_dir=output)
    assert verify_ceqanet_operator_bundle(bundle_dir=output).passed
    assert not (output / bundle_writer._BUNDLE_PENDING_MANIFEST).exists()
