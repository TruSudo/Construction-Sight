"""Adversarial integration checks for operator evidence entry points."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
import typer

from constructionsight import ceqanet_csv_cli, intake_service
from constructionsight.storage.runtime_artifacts import RuntimeArtifactError

# Exercise real entry points: rejection must precede parsing/model construction.
_JSON_LOADERS = (
    ("audit_package_cli", "_load_sources_from_json"),
    ("ceqanet_chain_cli", "_load_json_object"),
    ("ceqanet_csv_access_policy_cli", "_load_json"),
    ("ceqanet_csv_evidence_series_cli", "_load_json"),
    ("ceqanet_detail_enrichment_cli", "_load_json_object"),
    ("ceqanet_detail_parse_cli", "_load_json_object"),
    ("ceqanet_fixture_query_cli", "_read_fixture_rows"),
    ("ceqanet_maturity_proposal_cli", "_load_json"),
    ("ceqanet_operator_bundle_cli", "_load_json_object"),
    ("ceqanet_operator_export_cli", "_load_json_object"),
    ("ceqanet_operator_package_cli", "_load_json_object"),
    ("ceqanet_operator_report_cli", "_load_json_object"),
    ("ceqanet_persistence_execute_cli", "_load_json_object"),
    ("ceqanet_persistence_preview_cli", "_load_json_object"),
    ("ceqanet_recurring_run_cli", "_load_json"),
    ("ceqanet_result_parse_cli", "_load_json_object"),
    ("ceqanet_vocabulary_export_cli", "_load_json_object"),
    ("ceqanet_write_plan_cli", "_load_json_object"),
    ("cli", "_load_sources_from_json"),
    ("cli", "_read_json_object_file"),
    ("cli", "_read_artifact_resolution_preview_input"),
    ("opportunity_cli", "_load_intake_record"),
    ("parcel_row_preview", "load_row_preview_input"),
    ("parcel_schema_preview", "load_schema_preview_input"),
    ("site_resolution_cli", "_load_intake_record"),
    ("source_promotion_plan_cli", "_load_sources_from_json"),
    ("source_promotion_plan_cli", "_load_observations"),
    ("source_readiness_cli", "_load_sources_from_json"),
    ("source_registry_update_plan_cli", "_load_sources_from_json"),
    ("source_registry_update_plan_cli", "_load_observations"),
    ("source_registry_update_plan_cli", "_load_plan"),
    ("source_status_cli", "_load_sources_from_json"),
    ("source_verification_checklist_cli", "_load_sources_from_json"),
    ("source_verification_checklist_cli", "_load_observations"),
    ("ceqanet_csv_cli", "verify_live_csv_execution"),
)


def _unsafe_input(tmp_path: Path, attack: str) -> Path:
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "input.json"
    source.write_text("{}", encoding="utf-8")
    if attack == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        return alias / source.name
    if attack == "final":
        alias = tmp_path / "alias.json"
        alias.symlink_to(source)
        return alias
    with source.open("wb") as handle:
        handle.truncate(16 * 1024 * 1024 + 1)
    return source


@pytest.mark.parametrize(("module_name", "function_name"), _JSON_LOADERS)
@pytest.mark.parametrize("attack", ("ancestor", "final", "oversized"))
def test_json_loaders_reject_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    module_name: str, function_name: str, attack: str,
) -> None:
    module = importlib.import_module(f"constructionsight.{module_name}")
    loader = getattr(module, function_name)
    source = _unsafe_input(tmp_path, attack)

    def reject_parse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unsafe or oversized evidence reached JSON materialization")

    monkeypatch.setattr(json, "loads", reject_parse)
    with pytest.raises((OSError, RuntimeArtifactError, typer.BadParameter)):
        loader(source)


@pytest.mark.parametrize("module_name", (
    "ceqanet_detail_parse_cli", "ceqanet_result_parse_cli", "ceqanet_vocabulary_export_cli",
))
@pytest.mark.parametrize("attack", ("ancestor", "final", "oversized"))
def test_html_loaders_reject_unsafe_input(
    tmp_path: Path, module_name: str, attack: str,
) -> None:
    module = importlib.import_module(f"constructionsight.{module_name}")
    source = _unsafe_input(tmp_path, attack)
    with pytest.raises((OSError, RuntimeArtifactError, typer.BadParameter)):
        module._extract_html(source, input_format="html", snapshot_index=0)


@pytest.mark.parametrize("module_name", (
    "ceqanet_detail_parse_cli", "ceqanet_result_parse_cli", "ceqanet_vocabulary_export_cli",
))
def test_html_auto_detection_uses_one_byte_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module_name: str,
) -> None:
    module = importlib.import_module(f"constructionsight.{module_name}")
    path = tmp_path / "input.html"
    path.write_text("<p>reviewed content</p>", encoding="utf-8")
    original_loads = json.loads

    def swap_after_detection(value: Any, *args: Any, **kwargs: Any) -> Any:
        path.write_text("<p>substituted content</p>", encoding="utf-8")
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr(json, "loads", swap_after_detection)
    result = module._extract_html(path, input_format="auto", snapshot_index=0)
    assert result[0] == "<p>reviewed content</p>"


@pytest.mark.parametrize("attack", ("ancestor", "final"))
def test_intake_file_rejects_symlinks(tmp_path: Path, attack: str) -> None:
    with pytest.raises((OSError, RuntimeArtifactError)):
        intake_service.inspect_lawful_file(_unsafe_input(tmp_path, attack))


@pytest.mark.parametrize("attack", ("ancestor", "final"))
def test_csv_file_rejects_symlinks_before_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str,
) -> None:
    source = _unsafe_input(tmp_path, attack)

    def reject_inspection(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("symlinked evidence reached CSV inspection")

    monkeypatch.setattr(ceqanet_csv_cli, "inspect_ceqanet_csv_bytes", reject_inspection)
    with pytest.raises(typer.BadParameter):
        ceqanet_csv_cli.inspect_csv_file(
            source,
            source_url="https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2024010001",
        )


@pytest.mark.parametrize("operation", ("replay", "verify-source", "verify-replay"))
@pytest.mark.parametrize("attack", ("ancestor", "final", "oversized"))
def test_csv_replay_rejects_each_unsafe_input_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, attack: str,
) -> None:
    unsafe = _unsafe_input(tmp_path, attack)
    source = tmp_path / "safe.json"
    source.write_text("{}", encoding="utf-8")
    parses = 0

    def reject_unsafe_parse(*args: Any, **kwargs: Any) -> Any:
        nonlocal parses
        parses += 1
        if operation == "verify-replay" and parses == 1:
            return {}
        raise AssertionError("unsafe replay evidence reached JSON materialization")

    monkeypatch.setattr(json, "loads", reject_unsafe_parse)
    with pytest.raises(typer.BadParameter):
        if operation == "replay":
            ceqanet_csv_cli.replay_csv_execution(unsafe, tmp_path / "output.json")
        elif operation == "verify-source":
            ceqanet_csv_cli.verify_csv_replay(unsafe, source)
        else:
            ceqanet_csv_cli.verify_csv_replay(source, unsafe)
    assert parses == (1 if operation == "verify-replay" else 0)
