"""Mocked integration tests: SMARTS recent-query → exact fetch → site preview."""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from constructionsight.smarts_api import RESOURCE_IDS, SmartsApiError
from constructionsight.smarts_recent_review_cli import build_recent_review, main


def _recent(
    app_id: str = "602870", status: str = "Active"
) -> dict[str, object]:
    return {
        "_id": 10,
        "APP_ID": app_id,
        "WDID": "W001",
        "SITE_COUNTY": "San Bernardino",
        "SITE_CITY": "Grand Terrace",
        "STATUS": status,
        "NOI_PROCESSED_DATE": "2026-09-17",
        "CONSTRUCTION_COMMENCEMENT_DATE": "2026-10-01",
        "NOT_EFFECTIVE_DATE": None,
    }


def _full(app_id: str = "602870") -> dict[str, object]:
    return {
        **_recent(app_id),
        "SITE_NAME": "Gateway at Grand Terrace",
        "SITE_ADDRESS": "123 Example Boulevard",
        "SITE_LATITUDE": "34.03",
        "SITE_LONGITUDE": "-117.31",
        "DEVELOPER_NAME": "Lewis Land Developers LLC",
        "DEVELOPER_EMAIL": "example.private@example.test",
    }


def _res(rows: list[dict[str, object]]) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={
            "success": True,
            "result": {
                "total": len(rows),
                "resource_id": RESOURCE_IDS["facilities"],
                "fields": [{"id": key} for key in (list(rows[0]) if rows else
                            ["_id", "APP_ID", "WDID", "SITE_COUNTY"])],
                "records": rows,
            },
        },
    )


def test_recent_review_uses_two_read_only_requests_no_lead_promotion() -> None:
    paths: list[str] = []
    def responder(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/datastore_search_sql"):
            return httpx.Response(200, headers={"content-type": "application/json"},
                json={"success": True, "result": {"records": [_recent()]}})
        assert request.url.path.endswith("/datastore_search")
        query = parse_qs(request.url.query.decode())
        assert json.loads(query["filters"][0]) == {
            "SITE_COUNTY": "San Bernardino", "APP_ID": "602870"
        }
        return _res([_full()])

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        report = build_recent_review(client, county="San Bernardino", limit=1)

    assert len(paths) == 2
    assert report["reviewed_count"] == 1
    assert report["candidate_count"] == 1
    assert report["outreach_authorized"] is False
    assert report["persistence_mutated"] is False
    assert report["construction_activity_verified"] is False
    first = report["records"][0]
    assert first["site_name"] == "Gateway at Grand Terrace"
    assert first["construction_activity"] == "unverified"
    assert first["commercial_readiness"] == "blocked_pending_verification"
    assert first["reported_commencement"] == "2026-10-01"
    assert "example.private@example.test" not in json.dumps(report)


def test_active_na_id_is_skipped_without_unsafe_fallback() -> None:
    count = 0
    def responder(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        assert request.url.path.endswith("/datastore_search_sql")
        return httpx.Response(200, headers={"content-type": "application/json"},
            json={"success": True, "result": {"records": [_recent(app_id="NA")]}})

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        report = build_recent_review(client, county="San Bernardino", limit=1)

    assert count == 1
    assert report["reviewed_count"] == 0
    assert report["skipped"] == [{"reason": "missing_usable_app_id"}]


def test_nonactive_regulatory_result_is_not_promoted() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/datastore_search_sql")
        return httpx.Response(200, headers={"content-type": "application/json"},
            json={"success": True, "result": {
                "records": [_recent(status="Terminated")]}})

    with httpx.Client(transport=httpx.MockTransport(responder)) as client:
        report = build_recent_review(client, county="San Bernardino", limit=1)

    assert report["reviewed_count"] == 0
    assert report["skipped"][0]["reason"] == "not_active_regulatory_status"


@pytest.mark.parametrize("limit", [0, 6, -1, True])
def test_invalid_review_budgets_fail_before_network(limit: int) -> None:
    def no_network(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid review budget must never reach network")

    with httpx.Client(transport=httpx.MockTransport(no_network)) as client, pytest.raises(
        SmartsApiError
    ):
        build_recent_review(client, county="San Bernardino", limit=limit)


def test_cli_never_runs_implicitly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--county", "San Bernardino", "--limit", "1"])
    assert exc.value.code == 2
    assert "--execute-live" in capsys.readouterr().err
