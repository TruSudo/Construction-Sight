"""Classification remains an inference; parcel identity and provenance fail closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from constructionsight.lead_quality import classify_names, quality_report
from constructionsight.parcel_use_enrichment import (
    LAYER,
    claims_from_responses,
    collect_parcel_use,
    source_use_type,
)
from constructionsight.security_fit import rank_leads


@pytest.mark.parametrize(
    ("name", "subtype"),
    [
        ("Senior Housing at Elm", "multifamily"),
        ("Meadows Elementary School", "school"),
        ("Victor Valley Medical Clinic", "medical"),
        ("New Hotel", "hotel"),
        ("Self Storage Facility", "storage"),
        ("Distribution Center", "warehouse_logistics"),
        ("Data Center Phase 1", "data_center"),
        ("Cannabis Cultivation", "cannabis"),
        ("Auto Dealership", "auto"),
        ("St Mary Church", "church"),
        ("Walmart Expansion", "retail"),
        ("Solar Facility", "solar"),
    ],
)
def test_explicit_source_words_are_explainable_unverified(name: str, subtype: str) -> None:
    result = classify_names({"SITE_NAME": name})
    assert result["subtype"] == subtype
    assert result["evidence_field"] == "SITE_NAME"
    assert result["matched_keyword"]
    assert result["verified"] is False


@pytest.mark.parametrize("name", ["TRACT 12345", "Hillside Park", "Centerpoint 123", "Automaton"])
def test_generic_tokens_do_not_manufacture_a_project_type(name: str) -> None:
    assert classify_names({"SITE_NAME": name})["project_type"] == "unknown"


def test_report_tokens_are_site_only_and_include_unknown_developers() -> None:
    report = quality_report(
        [
            {
                "project_type": "unknown",
                "SITE_NAME": "TRACT 12345",
                "DEVELOPER_NAME": "Rare Company",
            },
            {"project_type": "infrastructure"},
        ]
    )
    assert ["rare", 1] not in report["unknown_tokens"]
    assert report["unknown_developers"] == [("Rare Company", 1)]
    assert report["unknown_percent_non_excluded"] == 100


def test_use_code_never_establishes_proposed_use_or_decodes_numbers() -> None:
    assert source_use_type("123") is None
    assert source_use_type("Avocado Grove with SFR") is None
    claim = source_use_type("Apartment Over 100 Units")
    assert claim and claim["project_type"] == "residential" and claim["verified"] is False
    assert claim["source"] == "Source-claimed, from parcel use code"
    row = rank_leads([{"SITE_NAME": "Phase 3", "parcel_use_claim": claim}])[0]
    assert row["project_type"] == "residential"
    assert row["field_sources"]["project_type"]["verified"] is False


def test_ambiguous_cross_city_and_tampered_parcel_claims(tmp_path: Path) -> None:
    def evidence(features: list[dict]) -> list[dict]:
        raw = json.dumps({"features": [{"attributes": r} for r in features]}).encode()
        (tmp_path / "response.json").write_bytes(raw)
        return [
            {
                "source_url": LAYER + "/query?f=json",
                "path": "response.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "captured_at": "2026-10-14",
            }
        ]

    lead = {
        "SITE_NAME": "Phase 3",
        "SITE_ADDRESS": "100 Main Street",
        "SITE_CITY": "Perris",
        "SITE_COUNTY": "Riverside",
        "project_type": "unknown",
        "source_key": "test",
    }
    attrs = {
        "APN": "1",
        "SITUS_STREET": "100 MAIN ST",
        "SITUS_CITY": "PERRIS CA 92570",
        "CLASS_CODE": "Apartment Over 100 Units",
        "UNIT_NUMBER": "",
    }
    refs = evidence([attrs])
    claims, counts = claims_from_responses([lead], refs, tmp_path)
    assert counts["classified"] == 1 and claims["test"]["verified"] is False
    assert claims_from_responses([{**lead, "SITE_CITY": "Corona"}], refs, tmp_path)[0] == {}
    refs = evidence([attrs, {**attrs, "APN": "2", "UNIT_NUMBER": "2"}])
    assert claims_from_responses([lead], refs, tmp_path)[1]["ambiguous"] == 1
    (tmp_path / "response.json").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        claims_from_responses([lead], refs, tmp_path)


def test_403_stops_without_publishing_or_retrying(tmp_path: Path) -> None:
    calls = []

    def denied(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(403, request=request)

    lead = {"SITE_ADDRESS": "100 Main St", "SITE_COUNTY": "Riverside", "project_type": "unknown"}
    with (
        httpx.Client(transport=httpx.MockTransport(denied)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        collect_parcel_use(client, [lead], tmp_path)
    assert len(calls) == 1 and not (tmp_path / "parcel-use.json").exists()


def test_bad_parcel_manifest_does_not_take_the_lead_console_down(tmp_path: Path) -> None:
    from constructionsight.live_command_center import projection

    (tmp_path / "parcel-use.json").write_text("{broken")
    snapshot = {
        "rows": [{"SITE_NAME": "Tract 123", "source_key": "test"}],
        "captured_at": "2026-10-14",
        "requests": 0,
        "totals": {},
        "baseline": True,
        "missing_count": 0,
    }
    result = projection(snapshot, tmp_path)
    assert result["rows"][0]["project_type"] == "unknown"
    assert "Parcel enrichment rejected" in result["warning"]
