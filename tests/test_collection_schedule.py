from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from constructionsight import collection_schedule as schedule
from constructionsight import command_center_state as state
from constructionsight.data_folder import point_startup
from constructionsight.lead_workflow import begin_run, finish_run


def test_review_install_next_run_disable_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, units = tmp_path / "data", tmp_path / "units"
    schedule.save(data, {"hour": 7, "minute": 30, "timezone": "America/Los_Angeles"})
    active = False

    def manager(*args: str) -> subprocess.CompletedProcess[str]:
        nonlocal active
        if args[0] == "restart":
            active = True
        elif args[0] == "disable":
            active = False
        output = (
            (
                "ActiveState=" + ("active" if active else "inactive") + "\nUnitFileState=enabled\n"
                "NextElapseUSecRealtime=Thu 2026-10-15 07:30:00 PDT\nResult=success\n"
            )
            if args[0] == "show"
            else ""
        )
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(schedule, "systemctl", manager)
    before = schedule.status(data, data)
    assert before["next_run"] is None
    with pytest.raises(ValueError, match="Review"):
        schedule.install(
            data,
            data,
            {"reviewed": False, "digest": before["preview"]["digest"]},
            unit_directory=units,
        )
    installed = schedule.install(
        data, data, {"reviewed": True, "digest": before["preview"]["digest"]}, unit_directory=units
    )
    assert installed["active"] and installed["config"]["enabled"]
    assert installed["next_run"] == "Thu 2026-10-15 07:30:00 PDT"
    assert "*-*-* 07:30:00 America/Los_Angeles" in (units / (schedule.UNIT + ".timer")).read_text()
    assert schedule.disable(data, data)["config"]["enabled"] is False

    def failed(*args: str) -> subprocess.CompletedProcess[str]:
        if args[0] == "show":
            return manager(*args)
        return subprocess.CompletedProcess(args, 1, "", "Demo install failure")

    monkeypatch.setattr(schedule, "systemctl", failed)
    with pytest.raises(ValueError, match="Demo install failure"):
        schedule.install(
            data,
            data,
            {"reviewed": True, "digest": before["preview"]["digest"]},
            unit_directory=units,
        )
    assert not schedule.config(data)["enabled"]
    assert "Demo install failure" in str(schedule.warning(data))


def test_scheduled_runner_redirect_disabled_and_403_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    startup, target = tmp_path / "startup", tmp_path / "relocated"
    startup.mkdir()
    state.initialize(target)
    point_startup(startup, target)
    schedule.write(target, {**schedule.DEFAULT, "enabled": True})
    collector = Mock(return_value=0)
    monkeypatch.setattr("constructionsight.live_command_center.main", collector)
    state.save_settings(target, {"source_enabled": False})
    assert schedule.run(startup) == 0
    collector.assert_not_called()
    state.save_settings(target, {"source_enabled": True})

    def denied(_args: list[str]) -> int:
        run_id = begin_run(target)
        finish_run(target, run_id, None, "HTTPStatusError: 403 Forbidden")
        return 1

    monkeypatch.setattr("constructionsight.live_command_center.main", denied)
    assert schedule.run(startup) == 1
    assert not schedule.config(target)["enabled"] and not state.settings(target)["source_enabled"]
    assert "failed" in str(schedule.warning(target))
    assert json.loads((target / "schedule-run.json").read_text())["outcome"] == "error"


def test_unavailable_manager_stays_unknown_and_unit_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        schedule, "systemctl", lambda *args: subprocess.CompletedProcess(args, 0, "No manager", "")
    )
    result = schedule.status(tmp_path, tmp_path)
    assert not result["available"] and result["next_run"] is None
    preview = schedule.preview(tmp_path, tmp_path)
    assert "Persistent=true" in preview["timer"]
    assert "constructionsight.collection_schedule" in preview["service"]
    for suffix in ("timer", "service"):
        (tmp_path / (schedule.UNIT + "." + suffix)).write_text(preview[suffix])
    result = subprocess.run(
        [
            "/usr/bin/systemd-analyze",
            "verify",
            str(tmp_path / (schedule.UNIT + ".service")),
            str(tmp_path / (schedule.UNIT + ".timer")),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    with pytest.raises(ValueError):
        schedule.save(tmp_path, {"hour": 24, "minute": 0, "timezone": "UTC"})
    with pytest.raises(ValueError):
        schedule.save(tmp_path, {"hour": 1, "minute": 0, "timezone": "Invented/Timezone"})
