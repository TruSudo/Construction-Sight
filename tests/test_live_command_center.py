from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from constructionsight import smarts_active
from constructionsight.live_command_center import make_server, projection
from constructionsight.security_fit import rank_leads
from constructionsight.smarts_api import RESOURCE_IDS, SmartsApiError, fetch_page
from constructionsight.smarts_evidence_ledger import (
    record_smarts_observation,
    verify_smarts_journal,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview


def row(i: int, county: str = "Riverside") -> dict[str, Any]:
    return {
        "_id": i,
        "SITE_COUNTY": county,
        "APP_ID": str(600000 + i),
        "WDID": "8 36C" + str(400000 + i),
        "STATUS": "Active",
        "SITE_NAME": "Warehouse",
        "DEVELOPER_NAME": "Builder",
        "CONSTRUCTION_COMMENCEMENT_DATE": "2026-10-01",
        "COMPLETE_PROJECT_DATE": "2027-01-01",
        "DEVELOPER_EMAIL": "private@example.test",
    }


def client_for(rosters: dict[str, list[dict[str, Any]]], fail: bool = False) -> httpx.Client:
    def respond(request: httpx.Request) -> httpx.Response:
        filters = json.loads(request.url.params["filters"])
        assert filters["STATUS"] == "Active"
        assert request.url.params["sort"] == "_id asc"
        records = rosters[filters["SITE_COUNTY"]]
        offset, limit = int(request.url.params["offset"]), int(request.url.params["limit"])
        if fail and filters["SITE_COUNTY"] == "Riverside":
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "resource_id": RESOURCE_IDS["facilities"],
                    "total": len(records),
                    "records": records[offset : offset + limit],
                    "fields": [{"id": name} for name in row(1)],
                },
            },
        )

    return httpx.Client(transport=httpx.MockTransport(respond))


def no_journal(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []

    def record(path: Path, page: Any) -> dict[str, Any]:
        receipts = {}
        for row in page.records:
            preview = build_smarts_intake_preview(page, row)
            if preview.source_record_key is None:
                continue
            calls.append(page)
            receipts[preview.record_sha256] = SimpleNamespace(
                source_record_key=preview.source_record_key,
                row_sha256=preview.record_sha256,
                response_sha256=page.response_sha256,
            )
        return receipts

    monkeypatch.setattr(smarts_active, "record_smarts_page", record)
    return calls


def test_beyond_500_baseline_diff_and_transport_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = no_journal(monkeypatch)
    rosters = {
        "San Bernardino": [row(i, "San Bernardino") for i in range(501)],
        "Riverside": [row(1000), row(1001)],
    }
    with client_for(rosters) as client:
        first = smarts_active.collect_active(client, tmp_path)
    assert len(first["rows"]) == 503 and first["requests"] == 7
    assert first["baseline"] and first["new_count"] == 0
    assert all(not r["is_new"] for r in first["rows"])
    assert len(calls) == 503
    rosters["Riverside"] = [row(1001), row(1002), {**row(1002), "_id": 9999}]
    with client_for(rosters) as client:
        second = smarts_active.collect_active(client, tmp_path)
    assert second["new_count"] == 1 and second["missing_count"] == 1
    assert second["duplicate_rows"] == 1
    assert [r["APP_ID"] for r in second["rows"] if r["is_new"]] == ["601002"]
    assert "DEVELOPER_EMAIL" not in second["rows"][0]
    with client_for(rosters) as client:
        replay = smarts_active.collect_active(client, tmp_path)
    assert replay["new_count"] == 0
    assert projection(replay)["kpis"]["new_week"] == 1


def test_failed_run_keeps_previous_complete_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_journal(monkeypatch)
    rosters = {"San Bernardino": [row(1, "San Bernardino")], "Riverside": [row(2)]}
    with client_for(rosters) as client:
        smarts_active.collect_active(client, tmp_path)
    original = (tmp_path / "active.json").read_bytes()
    with client_for(rosters, fail=True) as client, pytest.raises(SmartsApiError):
        smarts_active.collect_active(client, tmp_path)
    assert (tmp_path / "active.json").read_bytes() == original


def test_page_retained_with_multiple_rows_and_identical_duplicates(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    rosters = {"Riverside": [row(1), row(2), {**row(2), "_id": 44}]}
    with client_for(rosters) as client:
        page = fetch_page(client, county="Riverside", active_only=True, limit=100)
    journal = tmp_path / "journal.sqlite3"
    for record in page.records[:2]:
        record_smarts_observation(
            journal, page, build_smarts_intake_preview(page, record), paginated=True
        )
    assert verify_smarts_journal(journal)["sources"] == 2


def test_conflicting_source_fields_display_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_journal(monkeypatch)
    records = [row(1), {**row(1), "_id": 44, "SITE_NAME": "Different site"}]
    with client_for({"San Bernardino": [], "Riverside": records}) as client:
        result = smarts_active.collect_active(client, tmp_path)
    assert len(result["rows"]) == 1
    assert result["rows"][0]["SITE_NAME"] is None
    assert result["rows"][0]["conflicting_fields"] == ["SITE_NAME"]
    assert result["rows"][0]["source_variants"] == 2


def test_security_fit_dates_unknowns_and_repeat_developers() -> None:
    rows = [
        row(1),
        {**row(2), "SITE_NAME": "Retail hotel"},
        {
            **row(3),
            "SITE_NAME": "Unknown",
            "DEVELOPER_NAME": "NA",
            "CONSTRUCTION_COMMENCEMENT_DATE": "bad",
            "COMPLETE_PROJECT_DATE": None,
        },
        {**row(4), "COMPLETE_PROJECT_DATE": "2025-01-01"},
    ]
    ranked = rank_leads(rows, today=date(2026, 10, 13))
    by_id = {r["APP_ID"]: r for r in ranked}
    assert by_id["600001"]["security_fit"] == 80
    assert by_id["600003"]["security_fit"] == 5
    assert by_id["600004"]["stage"] == "Reported completion date passed"
    assert "Developer appears in 3" in by_id["600001"]["reason"]
    assert ranked[0]["security_fit"] >= ranked[-1]["security_fit"]


def test_local_http_real_row_projection_and_read_only_routes() -> None:
    snapshot = {
        "rows": [row(1)],
        "captured_at": "2026-10-13T09:00:00+00:00",
        "requests": 1,
        "totals": {"Riverside": 1, "San Bernardino": 0},
        "baseline": True,
        "missing_count": 0,
    }
    server = make_server(snapshot, 0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as c:
            assert c.get("/").status_code == 200
            assert c.get("/app.js").status_code == 200
            assert c.get("/api/leads").json()["kpis"]["total"] == 1
            assert c.post("/api/leads").status_code == 501
            assert c.get("/../../pyproject.toml").status_code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_rows_without_ids_are_counted_and_raw_page_is_retained(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    rosters = {
        "San Bernardino": [],
        "Riverside": [row(1), {**row(2), "WDID": "NA", "APP_ID": "NA"}],
    }
    with client_for(rosters) as client:
        result = smarts_active.collect_active(client, tmp_path)
    assert result["missing_identity_rows"] == 1
    assert len(result["rows"]) == 1
    assert result["duplicate_rows"] == 0
    assert verify_smarts_journal(tmp_path / "evidence.sqlite3")["sources"] == 1
