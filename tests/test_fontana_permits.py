from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from constructionsight.fontana_permits import address, fetch_candidates, retain_candidates


def lead() -> dict:
    return {
        "source_key": "demo:1",
        "SITE_COUNTY": "San Bernardino",
        "SITE_CITY": "Fontana",
        "SITE_ADDRESS": "13592 Slover Avenue",
    }


def test_exact_address_candidates_do_not_invent_dossier_facts(tmp_path: Path) -> None:
    rows = [
        {"StreetNumber": "13592", "StreetName": "SLOVER AVE.", "PermitNumber": "Demo-1"},
        {"StreetNumber": "13592", "StreetName": "SLOVER", "PermitNumber": "Demo-2"},
        {"StreetNumber": "13593", "StreetName": "SLOVER AVE", "PermitNumber": "Demo-3"},
        {
            "StreetNumber": "13592",
            "StreetName": "SLOVER AVE",
            "Unit": "2",
            "PermitNumber": "Demo-4",
        },
    ]
    body = json.dumps({"results": rows}).encode()

    def response(request: httpx.Request) -> httpx.Response:
        assert request.url.params["StreetNumber"] == "13592"
        assert request.url.params["StreetName"] == "SLOVER AVE"
        return httpx.Response(200, content=body)

    with httpx.Client(transport=httpx.MockTransport(response)) as c:
        result = fetch_candidates(c, lead())
    assert len(result["candidates"]) == 1
    assert result["response_sha256"] == hashlib.sha256(body).hexdigest()
    assert result["filled_dossier_fields"] == {} and not result["project_match_verified"]
    retain_candidates(tmp_path, result)
    assert json.loads((tmp_path / "fontana-permits.json").read_text())["demo:1"] == result


def test_no_fuzzy_address_or_cross_county_and_no_bypass() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403))) as c:
        with pytest.raises(ValueError, match="HTTP 403"):
            fetch_candidates(c, lead())
        with pytest.raises(ValueError, match="Only"):
            fetch_candidates(c, {**lead(), "SITE_COUNTY": "Riverside"})
    assert address("Locust Avenue and Armstrong Road") is None
    assert address("13592 Slover Avenue") == address("13592 SLOVER AVE.")
