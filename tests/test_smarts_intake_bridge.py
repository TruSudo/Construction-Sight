"""Offline contract tests for SMARTS→existing source-neutral intake and site resolution."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from constructionsight.intake_models import (
    FactConfidence,
    IntakeRouting,
    MaterialFactKind,
)
from constructionsight.site_resolution_models import SiteResolutionStatus
from constructionsight.smarts_api import (
    RESOURCE_IDS,
    SmartsApiError,
    SmartsPage,
    fetch_exact_facility,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview
from constructionsight.smarts_intake_cli import main


def _record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "_id": 8,
        "APP_ID": "600752",
        "WDID": "6A33C123456",
        "SITE_COUNTY": "Riverside",
        "SITE_CITY": "Menifee",
        "SITE_NAME": "Northern Gateway Street Improvements",
        "SITE_ADDRESS": "123 Example Road",
        "SITE_LATITUDE": "33.70",
        "SITE_LONGITUDE": "-117.17",
        "STATUS": "Active",
        "NOI_PROCESSED_DATE": "2026-09-23",
        "CONSTRUCTION_COMMENCEMENT_DATE": "2026-10-01",
        "DEVELOPER_NAME": "Example Construction LLC",
        "DEVELOPER_EMAIL": "private@example.test",
        "DEVELOPER_PHONE": "555-555-5555",
    }
    record.update(overrides)
    return record


def _page(record: dict[str, Any], *, county: str | None = "Riverside") -> SmartsPage:
    return SmartsPage(
        resource="facilities",
        county=county,
        offset=0,
        limit=2,
        total=1,
        request_url="https://publish.data.ca.gov/api/3/action/datastore_search",
        response_sha256="1" * 64,
        fields=tuple(record),
        records=(record,),
    )


def _api_response(
    rows: list[dict[str, Any]], total: int | None = None
) -> httpx.Response:
    fields = list(rows[0]) if rows else ["_id", "APP_ID", "WDID", "SITE_COUNTY"]
    return httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={
            "success": True,
            "result": {
                "resource_id": RESOURCE_IDS["facilities"],
                "total": len(rows) if total is None else total,
                "records": rows,
                "fields": [{"id": name} for name in fields],
            },
        },
    )


def test_exact_app_id_request_and_intake_bridge() -> None:
    requests: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _api_response([_record()])

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        page = fetch_exact_facility(client, county="Riverside", app_id="600752")

    params = parse_qs(requests[0].url.query.decode())
    assert json.loads(params["filters"][0]) == {
        "SITE_COUNTY": "Riverside", "APP_ID": "600752"
    }
    assert params["limit"] == ["2"]
    preview = build_smarts_intake_preview(page, page.records[0])
    assert preview.identity_status == "source_scoped_candidate"
    assert preview.source_record_key == "smarts:facility:Riverside:wdid:6A33C123456"
    assert preview.read_only is True
    assert preview.construction_activity == "unverified"
    assert preview.commercial_readiness == "blocked_pending_verification"
    assert preview.external_project_match == "unreviewed"
    assert preview.site_resolution.status == SiteResolutionStatus.PARTIAL
    assert preview.site_resolution.candidates[0].latitude == 33.70
    assert preview.intake.routing == IntakeRouting.HUMAN_REVIEW
    assert preview.intake.record_hints["reported_construction_commencement"] == "2026-10-01"
    assert preview.intake.evidence.sha256 == preview.record_sha256
    assert all(fact.confidence == FactConfidence.SOURCE_CLAIMED
               for fact in preview.intake.extracted_facts)
    assert {fact.fact_kind for fact in preview.intake.extracted_facts} == {
        MaterialFactKind.PROJECT_TITLE,
        MaterialFactKind.ADDRESS,
        MaterialFactKind.PERSON_OR_ORGANIZATION,
    }
    rendered = json.dumps(preview.model_dump(mode="json"))
    assert "private@example.test" not in rendered
    assert "555-555-5555" not in rendered


def test_ckan_row_position_does_not_change_semantic_record_digest() -> None:
    left = _record(_id=100)
    right = _record(_id=200)
    preview1 = build_smarts_intake_preview(_page(left), left)
    preview2 = build_smarts_intake_preview(_page(right), right)
    assert preview1.record_sha256 == preview2.record_sha256
    assert preview1.intake.intake_id == preview2.intake.intake_id
    assert preview1.source_record_key == preview2.source_record_key


def test_one_changed_business_field_produces_new_evidence_digest() -> None:
    before = _record(STATUS="Active")
    after = _record(STATUS="Terminated")
    old = build_smarts_intake_preview(_page(before), before)
    new = build_smarts_intake_preview(_page(after), after)
    assert old.record_sha256 != new.record_sha256
    assert old.source_record_key == new.source_record_key
    assert old.construction_activity == new.construction_activity == "unverified"


def test_na_app_id_never_becomes_a_stable_identity() -> None:
    row = _record(APP_ID="NA", WDID="NA")
    preview = build_smarts_intake_preview(_page(row), row)
    assert preview.source_record_key is None
    assert preview.identity_status == "missing_source_identity"
    assert preview.site_resolution.status == SiteResolutionStatus.PARTIAL
    assert any("No usable" in message for message in preview.limitations)


def test_malformed_source_identifiers_never_become_stable_keys() -> None:
    row = _record(APP_ID="000", WDID="bad;id")
    preview = build_smarts_intake_preview(_page(row), row)
    assert preview.source_record_key is None
    assert preview.identity_status == "missing_source_identity"


def test_valid_wdid_can_anchor_source_identity_when_app_id_is_na() -> None:
    row = _record(APP_ID="NA", WDID="7 33C300548")
    preview = build_smarts_intake_preview(_page(row), row)
    assert preview.source_record_key == "smarts:facility:Riverside:wdid:7 33C300548"


def test_missing_site_information_remains_unresolved() -> None:
    row = _record(
        SITE_NAME=None, SITE_ADDRESS="NA", DEVELOPER_NAME="NA",
        SITE_LATITUDE="0", SITE_LONGITUDE="0",
    )
    preview = build_smarts_intake_preview(_page(row), row)
    assert preview.site_resolution.status == SiteResolutionStatus.UNRESOLVED
    assert preview.intake.unmapped_fragments
    assert any("coordinates" in message.lower() for message in preview.limitations)


def test_source_county_conflict_rejected() -> None:
    row = _record(SITE_COUNTY="San Bernardino")
    with pytest.raises(SmartsApiError, match="county"):
        build_smarts_intake_preview(_page(row), row)


def test_unbound_record_rejected() -> None:
    row = _record()
    with pytest.raises(SmartsApiError, match="Unbound"):
        build_smarts_intake_preview(_page(row), _record(APP_ID="99999"))


@pytest.mark.parametrize(
    "app_id,wdid",
    [
        ("NA", None),
        ("602710' OR 1=1", None),
        ("0;DROP", None),
        ("0", None),
        (None, "  "),
        (None, "invalid';--"),
    ],
)
def test_invalid_lookups_fail_before_network(
    app_id: str | None, wdid: str | None
) -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Network must not be used for invalid input")

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(SmartsApiError):
            fetch_exact_facility(client, county="Riverside", app_id=app_id, wdid=wdid)


def test_missing_or_duplicate_exact_match_is_rejected() -> None:
    for response in (_api_response([], 0), _api_response([_record(), _record(_id=9)], 2)):
        with httpx.Client(
            transport=httpx.MockTransport(lambda _: response)
        ) as client:
            with pytest.raises(SmartsApiError):
                fetch_exact_facility(client, county="Riverside", app_id="600752")


def test_mismatched_returned_identity_rejected() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: _api_response([_record(APP_ID="777")]))
    ) as client:
        with pytest.raises(SmartsApiError, match="APP_ID filter"):
            fetch_exact_facility(client, county="Riverside", app_id="600752")


def test_cli_requires_explicit_live_authorization(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--county", "Riverside", "--app-id", "600752"])
    assert exc.value.code == 2
    assert "--execute-live" in capsys.readouterr().err
