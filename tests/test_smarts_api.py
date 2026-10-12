"""Offline regression tests for the SMARTS public read-only observation boundary."""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from constructionsight.smarts_api import (
    RESOURCE_IDS,
    SmartsApiError,
    fetch_bounded_snapshot,
    fetch_page,
    main,
)


def _response(
    rows: list[dict[str, object]],
    *,
    total: int | None = None,
    resource: str = "facilities",
    fields: tuple[str, ...] | None = None,
) -> httpx.Response:
    names = fields or (
        ("_id", "APP_ID", "WDID", "SITE_COUNTY")
        if resource == "facilities"
        else ("_id", "APP_ID", "WDID")
    )
    return httpx.Response(
        200,
        headers={"content-type": "application/json; charset=utf-8"},
        json={
            "success": True,
            "result": {
                "resource_id": RESOURCE_IDS[resource],
                "total": len(rows) if total is None else total,
                "fields": [{"id": n} for n in names],
                "records": rows,
            },
        },
    )


def _client(handler: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _row(number: int) -> dict[str, object]:
    return {
        "_id": number,
        "APP_ID": "APP" + str(number),
        "WDID": "WDID" + str(number),
        "SITE_COUNTY": "San Bernardino",
    }


def test_exact_approved_resource_and_county_query() -> None:
    requests: list[httpx.Request] = []

    def responder(req: httpx.Request) -> httpx.Response:
        requests.append(req)
        return _response([_row(1)])

    with _client(responder) as client:
        page = fetch_page(client, county="San Bernardino", limit=1)

    assert page.total == 1
    assert page.records[0]["APP_ID"] == "APP1"
    assert len(page.response_sha256) == 64
    assert requests[0].url.host == "publish.data.ca.gov"
    assert requests[0].url.path == "/api/3/action/datastore_search"
    assert requests[0].method == "GET"
    params = parse_qs(requests[0].url.query.decode())
    assert params["resource_id"] == [RESOURCE_IDS["facilities"]]
    assert params["limit"] == ["1"]
    assert json.loads(params["filters"][0]) == {"SITE_COUNTY": "San Bernardino"}


@pytest.mark.parametrize(
    "resource, county, limit, offset",
    [
        ("private-resource", None, 3, 0),
        ("inspections", "Riverside", 3, 0),
        ("facilities", "Other", 3, 0),
        ("facilities", None, 0, 0),
        ("facilities", None, 101, 0),
        ("facilities", None, 2, -1),
        ("facilities", None, 2, 1_000_001),
    ],
)
def test_invalid_requests_fail_before_network(
    resource: str, county: str | None, limit: int, offset: int
) -> None:
    def no_network(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Request must be rejected locally")

    with _client(no_network) as client:
        with pytest.raises(SmartsApiError):
            fetch_page(client, resource=resource, county=county, limit=limit, offset=offset)


def test_http_error_and_redirect_fail_closed() -> None:
    for status in (302, 401, 403, 429, 500):
        with _client(lambda _: httpx.Response(status)) as client:
            with pytest.raises(SmartsApiError, match="HTTP status"):
                fetch_page(client)


def test_missing_or_wrong_media_type_is_rejected() -> None:
    with _client(lambda _: httpx.Response(200, content=b"<html>ok</html>")) as client:
        with pytest.raises(SmartsApiError, match="Expected a JSON"):
            fetch_page(client)


def test_oversized_body_is_rejected() -> None:
    with _client(lambda _: httpx.Response(
        200, content=b"x" * 2_000_001, headers={"content-type": "application/json"}
    )) as client:
        with pytest.raises(SmartsApiError, match="byte limit"):
            fetch_page(client)


def test_bad_response_identity_or_count_rejected() -> None:
    bad = _response([_row(1)], total=0)
    wrong = httpx.Response(
        200, headers={"content-type": "application/json"},
        json={"success": True, "result": {
            "resource_id": "not-ours", "total": 0,
            "fields": [{"id": "_id"}, {"id": "APP_ID"}, {"id": "WDID"},
                       {"id": "SITE_COUNTY"}], "records": [],
        }},
    )
    for response in (bad, wrong):
        with _client(lambda _, resp=response: resp) as client:
            with pytest.raises(SmartsApiError):
                fetch_page(client)


def test_inspection_schema_is_verified_independently() -> None:
    with _client(lambda _: _response(
        [{"_id": 1, "APP_ID": 22, "WDID": "x"}], resource="inspections"
    )) as client:
        page = fetch_page(client, resource="inspections")
    assert page.resource == "inspections"
    assert page.records[0]["APP_ID"] == 22


def test_bounded_two_page_snapshot() -> None:
    offsets: list[int] = []

    def responder(req: httpx.Request) -> httpx.Response:
        offset = int(parse_qs(req.url.query.decode())["offset"][0])
        offsets.append(offset)
        rows = [_row(1), _row(2)] if offset == 0 else [_row(3)]
        return _response(rows, total=3)

    with _client(responder) as client:
        pages = fetch_bounded_snapshot(client, page_size=2, max_records=3)
    assert offsets == [0, 2]
    assert sum(len(p.records) for p in pages) == 3


def test_snapshot_refuses_incomplete_large_scope() -> None:
    with _client(lambda _: _response([_row(1)], total=600)) as client:
        with pytest.raises(SmartsApiError, match="budget"):
            fetch_bounded_snapshot(client, max_records=500)


def test_snapshot_refuses_duplicate_id() -> None:
    def responder(req: httpx.Request) -> httpx.Response:
        offset = int(parse_qs(req.url.query.decode())["offset"][0])
        rows = [_row(1)] if offset == 0 else [_row(1)]
        return _response(rows, total=2)

    with _client(responder) as client:
        with pytest.raises(SmartsApiError, match="Duplicate"):
            fetch_bounded_snapshot(client, page_size=1, max_records=2)


def test_snapshot_refuses_drifting_total() -> None:
    def responder(req: httpx.Request) -> httpx.Response:
        offset = int(parse_qs(req.url.query.decode())["offset"][0])
        return _response([_row(offset + 1)], total=2 if offset == 0 else 3)

    with _client(responder) as client:
        with pytest.raises(SmartsApiError, match="changed"):
            fetch_bounded_snapshot(client, page_size=1, max_records=5)


def test_cli_does_not_access_network_without_explicit_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "--execute-live" in capsys.readouterr().err
