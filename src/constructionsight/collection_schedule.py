"""Reviewed daily capture via a local systemd user timer; never sends outreach."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import SQLAlchemyError

from constructionsight import command_center_state as state
from constructionsight.data_folder import resolve_folder
from constructionsight.lead_workflow import now, run_history

UNIT = "constructionsight-capture"
WORKER_UNIT = "constructionsight-investigations"
DEFAULT = {"hour": 6, "minute": 0, "timezone": "America/Los_Angeles", "enabled": False}


def config(directory: Path) -> dict[str, Any]:
    path = directory / "schedule.json"
    return {**DEFAULT, **(json.loads(path.read_text()) if path.exists() else {})}


def write(directory: Path, value: dict[str, Any], name: str = "schedule.json") -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = directory / ("." + name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(directory / name)


def save(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"hour", "minute", "timezone"}:
        raise ValueError("Daily schedule requires hour, minute and timezone")
    if (
        type(payload["hour"]) is not int
        or not 0 <= payload["hour"] <= 23
        or type(payload["minute"]) is not int
        or not 0 <= payload["minute"] <= 59
    ):
        raise ValueError("Enter a daily time from 00:00 to 23:59")
    try:
        if not isinstance(payload["timezone"], str):
            raise ValueError("Timezone must be text")
        ZoneInfo(payload["timezone"])
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown IANA timezone") from exc
    value = {**config(directory), **payload}
    write(directory, value)
    return value


def unit_quote(value: str) -> str:
    if any(ord(c) < 32 for c in value):
        raise ValueError("Unit paths cannot contain control characters")
    return (
        '"'
        + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
        + '"'
    )


def preview(directory: Path, startup: Path, python: Path | None = None) -> dict[str, Any]:
    from constructionsight.investigation_runtime import systemd_units

    value = config(directory)
    calendar = f"*-*-* {value['hour']:02d}:{value['minute']:02d}:00 {value['timezone']}"
    executable = python or Path(sys.executable)
    service = (
        "[Unit]\nDescription=ConstructionSight lawful daily collection\n\n[Service]\nType=oneshot\n"
    )
    service += (
        "ExecStart="
        + " ".join(
            unit_quote(s)
            for s in [
                str(executable.absolute()),
                "-m",
                "constructionsight.collection_schedule",
                "--run",
                "--data-dir",
                str(startup.absolute()),
            ]
        )
        + "\n"
    )
    service += "Environment=PYTHONUNBUFFERED=1\nTimeoutStartSec=20min\nUMask=0077\n"
    timer = (
        "[Unit]\nDescription=ConstructionSight daily collection timer\n\n[Timer]\n"
        f"OnCalendar={calendar}\nPersistent=true\nAccuracySec=1min\nUnit={UNIT}.service\n"
        "\n[Install]\nWantedBy=timers.target\n"
    )
    worker_units = systemd_units(executable, startup)
    investigation_service = worker_units[WORKER_UNIT + ".service"]
    investigation_timer = worker_units[WORKER_UNIT + ".timer"]
    digest = hashlib.sha256(
        (service + timer + investigation_service + investigation_timer).encode()
    ).hexdigest()
    return {
        "service": service,
        "timer": timer,
        "investigation_service": investigation_service,
        "investigation_timer": investigation_timer,
        "digest": digest,
        "calendar": calendar,
        "unit_directory": str(Path.home() / ".config/systemd/user"),
        "steps": [
            (
                f"Save the reviewed {UNIT} and {WORKER_UNIT} service/timer pairs "
                "in ~/.config/systemd/user/."
            ),
            "systemctl --user daemon-reload",
            f"systemctl --user enable --now {UNIT}.timer {WORKER_UNIT}.timer",
            f"systemctl --user list-timers {UNIT}.timer",
            f"journalctl --user -u {UNIT}.service -n 50 --no-pager",
            'Optional, to run while logged out: sudo loginctl enable-linger "$USER".'
            " Requires administrator approval on your OS.",
        ],
        "notes": (
            "Zorin OS / Ubuntu: user timers run while logged in unless lingering is enabled. "
            "Persistent catches up one missed run after downtime; it does not wake a "
            "powered-off computer. Keep this Python environment and application installed. "
            "CEQA background requests require a separate reviewed finite plan; "
            "installing these units grants no CEQA access. Nothing sends outreach."
        ),
    }


def systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *args], capture_output=True, text=True, timeout=10, check=False
    )


def properties(unit: str, fields: list[str]) -> tuple[dict[str, str], str | None]:
    try:
        result = systemctl("show", unit, *["--property=" + field for field in fields])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, str(exc)
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if result.returncode or "ActiveState" not in values:
        return {}, (result.stderr or result.stdout or "User systemd manager unavailable").strip()[
            :1000
        ]
    return values, None


def warning(directory: Path) -> str | None:
    value = config(directory)
    if value.get("install_error"):
        return "Daily schedule installation failed: " + str(value["install_error"])
    path = directory / "schedule-run.json"
    last = json.loads(path.read_text()) if path.exists() else {}
    if last.get("outcome") == "error":
        return "Last scheduled run failed: " + str(
            last.get("error") or "See source run history and journalctl"
        )
    ceqa_path = directory / "ceqa-background-run.json"
    ceqa = json.loads(ceqa_path.read_text()) if ceqa_path.exists() else {}
    if ceqa.get("ceqa_failed"):
        return "CEQA background acquisition stopped; inspect its reviewed plan and retained result"
    for lane in ("smarts", "inbox"):
        poll_path = directory / f"investigation-{lane}-run.json"
        poll = json.loads(poll_path.read_text()) if poll_path.exists() else {}
        if poll.get(f"{lane}_failed"):
            return f"Investigation {lane} intake failed; retained evidence requires review"
    active = directory / "active.json"
    if active.exists():
        snapshot = json.loads(active.read_text())
        handoff = snapshot.get("investigation_handoff", {})
        if handoff.get("status") == "error":
            worker_path = directory / "investigation-worker-run.json"
            worker = json.loads(worker_path.read_text()) if worker_path.exists() else {}
            if not (
                worker.get("smarts_polled") is True
                and snapshot.get("captured_at")
                and worker.get("source_capture_at") == snapshot["captured_at"]
                and worker.get("failed_jobs") == 0
                and worker.get("smarts_failed", 0) == 0
            ):
                return (
                    "Source evidence retained; investigation handoff failed. "
                    "Resume the local worker."
                )
    return None


def status(directory: Path, startup: Path) -> dict[str, Any]:
    planned = preview(directory, startup)
    value = config(directory)
    timer, error = properties(
        UNIT + ".timer", ["ActiveState", "NextElapseUSecRealtime", "UnitFileState", "LoadState"]
    )
    service, _ = (
        properties(UNIT + ".service", ["ActiveState", "Result", "ExecMainStatus"])
        if timer
        else ({}, None)
    )
    active = timer.get("ActiveState") == "active"
    worker_timer, worker_error = properties(
        WORKER_UNIT + ".timer", ["ActiveState", "UnitFileState", "LoadState"]
    )
    worker_service, _ = properties(WORKER_UNIT + ".service", ["Result", "ExecMainStatus"])
    next_run = timer.get("NextElapseUSecRealtime") if active else None
    if next_run in ("", "n/a", "0"):
        next_run = None
    issue = warning(directory)
    if service.get("Result") not in (None, "", "success"):
        issue = (
            "Scheduled collection service failed: " + service["Result"] + " · inspect journalctl"
        )
    if value["enabled"] and not active:
        issue = issue or "Daily collection is enabled in settings but the timer is not active"
    if value["enabled"] and worker_timer.get("ActiveState") != "active":
        issue = issue or "Investigation worker timer is not active; retained jobs may be waiting"
    if worker_service.get("Result") not in (None, "", "success"):
        issue = (
            issue or "Investigation worker failed; inspect its retained job status and journalctl"
        )
    path = directory / "schedule-run.json"
    return {
        "config": value,
        "preview": planned,
        "available": bool(timer),
        "manager_error": error,
        "active": active,
        "next_run": next_run,
        "unit_state": timer.get("UnitFileState"),
        "pending_review": value.get("installed_digest") != planned["digest"],
        "warning": issue,
        "last_run": json.loads(path.read_text()) if path.exists() else None,
        "investigation_worker": {
            "active": worker_timer.get("ActiveState") == "active",
            "manager_error": worker_error,
            "last_result": worker_service.get("Result"),
        },
    }



def deployment_preflight(
    directory: Path, startup: Path, *, unit_directory: Path | None = None
) -> dict[str, Any]:
    """Read-only local service check; never installs units or grants source access."""
    snapshot = status(directory, startup)
    planned = snapshot["preview"]
    try:
        attributes = directory.lstat()
        private_directory = (
            stat.S_ISDIR(attributes.st_mode)
            and attributes.st_uid == os.geteuid()
            and stat.S_IMODE(attributes.st_mode) & 0o077 == 0
        )
    except OSError:
        private_directory = False

    units = unit_directory or Path.home() / ".config/systemd/user"
    expected = {
        UNIT + ".service": planned["service"],
        UNIT + ".timer": planned["timer"],
        WORKER_UNIT + ".service": planned["investigation_service"],
        WORKER_UNIT + ".timer": planned["investigation_timer"],
    }
    unit_files_match = True
    for name, content in expected.items():
        path = units / name
        try:
            attributes = path.lstat()
            if (
                not stat.S_ISREG(attributes.st_mode)
                or attributes.st_uid != os.geteuid()
                or stat.S_IMODE(attributes.st_mode) & 0o077
                or path.read_text() != content
            ):
                unit_files_match = False
        except OSError:
            unit_files_match = False

    checks = {
        "private_data_directory": private_directory,
        "user_manager_available": bool(
            snapshot["available"] and not snapshot["investigation_worker"]["manager_error"]
        ),
        "reviewed_bundle_digest_current": bool(
            snapshot["config"]["enabled"] and not snapshot["pending_review"]
        ),
        "unit_files_match_reviewed_preview": unit_files_match,
        "capture_timer_active": snapshot["active"],
        "investigation_timer_active": snapshot["investigation_worker"]["active"],
    }
    blockers = [key for key, passed in checks.items() if not passed]
    if snapshot["warning"]:
        blockers.append("schedule_or_intake_warning")
    return {
        "schema_version": "constructionsight.deployment-preflight/v1",
        "local_service_preflight_passed": not blockers,
        "checks": checks,
        "blockers": blockers,
        "warning": snapshot["warning"],
        "reviewed_bundle_digest": planned["digest"],
        "network_requests_made": False,
        "source_authorization_assessed": False,
        "owner_device_changes_made": False,
    }


def install(
    directory: Path, startup: Path, payload: dict[str, Any], *, unit_directory: Path | None = None
) -> dict[str, Any]:
    planned = preview(directory, startup)
    if (
        set(payload) != {"reviewed", "digest"}
        or payload["reviewed"] is not True
        or payload["digest"] != planned["digest"]
    ):
        raise ValueError("Review the current unit preview before installing")
    if not status(directory, startup)["available"]:
        raise ValueError("A running systemd user manager is required; follow the Zorin setup steps")
    units = unit_directory or Path.home() / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    value = config(directory)
    try:
        for filename, content in {
            UNIT + ".service": planned["service"],
            UNIT + ".timer": planned["timer"],
            WORKER_UNIT + ".service": planned["investigation_service"],
            WORKER_UNIT + ".timer": planned["investigation_timer"],
        }.items():
            path = units / filename
            if path.is_symlink():
                raise ValueError("Schedule unit paths must not be symbolic links")
            path.write_text(content)
            path.chmod(0o600)
        value.update(enabled=True, installed_digest=planned["digest"], install_error=None)
        write(directory, value)
        for command in [
            ("daemon-reload",),
            ("enable", UNIT + ".timer", WORKER_UNIT + ".timer"),
            ("restart", UNIT + ".timer", WORKER_UNIT + ".timer"),
        ]:
            result = systemctl(*command)
            if result.returncode:
                raise ValueError(
                    (result.stderr or result.stdout or "systemctl failed").strip()[:1000]
                )
        value.update(enabled=True, installed_digest=planned["digest"], install_error=None)
        write(directory, value)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        with suppress(OSError, subprocess.TimeoutExpired):
            systemctl("disable", "--now", UNIT + ".timer", WORKER_UNIT + ".timer")
        value.update(enabled=False, install_error=str(exc))
        write(directory, value)
        raise ValueError("Daily schedule installation failed: " + str(exc)) from exc
    result_status = status(directory, startup)
    if not result_status["active"] or not result_status["investigation_worker"]["active"]:
        with suppress(OSError, subprocess.TimeoutExpired):
            systemctl("disable", "--now", UNIT + ".timer", WORKER_UNIT + ".timer")
        value.update(enabled=False, install_error="Timer did not become active")
        write(directory, value)
        raise ValueError("Timer did not become active; inspect systemctl status")
    return result_status


def disable(directory: Path, startup: Path) -> dict[str, Any]:
    value = config(directory)
    value.update(enabled=False)
    write(directory, value)
    try:
        result = systemctl("disable", "--now", UNIT + ".timer", WORKER_UNIT + ".timer")
        if not result.returncode:
            value["install_error"] = None
        else:
            value["install_error"] = (result.stderr or result.stdout).strip()[:1000]
    except (OSError, subprocess.TimeoutExpired) as exc:
        value["install_error"] = str(exc)
    write(directory, value)
    return status(directory, startup)


def run(startup: Path) -> int:
    directory = resolve_folder(startup)
    value = config(directory)
    if not value["enabled"] or not state.settings(directory)["source_enabled"]:
        write(directory, {"at": now(), "outcome": "skipped", "error": None}, "schedule-run.json")
        return 0
    from constructionsight.live_command_center import main as collect

    result = collect(["--data-dir", str(startup), "--capture-only", "--no-browser"])
    capture_result = result
    investigation: dict[str, Any] | None = None
    if result == 0:
        from constructionsight.investigation_runtime import InvestigationRuntime

        runtime = None
        try:
            runtime = InvestigationRuntime(directory)
            investigation = runtime.process(
                max_jobs=25, poll_smarts=True, poll_inbox=True, startup=startup
            )
            if (
                investigation["failed_jobs"]
                or investigation.get("inbox_failed", 0)
                or investigation.get("smarts_failed", 0)
            ):
                result = 1
        except (ValueError, OSError, SQLAlchemyError):
            investigation = {"error_code": "investigation_processing_failed"}
            result = 1
        finally:
            if runtime is not None:
                runtime.close()
    if capture_result:
        runs = run_history(directory)
        error = str(runs[0].get("error") or "") if runs else ""
        if error.startswith("SmartsAccessDenied:") or (
            "HTTPStatusError" in error and "403" in error
        ):
            value.update(enabled=False, access_blocked="403 access denied; no automatic retry")
            write(directory, value)
            state.save_settings(directory, {"source_enabled": False})
    write(
        directory,
        {
            "at": now(),
            "outcome": "ok" if result == 0 else "error",
            "error": (
                None
                if result == 0
                else "Capture returned nonzero; inspect run history"
                if capture_result
                else "Capture retained; investigation processing failed; inspect worker job status"
            ),
            "capture_outcome": "ok" if capture_result == 0 else "error",
            "investigation": investigation,
        },
        "schedule-run.json",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    return run(args.data_dir) if args.run else 0


if __name__ == "__main__":
    raise SystemExit(main())
