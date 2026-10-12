"""Offline regression tests for the SMARTS public read-only observation boundary."""

from __future__ import annotations

import json
from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest

from constructionsight.smarts_api import (
    CANDIDATE_FIELDS,
    RESOURCE_IDS,
    SmartsApiError,
    fetch_bounded_snapshot,
    fetch_page,
    fetch_recent_candidates,
    fetch_status_summary,
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


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _constant(response: httpx.Response) -> Callable[[httpx.Request], httpx.Response]:
    def responder(_: httpx.Request) -> httpx.Response:
        return response

    return responder


def _row(number: int) -> dict[str, object]:
    return {
        "_id": number,
        "APP_ID": "APP" + str(number),
        "WDID": "WDID" + str(number),
        "SITE_COUNTY": "San Bernardino",
    }


def _sql_response(rows: list[dict[str, object]]) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={"success": True, "result": {"records": rows}},
    )


def _candidate(number: int, county: str = "Riverside") -> dict[str, object]:
    return {
        "_id": number,
        "APP_ID": "APP" + str(number),
        "WDID": "WDID" + str(number),
        "SITE_COUNTY": county,
        "SITE_CITY": "Sample City",
        "STATUS": "Active",
        "NOI_PROCESSED_DATE": "2026-10-01",
        "CONSTRUCTION_COMMENCEMENT_DATE": "2027-01-01",
        "NOT_EFFECTIVE_DATE": None,
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

    with _client(no_network) as client, pytest.raises(SmartsApiError):
        fetch_page(client, resource=resource, county=county, limit=limit, offset=offset)


def test_http_error_and_redirect_fail_closed() -> None:
    for status in (302, 401, 403, 429, 500):
        with _client(_constant(httpx.Response(status))) as client, pytest.raises(
            SmartsApiError, match="HTTP status"
        ):
            fetch_page(client)


def test_missing_or_wrong_media_type_is_rejected() -> None:
    with _client(lambda _: httpx.Response(200, content=b"<html>ok</html>")) as client, \
            pytest.raises(SmartsApiError, match="Expected a JSON"):
        fetch_page(client)


def test_oversized_body_is_rejected() -> None:
    with _client(lambda _: httpx.Response(
        200, content=b"x" * 2_000_001, headers={"content-type": "application/json"}
    )) as client, pytest.raises(SmartsApiError, match="byte limit"):
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
        with _client(_constant(response)) as client, pytest.raises(SmartsApiError):
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
    with _client(lambda _: _response([_row(1)], total=600)) as client, \
            pytest.raises(SmartsApiError, match="budget"):
        fetch_bounded_snapshot(client, max_records=500)


def test_snapshot_refuses_duplicate_id() -> None:
    def responder(req: httpx.Request) -> httpx.Response:
        offset = int(parse_qs(req.url.query.decode())["offset"][0])
        rows = [_row(1)] if offset == 0 else [_row(1)]
        return _response(rows, total=2)

    with _client(responder) as client, pytest.raises(SmartsApiError, match="Duplicate"):
        fetch_bounded_snapshot(client, page_size=1, max_records=2)


def test_snapshot_refuses_drifting_total() -> None:
    def responder(req: httpx.Request) -> httpx.Response:
        offset = int(parse_qs(req.url.query.decode())["offset"][0])
        return _response([_row(offset + 1)], total=2 if offset == 0 else 3)

    with _client(responder) as client, pytest.raises(SmartsApiError, match="changed"):
        fetch_bounded_snapshot(client, page_size=1, max_records=5)


def test_cli_does_not_access_network_without_explicit_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "--execute-live" in capsys.readouterr().err


def test_status_summary_uses_fixed_county_sql_and_preserves_digest() -> None:
    requests: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _sql_response([{
            "SITE_COUNTY": "San Bernardino", "STATUS": "Active", "n": 698,
        }])

    with _client(responder) as client:
        summary = fetch_status_summary(client, county="San Bernardino")
    sql = parse_qs(requests[0].url.query.decode())["sql"][0]
    assert requests[0].url.path.endswith("/datastore_search_sql")
    assert requests[0].method == "GET"
    assert 'COUNT(*) AS n' in sql
    assert '"SITE_COUNTY" = \'San Bernardino\'' in sql
    assert "LIMIT 32" in sql
    assert summary.records[0]["n"] == 698
    assert len(summary.response_sha256) == 64
    assert "sql=" in summary.request_url


@pytest.mark.parametrize("county", ["Other", "Riverside' OR 1=1 --", "riverside", ""])
def test_sql_rejects_unapproved_county_before_network(county: str) -> None:
    def no_network(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Request must be rejected locally")

    with _client(no_network) as client:
        with pytest.raises(SmartsApiError, match="county"):
            fetch_status_summary(client, county=county)
        with pytest.raises(SmartsApiError, match="county"):
            fetch_recent_candidates(client, county=county)


@pytest.mark.parametrize("limit", [0, 26, True, 1.5])
def test_candidate_limit_rejected_before_network(limit: object) -> None:
    def no_network(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Request must be rejected locally")

    with _client(no_network) as client, pytest.raises(SmartsApiError, match="limit"):
        fetch_recent_candidates(client, county="Riverside", limit=limit)  # type: ignore[arg-type]


def test_recent_candidates_select_no_contact_columns_and_keep_future_date() -> None:
    requests: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _sql_response([_candidate(1)])

    with _client(responder) as client:
        candidates = fetch_recent_candidates(client, county="Riverside", limit=2)
    sql = parse_qs(requests[0].url.query.decode())["sql"][0]
    assert '"SITE_COUNTY" = \'Riverside\'' in sql
    assert '"NOI_PROCESSED_DATE" IS NOT NULL' in sql
    assert "LIMIT 2" in sql
    assert all('"' + field + '"' in sql for field in CANDIDATE_FIELDS)
    assert "CONTACT" not in sql and "DEVELOPER" not in sql and "ADDRESS" not in sql
    assert candidates.records[0]["CONSTRUCTION_COMMENCEMENT_DATE"] == "2027-01-01"


def test_sql_rejects_bad_rows_and_truncated_summary() -> None:
    cases: list[tuple[httpx.Response, str]] = [
        (_sql_response([{"SITE_COUNTY": "Riverside", "STATUS": "Active", "n": True}]),
         "summary"),
        (_sql_response([{"SITE_COUNTY": "Riverside", "STATUS": "Active", "n": 1}] * 32),
         "summary"),
        (_sql_response([_candidate(1, county="Other")]), "candidates"),
        (_sql_response([_candidate(1), _candidate(1)]), "candidates"),
    ]
    for response, kind in cases:
        with _client(_constant(response)) as client, pytest.raises(SmartsApiError):
            if kind == "summary":
                fetch_status_summary(client, county="Riverside")
            else:
                fetch_recent_candidates(client, county="Riverside")


def test_sql_failures_do_not_echo_source_body_or_contact_details() -> None:
    secret = "private.contact@example.test"
    responses = [
        httpx.Response(500, text=secret),
        httpx.Response(200, headers={"content-type": "application/json"},
                       json={"success": False, "error": secret}),
        httpx.Response(200, headers={"content-type": "application/json"},
                       content=b"x" * 2_000_001),
    ]
    for response in responses:
        with _client(_constant(response)) as client, pytest.raises(SmartsApiError) as exc:
            fetch_status_summary(client, county="Riverside")
        assert secret not in str(exc.value)


def test_sql_cli_stays_explicitly_gated(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--mode", "recent-candidates", "--county", "Riverside"])
    assert exc.value.code == 2
    assert "--execute-live" in capsys.readouterr().err


def test_sql_cli_labels_activity_and_omits_contact_data(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = _client(lambda _: _sql_response([_candidate(1)]))
    monkeypatch.setattr(httpx, "Client", lambda **_: client)
    assert main([
        "--mode", "recent-candidates", "--county", "Riverside",
        "--limit", "1", "--execute-live",
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["regulatory_status_is_construction_activity"] is False
    assert output["reported_commencement_is_verified_activity"] is False
    assert output["records"][0]["CONSTRUCTION_COMMENCEMENT_DATE"] == "2027-01-01"
    assert "DEVELOPER_EMAIL" not in json.dumps(output)


def test_page_cli_hides_contact_schema_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    row = _row(1) | {"DEVELOPER_EMAIL": "private.contact@example.test"}
    response = _response([row], fields=(
        "_id", "APP_ID", "WDID", "SITE_COUNTY", "DEVELOPER_EMAIL",
    ))
    client = _client(_constant(response))
    monkeypatch.setattr(httpx, "Client", lambda **_: client)
    assert main(["--county", "San Bernardino", "--limit", "1", "--execute-live"]) == 0
    output = capsys.readouterr().out
    assert "DEVELOPER_EMAIL" not in output
    assert "private.contact@example.test" not in output
