from __future__ import annotations

import csv
import io
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from constructionsight.lead_workflow import (
    begin_run,
    capture_lock,
    csv_export,
    developer_accounts,
    finish_run,
    get_feedback,
    outcome_report,
    run_history,
    save_feedback,
)
from constructionsight.live_command_center import make_server
from constructionsight.security_fit import load_weights, rank_leads


def snapshot() -> dict:
    return {
        "rows": [
            {
                "source_key": "demo:1",
                "SITE_NAME": "Demo warehouse",
                "SITE_CITY": "Demo",
                "SITE_COUNTY": "Riverside",
                "WDID": "Demo",
                "APP_ID": "Demo",
                "DEVELOPER_NAME": "Demo, LLC",
                "OWNER_NAME": None,
                "CONSTRUCTION_COMMENCEMENT_DATE": "2026-10-01",
                "is_new": True,
                "first_seen": datetime.now(UTC).isoformat(),
            }
        ],
        "captured_at": datetime.now(UTC).isoformat(),
        "requests": 0,
        "totals": {"Riverside": 1, "San Bernardino": 0},
        "baseline": False,
        "new_count": 1,
        "missing_count": 0,
        "demo": True,
    }


def test_feedback_reason_validation_and_restart(tmp_path: Path) -> None:
    lead = rank_leads(snapshot()["rows"])[0]
    with pytest.raises(ValueError, match="reason"):
        save_feedback(tmp_path, "demo:1", {"status": "Lost"}, lead)
    with pytest.raises(ValueError, match="date"):
        save_feedback(
            tmp_path, "demo:1", {"status": "Contacted", "last_contacted": "2026-02-30"}, lead
        )
    saved = save_feedback(
        tmp_path,
        "demo:1",
        {
            "status": "Not a fit",
            "reason_code": "Timing",
            "reason_text": "Demo reason",
            "notes": "Demo note",
        },
        lead,
    )
    assert saved == get_feedback(tmp_path)["demo:1"]
    assert saved["last_contacted"] is None
    assert saved["reason_text"] == "Demo reason"
    assert saved["score_at_update"] == lead["security_fit"]
    edited = save_feedback(
        tmp_path,
        "demo:1",
        {"status": "Not a fit", "reason_code": "Timing", "notes": "Demo note edited"},
        {**lead, "security_fit": 5},
    )
    assert edited["score_at_update"] == saved["score_at_update"]


def test_run_history_failure_and_interrupted_capture(tmp_path: Path) -> None:
    run = begin_run(tmp_path)
    finish_run(tmp_path, run, snapshot())
    interrupted = begin_run(tmp_path)
    next_run = begin_run(tmp_path)
    finish_run(tmp_path, next_run, None, "Demo transport error")
    history = run_history(tmp_path)
    assert history[0]["outcome"] == "error"
    assert history[0]["error"] == "Demo transport error"
    assert history[1]["id"] == interrupted and history[1]["error"] == "Interrupted capture"
    assert history[2]["rows"] == 1 and history[2]["new_count"] == 1
    with capture_lock(tmp_path), pytest.raises(BlockingIOError), capture_lock(tmp_path):
        pass


def test_developer_accounts_exact_normalization_owner_fallback() -> None:
    rows = snapshot()["rows"] + [
        {
            **snapshot()["rows"][0],
            "source_key": "demo:2",
            "DEVELOPER_NAME": " demo LLC ",
            "SITE_COUNTY": "San Bernardino",
            "CONSTRUCTION_COMMENCEMENT_DATE": "2025-03-02",
        },
        {
            **snapshot()["rows"][0],
            "source_key": "demo:3",
            "DEVELOPER_NAME": "NA",
            "OWNER_NAME": "Other Demo",
        },
    ]
    accounts = developer_accounts(rows)
    assert accounts[0]["active_sites"] == 2
    assert accounts[0]["earliest_start"] == "2025-03-02"
    assert accounts[0]["counties"] == ["Riverside", "San Bernardino"]
    assert accounts[1]["name"] == "Other Demo"


def test_weights_outcomes_and_csv_are_real_not_inferred(tmp_path: Path) -> None:
    weights = load_weights()
    weights["industrial"] = 0
    file = tmp_path / "weights.json"
    file.write_text(json.dumps(weights))
    assert rank_leads(snapshot()["rows"], weights=load_weights(file))[0]["security_fit"] == 30
    file.write_text('{"industrial": -5}')
    with pytest.raises(ValueError):
        load_weights(file)
    rows = [
        dict(
            rank_leads(snapshot()["rows"])[0],
            feedback={
                "status": "Won",
                "score_at_update": 10,
                "project_type_at_update": "commercial",
            },
        )
    ]
    report = outcome_report(rows)
    assert report[0]["win_rate"] == 1 and report[0]["score_band"] == "0–29"
    exported = list(
        csv.DictReader(
            io.StringIO(
                csv_export([{**rows[0], "SITE_NAME": "=Demo()", "security_fit": 0}]).decode(
                    "utf-8-sig"
                )
            )
        )
    )
    assert exported[0]["SITE_NAME"] == "'=Demo()"
    assert exported[0]["security_fit"] == "0"


def test_http_workflow_export_warning_and_outcome_restart(tmp_path: Path) -> None:
    data = snapshot()
    (tmp_path / "active.json").write_text(json.dumps(data))
    failed = begin_run(tmp_path)
    finish_run(tmp_path, failed, None, "Demo capture failure")
    server = make_server(data, 0, tmp_path)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=url, trust_env=False) as c:
            assert c.get("/icons.js").status_code == 200
            assert c.get("/api/leads", headers={"Host": "external.example"}).status_code == 403
            assert len(c.get("/api/terms").json()) == 3
            rows = c.get("/api/leads").json()
            assert "last good" in rows["warning"] and rows["rows"][0]["new_today"]
            payload = {"status": "Won", "notes": "Demo outcome"}
            assert c.post("/api/feedback/demo%3A1", json=payload).status_code == 403
            assert (
                c.post("/api/feedback/demo%3A1", json=payload, headers={"Origin": url}).status_code
                == 200
            )
            assert c.get("/api/leads").json()["rows"][0]["feedback"]["status"] == "Won"
            assert c.get("/api/developers").json()[0]["active_sites"] == 1
            assert c.get("/api/outcomes").json()[0]["won"] == 1
            assert "Demo outcome" in c.get("/api/export.csv?status=Won&new_today=1").text
            assert "Demo outcome" not in c.get("/api/export.csv?status=Lost").text
            (tmp_path / "active.json").write_text(json.dumps({**data, "rows": []}))
            assert c.get("/api/outcomes").json()[0]["won"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_capture_failure_keeps_last_good_file_and_records_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from constructionsight import live_command_center
    from constructionsight.smarts_api import SmartsApiError

    original = json.dumps(snapshot()).encode()
    (tmp_path / "active.json").write_bytes(original)

    def fail(client: httpx.Client, directory: Path) -> dict:
        raise SmartsApiError("Demo failed transport")

    monkeypatch.setattr(live_command_center, "collect_active", fail)
    assert live_command_center.main(["--capture-only", "--data-dir", str(tmp_path)]) == 1
    assert (tmp_path / "active.json").read_bytes() == original
    assert "Demo failed transport" in run_history(tmp_path)[0]["error"]
