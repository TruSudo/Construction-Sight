"""Writable, isolated Demo server for functional tests; never captures network data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from constructionsight.command_center_state import save_settings
from constructionsight.lead_watchlist import update_watch
from constructionsight.live_command_center import make_server, projection

parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--port", type=int, default=8766)
parser.add_argument("--real-fixture", action="store_true")
parser.add_argument("--local-map-fixture", action="store_true")
parser.add_argument("--schedule-fixture", action="store_true")
args = parser.parse_args()
if args.real_fixture:
    snapshot = json.loads((Path(__file__).parents[1] / "visual/real-capture.json").read_text())
else:
    snapshot = json.loads((Path(__file__).parents[1] / "visual/parity.json").read_text())
    snapshot.pop("parity_watches", None)
    for row in snapshot["rows"]:
        row.pop("parity_view", None)
        row["SITE_NAME"] = "Demo Warehouse " + str(row["APP_ID"])
        row["DEVELOPER_NAME"] = "Demo sourced developer"
        row["CONSTRUCTION_COMMENCEMENT_DATE"] = "2000-01-01"
        row["COMPLETE_PROJECT_DATE"] = "2099-01-01"
        for key in (
            "project_id",
            "project_type",
            "size_sf",
            "value",
            "architect",
            "contractor",
            "permit_date",
        ):
            row.pop(key, None)
save_settings(args.data_dir, {"source_enabled": False})
if not args.real_fixture:
    row = projection(snapshot, args.data_dir)["rows"][0]
    update_watch(
        args.data_dir,
        row["source_key"],
        {"action": "save", "note": "Demo follow-up", "remind_on": "2000-01-01"},
        row,
    )
if args.local_map_fixture:
    from constructionsight.data_folder import digest
    from constructionsight.offline_map import build

    extract = Path(__file__).parents[1] / "visual/offline-map-fixture.osm"
    build(
        extract,
        args.data_dir / "basemap.pmtiles",
        expected_sha256=digest(extract),
        max_zoom=8,
        source_url="Demo fixture",
    )
if args.schedule_fixture:
    import subprocess

    from constructionsight import collection_schedule as schedule

    active = False

    def manager(*command: str) -> subprocess.CompletedProcess[str]:
        global active
        if command[0] == "restart":
            active = True
        elif command[0] == "disable":
            active = False
        value = schedule.config(args.data_dir)
        output = (
            "ActiveState=" + ("active" if active else "inactive") + "\nResult=success\n"
            "UnitFileState=enabled\nNextElapseUSecRealtime=Demo fixture next run: "
            f"2026-10-15 {value['hour']:02d}:{value['minute']:02d} {value['timezone']}\n"
        )
        return subprocess.CompletedProcess(command, 0, output, "")

    schedule.systemctl = manager
    original_install = schedule.install

    def fixture_install(directory: Path, startup: Path, payload: dict) -> dict:
        return original_install(directory, startup, payload, unit_directory=args.data_dir / "units")

    schedule.install = fixture_install
    schedule.write(
        args.data_dir,
        {"at": "2026-10-14", "outcome": "error", "error": "Demo scheduled capture failure"},
        "schedule-run.json",
    )
server = make_server(snapshot, args.port, args.data_dir)
print(
    "Retained real-data structure server" if args.real_fixture else "Writable isolated Demo server",
    server.server_port,
    flush=True,
)
try:
    server.serve_forever()
finally:
    server.server_close()
