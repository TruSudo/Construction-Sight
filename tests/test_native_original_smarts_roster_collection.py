"""Native manual SMARTS roster collection keeps the original journal/checkpoint."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from constructionsight.command_center_smarts_roster_collection import (
    execute_reviewed_original_smarts_roster_collection,
    preview_original_smarts_roster_collection,
)
from constructionsight.live_command_center import make_server
from constructionsight.smarts_evidence_ledger import verify_smarts_journal
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_native_original_smarts_roster import _roster
from tests.test_smarts_collection import _page

_ALLOW = {
    "requires_login": False,
    "has_captcha": False,
    "robots_disallows_collection": False,
    "terms_disallow_collection": False,
    "paywalled": False,
    "access_fact_basis": "review:" + "b" * 64,
}


def _choice(known: bool = True) -> dict[str, object]:
    return {
        "run_id": "native-manual-smarts-1",
        "max_requests": 2,
        "access_review": (
            _ALLOW if known else {**_ALLOW, "terms_disallow_collection": None}
        ),
    }


def test_original_native_collector_fails_closed_unknown_or_unconfigured(
    tmp_path: Path,
) -> None:
    _db, roster, folder = _roster(tmp_path)
    journal, checkpoint = folder / "evidence.sqlite3", folder / "cursor.sqlite3"
    unknown = preview_original_smarts_roster_collection(
        roster, journal, checkpoint, _choice(known=False),
    )
    assert unknown["may_request_approval"] is False
    assert unknown["network_executed"] is False
    unconfigured = preview_original_smarts_roster_collection(
        roster, journal, None, _choice(),
    )
    assert unconfigured["available"] is False
    assert unconfigured["may_request_approval"] is False
    with pytest.raises(ValueError):
        execute_reviewed_original_smarts_roster_collection(
            roster, journal, checkpoint, {
                **_choice(known=False),
                "expected_preview_digest": unknown["expected_preview_digest"],
                "review_reason": "Exact original facility source evidence review",
                "caller_confirmation": True,
            },
        )


def test_original_native_collector_calls_real_checkpointed_original_only_once(
    tmp_path: Path,
) -> None:
    db, roster, folder = _roster(tmp_path)
    journal, checkpoint = folder / "evidence.sqlite3", folder / "cursor.sqlite3"
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    plan = preview_original_smarts_roster_collection(
        roster, journal, checkpoint, _choice(),
    )
    assert plan["may_request_approval"] is True
    approval = {
        **_choice(),
        "expected_preview_digest": plan["expected_preview_digest"],
        "review_reason": "Specific approved original exact facility roster",
        "caller_confirmation": True,
    }
    with pytest.raises(ValueError, match="stale"):
        execute_reviewed_original_smarts_roster_collection(
            roster, journal, checkpoint, {
                **approval, "expected_preview_digest": "0" * 64,
            },
        )
    def fake_get(
        _client: httpx.Client,
        *,
        county: str,
        app_id: str | None = None,
        wdid: str | None = None,
    ) -> object:
        return _page(
            app_id or "123456", wdid=wdid, county=county,
        )

    with patch(
        "constructionsight.command_center_smarts_roster_collection."
        "fetch_exact_facility",
        side_effect=fake_get,
    ) as fetch:
        receipt = execute_reviewed_original_smarts_roster_collection(
            roster, journal, checkpoint, approval,
        )
    assert fetch.call_count == 2
    assert receipt["original_request_count"] == 2
    assert receipt["completed"] == 2
    assert receipt["schedule_activated"] is False
    assert receipt["source_registry_mutated"] is False
    assert verify_smarts_journal(journal, read_only=True)["observations"] == 2
    assert checkpoint.is_file()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    # An explicitly approved replay of the completed original run does not
    # re-request completed IDs or create a new semantic source version.
    with patch(
        "constructionsight.command_center_smarts_roster_collection."
        "fetch_exact_facility",
        side_effect=AssertionError("completed original run repeated a live GET"),
    ):
        repeated = execute_reviewed_original_smarts_roster_collection(
            roster, journal, checkpoint, approval,
        )
    assert repeated["original_request_count"] == 0
    assert repeated["completed"] == 2
    assert verify_smarts_journal(journal, read_only=True)["observations"] == 2


def test_original_native_roster_collection_requires_same_origin_and_review(
    tmp_path: Path,
) -> None:
    db, roster, folder = _roster(tmp_path)
    journal, checkpoint = folder / "journal.sqlite3", folder / "checkpoint.sqlite3"
    server = make_server(
        snapshot(), 0, folder, operator_database=db,
        operator_smarts_collection_roster=roster,
        operator_smarts_journal=journal,
        operator_smarts_collection_checkpoint=checkpoint,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            cross = client.post(
                "/api/source-smarts-roster-preview",
                json=_choice(), headers={"Origin": "https://evil.invalid"},
            )
            assert cross.status_code == 403
            unknown = client.post(
                "/api/source-smarts-roster-preview",
                json=_choice(known=False), headers={"Origin": host},
            )
            assert unknown.status_code == 200, unknown.text
            assert unknown.json()["may_request_approval"] is False
            assert client.post(
                "/api/source-smarts-roster-collect",
                json={
                    **_choice(),
                    "expected_preview_digest": "0" * 64,
                    "review_reason": "Reviewed current exact facility roster",
                    "caller_confirmation": False,
                },
                headers={"Origin": host},
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
