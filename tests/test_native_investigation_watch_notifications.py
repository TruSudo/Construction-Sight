"""Phase 8 canonical investigation watch uses committed state and existing inbox."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import httpx

from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_command_center_live_graph import _ingest


def _server(directory: Path) -> tuple[object, threading.Thread]:
    server = make_server(snapshot(), 0, directory=directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_watched_investigation_change_notifies_only_own_record_and_survives_restart(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    _ingest(directory)
    original = (directory / "investigations.sqlite3").read_bytes()
    identity = None
    notification_id = None
    for iteration in (0, 1):
        server, thread = _server(directory)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with httpx.Client(base_url=base, trust_env=False) as client:
                if iteration == 0:
                    rows = client.get("/api/investigations").json()["rows"]
                    identity = rows[0]["investigation_id"]
                    selected = {"investigation_id": identity}
                    before = client.get("/api/investigation-watch", params=selected).json()
                    assert before["watched"] is False
                    assert client.get("/api/investigation-watch?investigation_id=a&x=1"
                                      ).status_code == 409
                    payload = {"action": "watch", **selected,
                               "expected_digest": before["current_digest"]}
                    assert client.post("/api/investigation-watch", json=payload).status_code == 403
                    assert client.post(
                        "/api/investigation-watch", json=payload,
                        headers={"Origin": "https://untrusted.example"},
                    ).status_code == 403
                    watched = client.post(
                        "/api/investigation-watch", json=payload, headers={"Origin": base},
                    )
                    assert watched.status_code == 200, watched.text
                    assert watched.json()["watched"] is True
                    assert watched.json()["changed"] is False
                    listing = client.get("/api/investigation-watches")
                    assert listing.status_code == 200, listing.text
                    assert len(listing.json()) == 1
                    assert listing.json()[0]["investigation_id"] == identity
                    assert listing.json()[0]["changed"] is False
                    assert client.get("/api/investigation-watches?extra=1").status_code == 409
                    assert client.post(
                        "/api/investigation-watch", json=payload, headers={"Origin": base}
                    ).status_code == 400
                    assert not [n for n in client.get("/api/notifications").json()
                                if n.get("investigation_id") == identity]
                    assert (directory / "investigations.sqlite3").read_bytes() == original
                    _ingest(directory, "Revised watched canonical investigation")
                    notice = [n for n in client.get("/api/notifications").json()
                              if n.get("investigation_id") == identity]
                    assert len(notice) == 1
                    assert notice[0]["source_claim_only"] is True
                    assert notice[0]["read"] is False
                    assert client.get("/api/investigation-watches").json()[0]["changed"] is True
                    notification_id = notice[0]["id"]
                    assert client.post(
                        "/api/investigation-watch",
                        json={**payload, "action": "acknowledge"},
                        headers={"Origin": base},
                    ).status_code == 400
                    assert client.post("/api/notifications/read",
                                       json={"ids": [notification_id]},
                                       headers={"Origin": base}).status_code == 200
                    assert client.get("/api/investigation-watch", params=selected
                                      ).json()["changed"] is True
                else:
                    assert identity is not None
                    selected = {"investigation_id": identity}
                    notices = [n for n in client.get("/api/notifications").json()
                               if n.get("investigation_id") == identity]
                    assert len(notices) == 1
                    assert notices[0]["id"] == notification_id
                    assert notices[0]["read"] is True
                    state = client.get("/api/investigation-watch", params=selected).json()
                    assert state["changed"] is True
                    ack = client.post(
                        "/api/investigation-watch",
                        json={"action": "acknowledge", **selected,
                              "expected_digest": state["current_digest"]},
                        headers={"Origin": base},
                    )
                    assert ack.status_code == 200, ack.text
                    assert ack.json()["changed"] is False
                    assert not [n for n in client.get("/api/notifications").json()
                                if n.get("investigation_id") == identity]
                    _ingest(directory, "Second watched canonical revision")
                    latest = [n for n in client.get("/api/notifications").json()
                              if n.get("investigation_id") == identity]
                    assert len(latest) == 1
                    assert latest[0]["id"] != notification_id
                    assert latest[0]["read"] is False
                    current = client.get("/api/investigation-watch", params=selected).json()
                    assert client.post(
                        "/api/investigation-watch",
                        json={"action": "remove", **selected,
                              "expected_digest": current["current_digest"]},
                        headers={"Origin": base},
                    ).status_code == 200
                    assert not [n for n in client.get("/api/notifications").json()
                                if n.get("investigation_id") == identity]
                    assert not client.get("/api/investigation-watch", params=selected
                                         ).json()["watched"]
                    assert client.get("/api/investigation-watches").json() == []
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    assert identity is not None
    assert hashlib.sha256((directory / "investigations.sqlite3").read_bytes()).hexdigest()
    assert not (directory / "original-ceqanet-exports").exists()


def test_unavailable_investigation_watch_keeps_existing_inbox(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    _ingest(directory)
    server, thread = _server(directory)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            identity = client.get("/api/investigations").json()["rows"][0]["investigation_id"]
            status = client.get("/api/investigation-watch",
                                params={"investigation_id": identity}).json()
            result = client.post("/api/investigation-watch",
                                 json={"action": "watch", "investigation_id": identity,
                                       "expected_digest": status["current_digest"]},
                                 headers={"Origin": base})
            assert result.status_code == 200, result.text
            original = directory / "investigations.sqlite3"
            moved = tmp_path / "original.sqlite3"
            original.replace(moved)
            original.symlink_to(moved)
            assert client.get("/api/investigation-watch",
                              params={"investigation_id": identity}).status_code == 409
            notices = client.get("/api/notifications")
            assert notices.status_code == 200, notices.text
            assert any(n["id"].startswith("investigation-watch:unavailable:")
                       for n in notices.json())
            assert moved.is_file()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
