"""Output containment and conflict preservation at real operator boundaries."""

from __future__ import annotations

import importlib
import os
import stat
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import constructionsight.storage.runtime_artifacts as runtime_artifacts
from constructionsight.source_registry_update_plan_cli import app as registry_app
from constructionsight.storage.runtime_artifacts import (
    RuntimeArtifactError,
    RuntimeArtifactLimitError,
    write_runtime_text,
)

_WRITERS = (
    "ceqanet_chain_cli", "ceqanet_detail_enrichment_cli", "ceqanet_detail_execute_cli",
    "ceqanet_detail_parse_cli", "ceqanet_fixture_query_cli", "ceqanet_listing_plan_cli",
    "ceqanet_operator_archive_cli", "ceqanet_operator_archive_verify_cli",
    "ceqanet_operator_bundle_cli", "ceqanet_operator_bundle_verify_cli",
    "ceqanet_operator_export_cli", "ceqanet_operator_package_cli", "ceqanet_operator_report_cli",
    "ceqanet_persistence_execute_cli", "ceqanet_persistence_preview_cli",
    "ceqanet_result_parse_cli", "ceqanet_vocabulary_export_cli", "ceqanet_write_plan_cli",
    "cli", "external_gap_cli", "external_intelligence_cli", "intake_cli",
    "opportunity_cli", "parcel_source_cli", "site_resolution_cli",
    "ceqanet_recurring_run_cli", "ceqanet_csv_access_policy_cli", "ceqanet_csv_cli",
    "ceqanet_csv_evidence_series_cli", "ceqanet_maturity_proposal_cli",
    "source_registry_update_plan_cli",
)


def _write(module_name: str, output: Path, value: str, *, overwrite: bool = True) -> None:
    module = importlib.import_module(f"constructionsight.{module_name}")
    payload = {"message": value}
    if module_name == "source_registry_update_plan_cli":
        module._atomic_write_text(output, value)
    elif module_name == "ceqanet_recurring_run_cli":
        module._write_json(output, payload)
    elif module_name == "ceqanet_csv_evidence_series_cli":
        module._write_json(output, payload, inputs=(), overwrite=overwrite)
    elif module_name in {"ceqanet_csv_access_policy_cli", "ceqanet_maturity_proposal_cli"}:
        module._write_json(output, payload, overwrite=overwrite)
    elif module_name == "ceqanet_csv_cli":
        module._write_json_file(output, payload, overwrite=overwrite)
    else:
        module._write_json_file(output, payload)


@pytest.mark.parametrize("module_name", _WRITERS)
@pytest.mark.parametrize("attack", ("ancestor", "final", "oversized"))
def test_operator_writers_reject_unsafe_or_oversized_output(
    tmp_path: Path, module_name: str, attack: str,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    original = outside / "report.json"
    original.write_bytes(b"retain outside or previous content")
    if attack == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        output = alias / original.name
    elif attack == "final":
        output = tmp_path / "alias.json"
        output.symlink_to(original)
    else:
        output = original
    content = "new evidence" if attack != "oversized" else "x" * (16 * 1024 * 1024 + 1)
    with pytest.raises((OSError, ValueError, typer.BadParameter)):
        _write(module_name, output, content)
    assert original.read_bytes() == b"retain outside or previous content"
    if attack == "final":
        assert output.is_symlink()
    assert sorted(p.name for p in outside.iterdir()) == [original.name]


@pytest.mark.parametrize("module_name", (
    "ceqanet_csv_access_policy_cli", "ceqanet_maturity_proposal_cli",
    "ceqanet_csv_cli", "ceqanet_csv_evidence_series_cli",
))
def test_create_only_operator_output_preserves_racing_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module_name: str,
) -> None:
    output = tmp_path / "report.json"
    original_exists = Path.exists
    observed = False

    def race_after_absence_check(path: Path) -> bool:
        nonlocal observed
        if path == output and not observed:
            observed = True
            path.write_bytes(b"racing winner")
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", race_after_absence_check)
    with pytest.raises((OSError, ValueError, typer.BadParameter)):
        _write(module_name, output, "losing publication", overwrite=False)
    assert observed
    assert output.read_bytes() == b"racing winner"


def test_report_parent_swap_cannot_redirect_temporary_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "reports"
    parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    output = parent / "report.json"
    held = tmp_path / "held"
    original_open = os.open
    changed = False

    def swap_at_stage_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal changed
        if not changed and flags & os.O_CREAT:
            changed = True
            parent.rename(held)
            parent.symlink_to(outside, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_at_stage_open)
    with pytest.raises((OSError, ValueError)):
        _write("source_registry_update_plan_cli", output, "new evidence")
    assert changed
    assert list(outside.iterdir()) == []


def test_registry_plan_preserves_a_concurrent_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text("[]", encoding="utf-8")
    output = tmp_path / "plan.json"
    original_exists = Path.exists
    raced = False

    def race_after_check(path: Path) -> bool:
        nonlocal raced
        if path == output and not raced:
            raced = True
            output.write_bytes(b"concurrent plan")
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", race_after_check)
    result = CliRunner().invoke(registry_app, ["plan", str(registry), "--output", str(output)])
    assert raced
    assert result.exit_code != 0
    assert output.read_bytes() == b"concurrent plan"


@pytest.mark.parametrize("attack", ("ancestor", "final"))
@pytest.mark.parametrize("writer", ("listing", "csv_emit", "markdown", "checklist"))
def test_alternate_operator_outputs_reject_symlink_traversal(
    tmp_path: Path, attack: str, writer: str,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    retained = outside / "report.json"
    retained.write_bytes(b"original")
    if attack == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        output = alias / retained.name
    else:
        output = tmp_path / "alias.json"
        output.symlink_to(retained)

    with pytest.raises((OSError, ValueError)):
        if writer == "listing":
            module = importlib.import_module("constructionsight.ceqanet_listing_execute_cli")
            module._write_or_print_json({"message": "new"}, output)
        elif writer == "csv_emit":
            module = importlib.import_module("constructionsight.ceqanet_csv_cli")
            module._emit_json({"message": "new"}, output)
        elif writer == "markdown":
            module = importlib.import_module("constructionsight.ceqanet_operator_report_cli")
            module._write_markdown_file(output, "new")
        else:
            module = importlib.import_module("constructionsight.source_verification_checklist_cli")
            registry = tmp_path / "registry.json"
            registry.write_text("[]", encoding="utf-8")
            module.source_observation_template(registry, output)
    assert retained.read_bytes() == b"original"


@pytest.mark.parametrize("content", ("", "plain text\n", "é😀\n"))
def test_text_replacement_preserves_external_hardlink_and_exact_utf8(
    tmp_path: Path, content: str,
) -> None:
    target = tmp_path / "report.txt"
    retained = tmp_path / "retained.txt"
    retained.write_bytes(b"prior evidence")
    target.hardlink_to(retained)
    write_runtime_text(target, content)
    assert retained.read_bytes() == b"prior evidence"
    assert target.read_bytes() == content.encode("utf-8")
    assert target.stat().st_ino != retained.stat().st_ino
    assert sorted(p.name for p in tmp_path.iterdir()) == ["report.txt", "retained.txt"]


def test_text_output_ceiling_counts_utf8_bytes_before_replacement(tmp_path: Path) -> None:
    target = tmp_path / "report.txt"
    target.write_bytes(b"prior")
    with pytest.raises(RuntimeArtifactLimitError):
        write_runtime_text(target, "😀" * 2, max_bytes=7)
    assert target.read_bytes() == b"prior"
    assert list(tmp_path.iterdir()) == [target]
    write_runtime_text(target, "😀" * 2, max_bytes=8)
    assert target.read_bytes() == "😀😀".encode()


@pytest.mark.parametrize("boundary", ("data_sync", "replace", "parent_sync"))
def test_replacement_failure_never_leaves_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str,
) -> None:
    target = tmp_path / "report.txt"
    target.write_bytes(b"prior")
    parent_inode = tmp_path.stat().st_ino
    original_sync, original_replace = os.fsync, os.replace
    published = False
    injected = False

    def sync(descriptor: int) -> None:
        nonlocal injected
        info = os.fstat(descriptor)
        selected = (
            boundary == "data_sync" and stat.S_ISREG(info.st_mode)
        ) or (boundary == "parent_sync" and published and info.st_ino == parent_inode)
        if selected and not injected:
            injected = True
            raise OSError("injected durability failure")
        original_sync(descriptor)

    def replace(*args: Any, **kwargs: Any) -> None:
        nonlocal published, injected
        assert target.read_bytes() == b"prior"
        if boundary == "replace":
            injected = True
            raise OSError("injected replacement failure")
        original_replace(*args, **kwargs)
        published = True

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(OSError, match="injected"):
        write_runtime_text(target, "complete new evidence")
    assert injected
    assert target.read_bytes() == (b"complete new evidence" if published else b"prior")
    assert list(tmp_path.iterdir()) == [target]


def test_replacement_is_synced_in_order_and_uses_pinned_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "report.txt"
    target.write_bytes(b"prior")
    events: list[str] = []
    parent_inode = tmp_path.stat().st_ino
    original_sync, original_replace = os.fsync, os.replace

    def sync(descriptor: int) -> None:
        info = os.fstat(descriptor)
        if stat.S_ISREG(info.st_mode):
            events.append("file")
        elif info.st_ino == parent_inode:
            events.append("parent")
        original_sync(descriptor)

    def replace(source: str, destination: str, **kwargs: Any) -> None:
        assert Path(source).name == source
        assert destination == target.name
        assert isinstance(kwargs["src_dir_fd"], int)
        assert os.fstat(kwargs["dst_dir_fd"]).st_ino == parent_inode
        events.append("replace")
        original_replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    write_runtime_text(target, "new")
    assert events.index("file") < events.index("replace") < events.index("parent")


@pytest.mark.parametrize("capability", (
    "_DIRECTORY_RELATIVE_REPLACEMENT_SUPPORTED", "_DIRECTORY_RELATIVE_PUBLICATION_SUPPORTED",
))
def test_unsupported_output_primitive_fails_before_touching_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capability: str,
) -> None:
    target = tmp_path / "new-parent" / "report.txt"
    monkeypatch.setattr(runtime_artifacts, capability, False)
    with pytest.raises(RuntimeArtifactError, match="unavailable"):
        write_runtime_text(target, "new")
    assert list(tmp_path.iterdir()) == []
