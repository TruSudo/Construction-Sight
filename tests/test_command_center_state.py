from __future__ import annotations

import io
import json
import threading
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from constructionsight import command_center_state as state
from constructionsight.lead_watchlist import update_watch, watchlist
from constructionsight.lead_workflow import begin_run, finish_run
from constructionsight.live_command_center import make_server, projection, readiness


def snapshot() -> dict[str, Any]:
    return {
        "rows": [
            {
                "source_key": "real-source:1",
                "SITE_NAME": "Warehouse",
                "SITE_CITY": "Riverside",
                "SITE_COUNTY": "Riverside",
                "WDID": "123",
                "APP_ID": "456",
                "is_new": True,
                "CONSTRUCTION_COMMENCEMENT_DATE": "2000-01-01",
                "COMPLETE_PROJECT_DATE": "2099-01-01",
            }
        ],
        "captured_at": "2026-10-14T12:00:00+00:00",
        "requests": 1,
        "totals": {"Riverside": 1, "San Bernardino": 0},
        "baseline": False,
        "missing_count": 0,
    }


def test_manual_provenance_readiness_and_source_change_separation(tmp_path: Path) -> None:
    source = snapshot()
    initial = projection(source, tmp_path)["rows"][0]
    update_watch(tmp_path, initial["source_key"], {"action": "save"}, initial)
    state.save_facts(
        tmp_path,
        initial["source_key"],
        {"value": "42000000.00", "size_sf": 325000, "site_verified": True},
    )
    state.save_contact(
        tmp_path,
        initial["source_key"],
        {
            "name": "Sourced person",
            "email": "person@example.test",
            "source": "Entered by user: company website",
        },
    )
    row = projection(source, tmp_path)["rows"][0]
    assert row["value"] == "42000000.00" and row["size_sf"] == 325000
    assert row["field_sources"]["value"]["source"] == "Entered by user"
    assert readiness(row) == "ready"
    assert not watchlist(tmp_path, [row])[0]["changed"]
    assert "value" not in source["rows"][0]


def test_queue_dnc_idempotence_and_reload(tmp_path: Path) -> None:
    row = projection(snapshot(), tmp_path)["rows"][0]
    state.queue(tmp_path, row)
    state.queue(tmp_path, row)
    row = projection(snapshot(), tmp_path)["rows"][0]
    assert row["outreach_queued"] and row["feedback"]["status"] == "Outreach queued"
    assert (
        len(
            [
                e
                for e in state.activity(tmp_path, row["source_key"])
                if e["kind"] == "outreach_queued"
            ]
        )
        == 1
    )
    state.control(tmp_path, row["source_key"], {"dnc": True})
    row = projection(snapshot(), tmp_path)["rows"][0]
    assert row["do_not_contact"] and not row["outreach_queued"]
    with pytest.raises(ValueError, match="Do-Not-Contact"):
        state.queue(tmp_path, row)


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "NaN"},
        {"value": "1.001"},
        {"size_sf": -1},
        {"SITE_LATITUDE": 100},
        {"SITE_LONGITUDE": "Infinity"},
        {"site_verified": "yes"},
        {"permit_date": "2026-02-30"},
    ],
)
def test_invalid_facts_are_atomic(tmp_path: Path, payload: dict[str, Any]) -> None:
    state.save_facts(tmp_path, "k", {"OWNER_NAME": "Original"})
    with pytest.raises(ValueError):
        state.save_facts(tmp_path, "k", {"OWNER_NAME": "Wrong", **payload})
    with state.connect(tmp_path) as db:
        assert (
            json.loads(db.execute("SELECT data FROM cc_facts").fetchone()[0])["OWNER_NAME"]["value"]
            == "Original"
        )


def test_settings_patch_preserves_profile_and_validation(tmp_path: Path) -> None:
    profile = {
        "name": "Actual operator",
        "role": "Owner",
        "company": "Actual company",
        "default_region": "",
    }
    state.save_settings(tmp_path, {"profile": profile})
    state.save_settings(tmp_path, {"map_view": {"center": [34, -117], "zoom": 10}})
    assert state.settings(tmp_path)["profile"] == profile
    with pytest.raises(ValueError):
        state.save_settings(tmp_path, {"profile": profile, "source_enabled": "true"})
    assert state.settings(tmp_path)["source_enabled"] is True


def test_notifications_read_backup_and_missing_evidence(tmp_path: Path) -> None:
    row = projection(snapshot(), tmp_path)["rows"][0]
    update_watch(tmp_path, row["source_key"], {"action": "save", "remind_on": "2000-01-01"}, row)
    run = begin_run(tmp_path)
    finish_run(tmp_path, run, None, "HTTP 403")
    notices = state.notifications(tmp_path, [row])
    assert len(notices) == 3
    state.mark_read(tmp_path, {"ids": [n["id"] for n in notices]})
    assert all(n["read"] for n in state.notifications(tmp_path, [row]))
    assert state.evidence(tmp_path, row, verify=True)["verified"] is False
    with zipfile.ZipFile(io.BytesIO(state.backup(tmp_path))) as archive:
        assert archive.read("workflow.sqlite3").startswith(b"SQLite format 3")


def test_same_origin_writes_and_restart(tmp_path: Path) -> None:
    def launch() -> tuple[Any, threading.Thread]:
        server = make_server(snapshot(), 0, tmp_path)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        return server, thread

    server, thread = launch()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, trust_env=False) as c:
            assert c.post("/api/facts/real-source%3A1", json={"value": "42"}).status_code == 403
            assert (
                c.post(
                    "/api/settings", json={"source_enabled": False}, headers={"Origin": base}
                ).status_code
                == 200
            )
            assert c.post("/api/capture", json={}, headers={"Origin": base}).status_code == 400
            assert (
                c.post(
                    "/api/facts/real-source%3A1", json={"value": "42"}, headers={"Origin": base}
                ).status_code
                == 200
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    server, thread = launch()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as c:
            assert c.get("/api/leads").json()["rows"][0]["value"] == "42"
            assert c.get("/api/settings").json()["source_enabled"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_verified_smarts_contact_import_is_bound_to_original_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from constructionsight.smarts_active import collect_active
    from tests.test_live_command_center import client_for, row

    record = {
        **row(1),
        "DEVELOPER_CONTACT_FIRST_NAME": "Source",
        "DEVELOPER_CONTACT_LAST_NAME": "Person",
        "DEVELOPER_PHONE": "9515550101",
        "SITE_EMAIL": "NA",
        "SITE_PHONE": "0",
    }
    from tests import test_live_command_center as legacy

    monkeypatch.setattr(legacy, "row", lambda i: record)
    with client_for({"San Bernardino": [], "Riverside": [record]}) as client:
        captured = collect_active(client, tmp_path)
    lead = projection(captured, tmp_path)["rows"][0]
    result = state.import_smarts_contacts(tmp_path, lead)
    assert len(result["contacts"]) == 1
    imported = result["contacts"][0]
    assert imported["email"] == "private@example.test" and imported["name"] == "Source Person"
    assert lead["response_sha256"] in imported["source"]
    state.import_smarts_contacts(tmp_path, lead)
    assert len(projection(captured, tmp_path)["rows"][0]["sourced_contacts"]) == 1
    with pytest.raises(ValueError):
        state.import_smarts_contacts(tmp_path, {**lead, "response_sha256": "0" * 64})


def test_upload_photo_keeps_original_bytes_and_source(tmp_path: Path) -> None:
    import base64

    from PIL import Image

    image = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(image, format="PNG")
    state.save_photo(
        tmp_path,
        "real-source:1",
        {
            "data": base64.b64encode(image.getvalue()).decode(),
            "source": "Entered by user: owned photograph",
        },
    )
    assert projection(snapshot(), tmp_path)["rows"][0]["photo"] is True
    with state.connect(tmp_path) as db:
        stored = db.execute("SELECT * FROM cc_photos").fetchone()
        assert stored["data"] == image.getvalue() and "owned photograph" in stored["source"]


def test_deltas_need_history_and_use_region_matched_real_snapshots(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta

    current = snapshot()
    rows = projection(current, tmp_path)["rows"]
    assert state.deltas(tmp_path, rows)["Riverside"]["total"] is None
    old = snapshot()
    old["captured_at"] = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    run = begin_run(tmp_path)
    finish_run(tmp_path, run, old)
    with state.connect(tmp_path) as db:
        db.execute("UPDATE runs SET finished_at=? WHERE id=?", (old["captured_at"], run))
    current["rows"].append({**current["rows"][0], "source_key": "real-source:2"})
    result = state.deltas(tmp_path, projection(current, tmp_path)["rows"])
    assert result["Riverside"]["total"] == 100.0 and result["Riverside"]["new"] is None


def test_exclusion_words_do_not_match_inside_unrelated_names(tmp_path: Path) -> None:
    from constructionsight.security_fit import rank_leads

    rows = rank_leads(
        [
            {"SITE_NAME": "Broadway Warehouse", "source_key": "a"},
            {"SITE_NAME": "Industrial Pipeline Replacement", "source_key": "b"},
            {"SITE_NAME": "Solar Facility", "source_key": "c"},
        ]
    )
    types = {r["source_key"]: r["project_type"] for r in rows}
    assert types == {"a": "industrial", "b": "infrastructure", "c": "infrastructure"}
    assert all(
        r["field_sources"]["project_type"]["source"] == "Name-based classifier; type unverified"
        for r in rows
    )
