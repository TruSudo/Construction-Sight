"""Parity isolation, truthful readiness, and persistent local queue regressions."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.live_command_center import make_server, projection, readiness

FIXTURE = Path(__file__).parent / "visual/parity.json"


def test_parity_is_explicit_demo_and_isolated(tmp_path: Path) -> None:
    snapshot = json.loads(FIXTURE.read_text())
    normal = projection(snapshot)
    assert not normal["mockup_parity"]
    assert normal["parity_watches"] == []
    assert all(r["readiness"] != "ready" for r in normal["rows"])
    parity = projection(snapshot, parity=True)
    assert parity["demo"] and len(parity["rows"]) == 247
    assert sum(r["readiness"] == "ready" for r in parity["rows"]) == 86
    assert sum(r["readiness"] == "review" for r in parity["rows"]) == 104
    assert sum(r["readiness"] == "not_ready" for r in parity["rows"]) == 57
    assert sum(r["new_week"] for r in parity["rows"]) == 28
    assert len(parity["parity_watches"]) == 4
    with pytest.raises(ValueError, match="isolated"):
        projection(snapshot, tmp_path, parity=True)
    with pytest.raises(ValueError, match="isolated"):
        projection({**snapshot, "demo": False}, parity=True)


def test_high_fit_is_never_outreach_readiness_on_its_own() -> None:
    row = {"fit_band": "high", "project_type": "industrial"}
    assert readiness(row) == "review"
    row["site_verification"] = {"verified": True, "source": "Entered by user"}
    assert readiness(row) == "review"
    row["sourced_contacts"] = [{"email": "fixture@example.test"}]
    assert readiness(row) == "review"
    row["sourced_contacts"][0]["source"] = "Test evidence"
    assert readiness(row) == "ready"
    assert readiness({**row, "conflicting_fields": ["SITE_NAME"]}) == "review"
    assert readiness({**row, "do_not_contact": True}) == "not_ready"
    assert readiness({**row, "project_type": "infrastructure"}) == "not_ready"


def test_local_outreach_queue_persists_and_no_parity_photo_in_normal_mode(tmp_path: Path) -> None:
    snapshot = json.loads(FIXTURE.read_text())
    snapshot["demo"] = False
    snapshot["rows"] = [snapshot["rows"][0]]
    server = make_server(snapshot, 0, tmp_path)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as c:
            assert (
                c.get("/fonts/roboto-latin-400-normal.woff2").headers["content-type"]
                == "font/woff2"
            )
            assert c.get("/parity-photo.png").status_code == 404
            assert c.get("/demo.json").status_code == 404
            assert c.post("/api/outreach/demo%3A1", json={}).status_code == 403
            assert c.post("/api/outreach/demo%3A1", json={}, headers={"Origin": base}).json()[
                "queued"
            ]
            assert c.post("/api/outreach/demo%3A1", json={}, headers={"Origin": base}).json()[
                "queued"
            ]
            assert len(c.get("/api/outreach").json()) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    restarted = make_server(snapshot, 0, tmp_path)
    thread = threading.Thread(target=restarted.serve_forever)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{restarted.server_port}", trust_env=False
        ) as c:
            assert len(c.get("/api/outreach").json()) == 1
    finally:
        restarted.shutdown()
        restarted.server_close()
        thread.join()
