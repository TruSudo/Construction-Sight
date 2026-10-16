"""Read-only operational checks for independent Phase 3 deployment."""

import json
import subprocess

from constructionsight import collection_schedule as schedule
from constructionsight.investigation_runtime import main


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
