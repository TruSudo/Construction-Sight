"""Existing source-watch changes reach the native inbox without commercial effects."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest

from constructionsight.command_center_legacy_reconciliation import (
    enqueue_legacy_reconciliation,
)
from constructionsight.investigation_runtime import InvestigationRuntime
from tests.test_native_original_source_revisions import _body, _changed, _setup, _store_original
from tests.test_native_source_inspection import _native


@pytest.mark.parametrize("kind", ["ceqa", "permit"])
def test_source_change_notice_preserves_review_boundary_and_read_state_after_restart(
    tmp_path: Path, kind: str,
) -> None:
    original, directory, record, identity, _ = _setup(tmp_path, kind)
    notice_id = None
    for turn in range(2):
        server, thread = _native(directory, original)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with httpx.Client(base_url=base, trust_env=False) as client:
                selector = {"kind": kind, "record_id": identity}
                if turn == 0:
                    assert client.post(
                        "/api/source-watchlist-action", json={"action": "add", **selector},
                    ).status_code == 403
                    created = client.post(
                        "/api/source-watchlist-action", json={"action": "add", **selector},
                        headers={"Origin": base},
                    )
                    assert created.status_code == 200, created.text
                    assert not [n for n in client.get("/api/notifications").json()
                                if n.get("record_id") == identity]
                    prior = client.get("/api/source-reconciliation", params=selector).json()
                    changed = _changed(record)
                    _store_original(original, changed)
                    before = original.read_bytes()
                    notices = client.get("/api/notifications").json()
                    matching = [n for n in notices if n.get("record_id") == identity]
                    assert len(matching) == 1
                    notice = matching[0]
                    notice_id = notice["id"]
                    assert notice["read"] is False
                    assert notice["source_claim_only"] is True
                    assert notice["record_kind"] == kind
                    assert "source_key" not in notice
                    assert notice["county"] == "Riverside"
                    assert client.get("/api/notifications").json() == notices
                    assert original.read_bytes() == before
                    review = client.get("/api/source-reconciliation", params=selector).json()
                    assert review["native_evidence_id"] == prior["native_evidence_id"]
                    assert review["revision_replay_eligible"] is True
                    # Notification inspection/read is never a revision approval.
                    marked = client.post(
                        "/api/notifications/read", json={"ids": [notice_id]},
                        headers={"Origin": base},
                    )
                    assert marked.status_code == 200
                    assert client.get(
                        "/api/source-reconciliation", params=selector,
                    ).json() == review
                    enqueue_legacy_reconciliation(directory, original, _body(review, revision=True))
                    runtime = InvestigationRuntime(directory)
                    try:
                        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
                    finally:
                        runtime.close()
                    updated = client.get("/api/source-reconciliation", params=selector).json()
                    assert updated["canonical_investigation_id"] == prior[
                        "canonical_investigation_id"
                    ]
                    assert updated["native_evidence_id"] != prior["native_evidence_id"]
                    assert original.read_bytes() == before
                else:
                    notices = client.get("/api/notifications").json()
                    matching = [n for n in notices if n.get("record_id") == identity]
                    assert len(matching) == 1
                    assert matching[0]["id"] == notice_id
                    assert matching[0]["read"] is True
                    # Archive removes the current attention item, preserving the source history.
                    archived = client.post(
                        "/api/source-watchlist-action", json={"action": "archive", **selector},
                        headers={"Origin": base},
                    )
                    assert archived.status_code == 200, archived.text
                    assert not [n for n in client.get("/api/notifications").json()
                                if n.get("record_id") == identity]
                    rearmed = client.post(
                        "/api/source-watchlist-action", json={"action": "add", **selector},
                        headers={"Origin": base},
                    )
                    assert rearmed.status_code == 200
                    assert not [n for n in client.get("/api/notifications").json()
                                if n.get("record_id") == identity]
                    _store_original(original, _changed(record, days=2))
                    latest = [n for n in client.get("/api/notifications").json()
                              if n.get("record_id") == identity]
                    assert len(latest) == 1
                    assert latest[0]["id"] != notice_id
                    assert latest[0]["read"] is False
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


def test_corrupt_original_watch_does_not_hide_native_notices_or_mutate_original(
    tmp_path: Path,
) -> None:
    original, directory, _, identity, _ = _setup(tmp_path)
    server, thread = _native(directory, original)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.post(
                "/api/source-watchlist-action",
                json={"action": "add", "kind": "ceqa", "record_id": identity},
                headers={"Origin": base},
            ).status_code == 200
            with sqlite3.connect(original) as db:
                db.execute("UPDATE intelligence_watchlist_items SET target_id='wrong'")
            before = original.read_bytes()
            response = client.get("/api/notifications")
            assert response.status_code == 200, response.text
            assert any(n["id"] == "source-watch:unavailable" for n in response.json())
            assert not any(n.get("record_id") == identity for n in response.json())
            assert original.read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
