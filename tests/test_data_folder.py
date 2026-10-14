from __future__ import annotations

import io
import json
import threading
import zipfile
from pathlib import Path

import httpx
import pytest

from constructionsight import command_center_state as state
from constructionsight import data_folder as folders
from constructionsight.live_command_center import ASSETS, make_server


def test_verified_restore_relocation_and_restart(tmp_path: Path) -> None:
    original = tmp_path / "original"
    snapshot = json.loads((ASSETS / "demo.json").read_text())
    server = make_server(snapshot, 0, original)
    (original / "active.json").write_text(json.dumps(snapshot))
    nested = original / "parcel-evidence"
    nested.mkdir()
    (nested / "response.json").write_text('{"source":"retained bytes"}')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, headers={"Origin": base}) as client:
            before = client.get("/api/settings").json()["profile"]
            backup = client.get("/api/backup.zip").content
            assert client.post("/api/restore-apply", json={"token": "unknown"}).status_code == 400
            assert (
                client.post(
                    "/api/settings", json={"profile": {**before, "name": "Later"}}
                ).status_code
                == 200
            )
            preview = client.post("/api/restore-preview", content=backup)
            assert preview.status_code == 200, preview.text
            report = preview.json()
            assert report["dry_run"] and report["sqlite_integrity"]
            assert client.get("/api/settings").json()["profile"]["name"] == "Later"
            applied = client.post("/api/restore-apply", json={"token": report["archive_sha256"]})
            assert applied.status_code == 200, applied.text
            restored = Path(applied.json()["directory"])
            assert client.get("/api/settings").json()["profile"] == before
            assert (restored / "parcel-evidence/response.json").read_bytes() == (
                nested / "response.json"
            ).read_bytes()
            assert state.settings(original)["profile"]["name"] == "Later"
            moved = tmp_path / "relocated"
            result = client.post("/api/data-folder", json={"directory": str(moved)})
            assert result.status_code == 200, result.text
            assert folders.resolve_folder(original) == moved
            assert restored.exists() and original.exists()
            restart = make_server(snapshot, 0, original)
            restart.server_close()
            assert state.settings(moved)["profile"] == before
            assert (
                client.post(
                    "/api/data-folder", json={"directory": str(moved / "nested/../child")}
                ).status_code
                == 400
            )
            occupied = tmp_path / "occupied"
            occupied.mkdir()
            (occupied / "keep").write_text("preserve")
            assert (
                client.post("/api/data-folder", json={"directory": str(occupied)}).status_code
                == 400
            )
            assert (occupied / "keep").read_text() == "preserve"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_backup_rejects_corruption_and_traversal(tmp_path: Path) -> None:
    directory = tmp_path / "data"
    directory.mkdir()
    (directory / "active.json").write_text('{"rows":[]}')
    backup = folders.make_backup(directory)
    original = zipfile.ZipFile(io.BytesIO(backup))
    for name, content in [("active.json", b'{"rows":[1]}'), ("../escape.json", b"{}")]:
        archive = tmp_path / (name.replace("/", "_") + ".zip")
        with zipfile.ZipFile(archive, "w") as modified:
            for item in original.infolist():
                modified.writestr(
                    item.filename, content if item.filename == name else original.read(item)
                )
            if name.startswith(".."):
                modified.writestr(name, content)
        with pytest.raises(ValueError):
            folders.preview_restore(archive, tmp_path / ("stage" + archive.stem))
    assert (directory / "active.json").read_text() == '{"rows":[]}'
