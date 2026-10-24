"""Original source watches and canonical watches converge in one native inbox.

Both use their existing durable stores. The original source change triggers before
the independent worker reviews the revision; after the worker commits, a canonical
watch triggers without duplicating either notice or approving any commercial act.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from constructionsight.command_center_legacy_reconciliation import (
    enqueue_legacy_reconciliation,
)
from constructionsight.investigation_runtime import InvestigationRuntime
from tests.test_native_original_source_revisions import (
    _body,
    _changed,
    _setup,
    _store_original,
)
from tests.test_native_source_inspection import _native


@pytest.mark.parametrize("kind", ["ceqa", "permit"])
def test_reviewed_original_revision_converges_both_durable_watches_after_restart(
    tmp_path: Path, kind: str,
) -> None:
    original, directory, record, original_id, _ = _setup(tmp_path, kind)
    selector = {"kind": kind, "record_id": original_id}
    initial_canonical_id = None
    source_notice_id = None
    canonical_notice_id = None

    for turn in (0, 1):
        server, thread = _native(directory, original)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with httpx.Client(base_url=base, trust_env=False) as client:
                if turn == 0:
                    review = client.get("/api/source-reconciliation", params=selector)
                    assert review.status_code == 200, review.text
                    initial_canonical_id = review.json()["canonical_investigation_id"]
                    assert initial_canonical_id

                    initial_watch = client.get("/api/investigation-watch", params={
                        "investigation_id": initial_canonical_id,
                    })
                    assert initial_watch.status_code == 200, initial_watch.text
                    watched = client.post(
                        "/api/investigation-watch",
                        json={
                            "action": "watch", "investigation_id": initial_canonical_id,
                            "expected_digest": initial_watch.json()["current_digest"],
                        },
                        headers={"Origin": base},
                    )
                    assert watched.status_code == 200, watched.text
                    assert watched.json()["changed"] is False
                    created = client.post(
                        "/api/source-watchlist-action",
                        json={"action": "add", **selector}, headers={"Origin": base},
                    )
                    assert created.status_code == 200, created.text
                    assert not [
                        n for n in client.get("/api/notifications").json()
                        if n.get("record_id") == original_id
                        or n.get("investigation_id") == initial_canonical_id
                    ]

                    # The original collector observes a new persisted source row.
                    # No worker approval or confirmed project identity accompanies it.
                    _store_original(original, _changed(record))
                    original_bytes = original.read_bytes()
                    before_worker = client.get("/api/notifications").json()
                    old = [n for n in before_worker if n.get("record_id") == original_id]
                    canonical = [
                        n for n in before_worker
                        if n.get("investigation_id") == initial_canonical_id
                    ]
                    assert len(old) == 1
                    assert canonical == []
                    assert old[0]["record_kind"] == kind
                    assert old[0]["source_claim_only"] is True
                    assert old[0]["read"] is False
                    source_notice_id = old[0]["id"]
                    assert original.read_bytes() == original_bytes

                    # Only exact reviewed source evidence can enter the common worker.
                    updated = client.get(
                        "/api/source-reconciliation", params=selector,
                    ).json()
                    assert updated["revision_replay_eligible"] is True
                    assert updated["canonical_investigation_id"] == initial_canonical_id
                    receipt = enqueue_legacy_reconciliation(
                        directory, original, _body(updated, revision=True),
                    )
                    assert receipt["outreach_authorized"] is False
                    assert receipt["bid_authorized"] is False
                    runtime = InvestigationRuntime(directory)
                    try:
                        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
                    finally:
                        runtime.close()

                    after_worker = client.get("/api/notifications").json()
                    original_notices = [
                        n for n in after_worker if n.get("record_id") == original_id
                    ]
                    canonical_notices = [
                        n for n in after_worker
                        if n.get("investigation_id") == initial_canonical_id
                    ]
                    assert len(original_notices) == 1
                    assert len(canonical_notices) == 1
                    assert original_notices[0]["id"] == source_notice_id
                    assert canonical_notices[0]["source_claim_only"] is True
                    assert canonical_notices[0]["read"] is False
                    canonical_notice_id = canonical_notices[0]["id"]
                    assert canonical_notice_id != source_notice_id
                    assert client.get("/api/notifications").json() == after_worker
                    assert original.read_bytes() == original_bytes
                    read = client.post(
                        "/api/notifications/read",
                        json={"ids": [source_notice_id]}, headers={"Origin": base},
                    )
                    assert read.status_code == 200, read.text
                    assert client.get("/api/investigation-watch", params={
                        "investigation_id": initial_canonical_id,
                    }).json()["changed"] is True

                else:
                    assert initial_canonical_id and source_notice_id and canonical_notice_id
                    notices = client.get("/api/notifications").json()
                    source_notices = [
                        n for n in notices if n.get("record_id") == original_id
                    ]
                    canonical_notices = [
                        n for n in notices
                        if n.get("investigation_id") == initial_canonical_id
                    ]
                    assert len(source_notices) == len(canonical_notices) == 1
                    assert source_notices[0]["id"] == source_notice_id
                    assert source_notices[0]["read"] is True
                    assert canonical_notices[0]["id"] == canonical_notice_id
                    assert canonical_notices[0]["read"] is False
                    current = client.get("/api/investigation-watch", params={
                        "investigation_id": initial_canonical_id,
                    }).json()
                    assert current["changed"] is True

                    # Acknowledging a canonical change does NOT secretly archive
                    # or acknowledge the independent original source watch.
                    acknowledged = client.post(
                        "/api/investigation-watch",
                        json={
                            "action": "acknowledge",
                            "investigation_id": initial_canonical_id,
                            "expected_digest": current["current_digest"],
                        },
                        headers={"Origin": base},
                    )
                    assert acknowledged.status_code == 200, acknowledged.text
                    assert acknowledged.json()["changed"] is False
                    remaining = client.get("/api/notifications").json()
                    assert [n["id"] for n in remaining if
                            n.get("record_id") == original_id] == [source_notice_id]
                    assert not [n for n in remaining if
                                n.get("investigation_id") == initial_canonical_id]

                    archived = client.post(
                        "/api/source-watchlist-action",
                        json={"action": "archive", **selector},
                        headers={"Origin": base},
                    )
                    assert archived.status_code == 200, archived.text
                    after_archive = client.get("/api/notifications").json()
                    assert not [n for n in after_archive if
                                n.get("record_id") == original_id
                                or n.get("investigation_id") == initial_canonical_id]
                    exact = client.get(
                        "/api/source-reconciliation", params=selector,
                    ).json()
                    assert exact["canonical_investigation_id"] == initial_canonical_id
                    assert exact["native_state"] == "exact_observation_already_retained"
                    assert exact["no_commercial_authorization"] is True
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
