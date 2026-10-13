from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.lead_watchlist import update_watch, watchlist
from constructionsight.live_command_center import make_server


def row() -> dict:
    return {
        "source_key": "demo:watch",
        "SITE_NAME": "Demo warehouse",
        "SITE_COUNTY": "Riverside",
        "APP_ID": "Demo",
        "WDID": "Demo",
        "row_sha256": "initial",
        "DEVELOPER_EMAIL": "excluded@example.test",
    }


def test_watch_restart_dates_and_private_field_exclusion(tmp_path: Path) -> None:
    update_watch(
        tmp_path,
        "demo:watch",
        {"action": "save", "note": "Demo reminder", "remind_on": "2000-01-01"},
        row(),
    )
    item = watchlist(tmp_path, [row()])[0]
    assert item["note"] == "Demo reminder" and item["due"] and not item["changed"]
    assert "DEVELOPER_EMAIL" not in item["row"]
    assert not watchlist(tmp_path, [{**row(), "response_sha256": "different page"}])[0]["changed"]
    assert not watchlist(tmp_path, [{**row(), "security_fit": 999}])[0]["changed"]


def test_change_alert_survives_note_edit_until_acknowledged(tmp_path: Path) -> None:
    update_watch(tmp_path, "demo:watch", {"action": "save"}, row())
    changed = {**row(), "row_sha256": "next", "SITE_NAME": "Demo updated"}
    assert watchlist(tmp_path, [changed])[0]["changed"]
    update_watch(tmp_path, "demo:watch", {"action": "save", "note": "Edited"}, changed)
    assert watchlist(tmp_path, [changed])[0]["changed"]
    update_watch(tmp_path, "demo:watch", {"action": "acknowledge"}, changed)
    assert not watchlist(tmp_path, [changed])[0]["changed"]
    assert watchlist(tmp_path, [changed])[0]["note"] == "Edited"


def test_missing_watch_remains_editable_and_reappearance_alerts(tmp_path: Path) -> None:
    update_watch(tmp_path, "demo:watch", {"action": "save"}, row())
    missing = watchlist(tmp_path, [])[0]
    assert missing["changed"] and not missing["present"]
    assert "not a deletion" in missing["source_state"]
    assert missing["row"]["SITE_NAME"] == "Demo warehouse"
    update_watch(tmp_path, "demo:watch", {"action": "save", "note": "Still watching"}, None)
    assert watchlist(tmp_path, [])[0]["changed"]
    update_watch(tmp_path, "demo:watch", {"action": "acknowledge"}, None)
    assert not watchlist(tmp_path, [])[0]["changed"]
    assert watchlist(tmp_path, [row()])[0]["changed"]
    update_watch(tmp_path, "demo:watch", {"action": "remove"}, None)
    assert watchlist(tmp_path, []) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "save", "remind_on": "2026-02-30"},
        {"action": "save", "remind_on": "tomorrow"},
        {"action": "save", "note": []},
        {"action": "save", "note": "a" * 2001},
        {"action": "save", "ready_for_outreach": True},
        {"action": "send"},
    ],
)
def test_invalid_watch_does_not_replace_saved_reminder(tmp_path: Path, payload: dict) -> None:
    update_watch(tmp_path, "demo:watch", {"action": "save", "note": "Keep"}, row())
    with pytest.raises(ValueError):
        update_watch(tmp_path, "demo:watch", payload, row())
    assert watchlist(tmp_path, [row()])[0]["note"] == "Keep"


def test_http_watch_guards_restart_and_missing_record_review(tmp_path: Path) -> None:
    data = {
        "rows": [row()],
        "captured_at": "2026-10-13T09:00:00+00:00",
        "requests": 0,
        "totals": {"Riverside": 1, "San Bernardino": 0},
        "baseline": True,
        "missing_count": 0,
        "demo": True,
    }
    path = tmp_path / "active.json"
    path.write_text(json.dumps(data))
    server = make_server(data, 0, tmp_path)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=url, trust_env=False) as client:
            endpoint = "/api/watchlist/demo%3Awatch"
            assert client.post(endpoint, json={"action": "save"}).status_code == 403
            headers = {"Origin": url}
            assert (
                client.post(endpoint, json={"action": "save"}, headers=headers).status_code == 200
            )
            assert (
                client.post(
                    "/api/watchlist/unknown", json={"action": "save"}, headers=headers
                ).status_code
                == 400
            )
            assert client.get("/api/watchlist").json()[0]["present"]
            path.write_text(json.dumps({**data, "rows": []}))
            assert client.get("/api/watchlist").json()[0]["changed"]
            assert (
                client.post(endpoint, json={"action": "acknowledge"}, headers=headers).status_code
                == 200
            )
            assert not client.get("/api/watchlist").json()[0]["changed"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert len(watchlist(tmp_path, [])) == 1
