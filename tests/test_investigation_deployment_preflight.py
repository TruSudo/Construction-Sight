"""Read-only operational checks for independent Phase 3 deployment."""

import json
import subprocess

from constructionsight import collection_schedule as schedule
from constructionsight.investigation_jobs import JobDefinition
from constructionsight.investigation_runtime import InvestigationRuntime, main


def _manager(*args):
    assert args[0] == "show"  # preflight never installs, enables or restarts a unit
    return subprocess.CompletedProcess(
        args, 0, "ActiveState=active\nUnitFileState=enabled\nLoadState=loaded\nResult=success\n", ""
    )


def test_preflight_without_installation_is_read_only_and_not_ready(tmp_path, monkeypatch, capsys):
    directory = tmp_path / "private"
    monkeypatch.setattr(
        schedule,
        "systemctl",
        lambda *args: subprocess.CompletedProcess(args, 1, "", "No user manager"),
    )
    assert main(["--data-dir", str(directory), "preflight"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == "constructionsight.deployment-preflight/v1"
    assert result["local_service_preflight_passed"] is False
    assert result["checks"]["private_data_directory"] is False
    assert result["checks"]["capture_timer_active"] is False
    assert result["checks"]["investigation_timer_active"] is False
    assert result["source_authorization_assessed"] is False
    assert result["owner_device_changes_made"] is False
    assert not directory.exists()


def test_preflight_requires_exact_reviewed_units_active_timers_and_private_data(
    tmp_path, monkeypatch
):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    runtime = InvestigationRuntime(directory)
    runtime.close()
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    preview = schedule.preview(directory, directory)
    units = {
        schedule.UNIT + ".service": preview["service"],
        schedule.UNIT + ".timer": preview["timer"],
        schedule.WORKER_UNIT + ".service": preview["investigation_service"],
        schedule.WORKER_UNIT + ".timer": preview["investigation_timer"],
    }
    for name, content in units.items():
        (unit_dir / name).write_text(content)
        (unit_dir / name).chmod(0o600)
    schedule.write(
        directory,
        {
            **schedule.DEFAULT,
            "enabled": True,
            "installed_digest": preview["digest"],
        },
    )
    monkeypatch.setattr(schedule, "systemctl", _manager)
    original = (directory / "schedule.json").read_bytes()
    ready = schedule.deployment_preflight(directory, directory, unit_directory=unit_dir)
    assert ready["local_service_preflight_passed"] is True
    assert all(ready["checks"].values())
    assert ready["blockers"] == []
    assert ready["network_requests_made"] is False
    assert ready["source_authorization_assessed"] is False
    assert (directory / "schedule.json").read_bytes() == original

    # Stored digest alone is insufficient: a changed unit must fail preflight.
    (unit_dir / (schedule.WORKER_UNIT + ".service")).write_text("changed")
    changed = schedule.deployment_preflight(directory, directory, unit_directory=unit_dir)
    assert changed["local_service_preflight_passed"] is False
    assert changed["checks"]["unit_files_match_reviewed_preview"] is False
    assert changed["checks"]["reviewed_bundle_digest_current"] is True

    # Restore exact bytes, but reject a world-readable installed unit.
    service = unit_dir / (schedule.WORKER_UNIT + ".service")
    service.write_text(preview["investigation_service"])
    service.chmod(0o644)
    insecure = schedule.deployment_preflight(directory, directory, unit_directory=unit_dir)
    assert insecure["checks"]["unit_files_match_reviewed_preview"] is False
    service.chmod(0o600)

    # Restored units still cannot pass if the operator has not reviewed this digest.
    schedule.write(
        directory,
        {
            **schedule.DEFAULT,
            "enabled": True,
            "installed_digest": "stale-review",
        },
    )
    stale = schedule.deployment_preflight(directory, directory, unit_directory=unit_dir)
    assert stale["checks"]["unit_files_match_reviewed_preview"] is True
    assert stale["checks"]["reviewed_bundle_digest_current"] is False
    assert stale["local_service_preflight_passed"] is False


def test_preflight_rejects_overly_permissive_directory_and_schedule_warning(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    runtime = InvestigationRuntime(directory)
    runtime.close()
    units = tmp_path / "units"
    units.mkdir()
    preview = schedule.preview(directory, directory)
    for name, key in (
        (schedule.UNIT + ".service", "service"),
        (schedule.UNIT + ".timer", "timer"),
        (schedule.WORKER_UNIT + ".service", "investigation_service"),
        (schedule.WORKER_UNIT + ".timer", "investigation_timer"),
    ):
        (units / name).write_text(preview[key])
        (units / name).chmod(0o600)
    schedule.write(
        directory,
        {**schedule.DEFAULT, "enabled": True, "installed_digest": preview["digest"]},
    )
    monkeypatch.setattr(schedule, "systemctl", _manager)
    directory.chmod(0o755)
    try:
        report = schedule.deployment_preflight(directory, directory, unit_directory=units)
        assert report["checks"]["private_data_directory"] is False
        assert report["local_service_preflight_passed"] is False
    finally:
        directory.chmod(0o700)

    (directory / "investigation-inbox-run.json").write_text('{"inbox_failed": 1}')
    report = schedule.deployment_preflight(directory, directory, unit_directory=units)
    assert report["checks"]["private_data_directory"] is True
    assert report["local_service_preflight_passed"] is False
    assert "schedule_or_intake_warning" in report["blockers"]


def test_preflight_exposes_pending_work_and_blocks_terminal_job_failures(
    tmp_path, monkeypatch
):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    runtime = InvestigationRuntime(directory)
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    preview = schedule.preview(directory, directory)
    for name, key in (
        (schedule.UNIT + ".service", "service"),
        (schedule.UNIT + ".timer", "timer"),
        (schedule.WORKER_UNIT + ".service", "investigation_service"),
        (schedule.WORKER_UNIT + ".timer", "investigation_timer"),
    ):
        path = unit_dir / name
        path.write_text(preview[key])
        path.chmod(0o600)
    schedule.write(
        directory,
        {**schedule.DEFAULT, "enabled": True, "installed_digest": preview["digest"]},
    )
    monkeypatch.setattr(schedule, "systemctl", _manager)
    try:
        initial = schedule.deployment_preflight(directory, directory, unit_directory=unit_dir)
        assert initial["local_service_preflight_passed"] is True
        assert initial["investigation_queue"]["pending"] == 0
        assert initial["investigation_queue"]["terminal_failures"] == 0

        runtime.queue.enqueue(
            JobDefinition(
                kind="parcel_assess", inputs={"source_id": "permit:demo", "receipt_id": "obs:demo"}
            )
        )
        queued = schedule.deployment_preflight(directory, directory, unit_directory=unit_dir)
        assert queued["local_service_preflight_passed"] is True
        assert queued["investigation_queue"]["counts"]["queued"] == 1
        assert queued["investigation_queue"]["pending"] == 1

        claim = runtime.queue.claim("synthetic-test-worker")
        assert claim is not None
        runtime.queue.fail(claim, error_code="synthetic_nonretryable", retryable=False)
        failed = schedule.deployment_preflight(directory, directory, unit_directory=unit_dir)
        assert failed["local_service_preflight_passed"] is False
        assert "no_terminal_investigation_job_failures" in failed["blockers"]
        assert failed["investigation_queue"]["counts"]["failed"] == 1
        assert failed["investigation_queue"]["terminal_failures"] == 1
    finally:
        runtime.close()


def test_queue_health_does_not_create_database_and_rejects_untrusted_file(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    missing = schedule.investigation_queue_health(directory)
    assert missing["available"] is False
    assert missing["error_code"] == "database_not_initialized"
    assert not (directory / "investigations.sqlite3").exists()

    original = tmp_path / "public.sqlite3"
    original.write_bytes(b"untrusted")
    (directory / "investigations.sqlite3").symlink_to(original)
    rejected = schedule.investigation_queue_health(directory)
    assert rejected["available"] is False
    assert rejected["error_code"].startswith("database_read_failed:")
    assert original.read_bytes() == b"untrusted"
