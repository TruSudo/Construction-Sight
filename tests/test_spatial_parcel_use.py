import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest

from constructionsight.parcel_use_enrichment import LAYER
from constructionsight.spatial_parcel_use import claims_from_responses, collect, containment

RING = [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]
ROW = {
    "source_key": "one",
    "project_type": "unknown",
    "SITE_COUNTY": "Riverside",
    "SITE_LONGITUDE": 1,
    "SITE_LATITUDE": 1,
}


def retained(tmp_path: Path, features: list[dict], **extra: object) -> list[dict]:
    raw = json.dumps({"spatialReference": {"wkid": 4326}, "features": features, **extra}).encode()
    (tmp_path / "response.json").write_bytes(raw)
    query = urlencode(
        {
            "inSR": 4326,
            "outSR": 4326,
            "geometryType": "esriGeometryPoint",
            "geometry": json.dumps({"x": 1, "y": 1}),
        }
    )
    return [
        {
            "source_url": LAYER + "/query?" + query,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "path": "response.json",
            "targets": {"one": [1, 1]},
            "captured_at": "2026-10-15",
        }
    ]


def feature(apn: str = "one", rings: list | None = None) -> dict:
    return {
        "attributes": {"APN": apn, "CLASS_CODE": "HOMESITE/< 1 ACRE"},
        "geometry": {"rings": rings or [RING]},
    }


def test_interior_only_holes_overlap_and_coordinate_binding(tmp_path: Path) -> None:
    refs = retained(tmp_path, [feature()])
    claims, counts = claims_from_responses([ROW], refs, tmp_path)
    assert counts["classified"] == 1 and claims["one"]["verified"] is False
    assert (
        claims_from_responses([{**ROW, "SITE_NAME": "Dosner Organic Farms"}], refs, tmp_path)[0]
        == {}
    )
    assert claims["one"]["confidence"] == 0.45
    assert claims["one"]["source"] == "Source-claimed, from parcel use code"
    assert claims_from_responses([{**ROW, "SITE_LONGITUDE": 1.1}], refs, tmp_path)[0] == {}
    refs = retained(tmp_path, [feature(), feature("two")])
    assert claims_from_responses([ROW], refs, tmp_path)[1]["ambiguous"] == 1
    hole = [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]]
    assert containment((1, 1), {"rings": [RING, hole]}) is False
    assert containment((0, 1), {"rings": [RING]}) is None


def test_rejected_truncated_tampered_and_escaping_responses(tmp_path: Path) -> None:
    refs = retained(tmp_path, [feature()], exceededTransferLimit=True)
    with pytest.raises(ValueError, match="incomplete"):
        claims_from_responses([ROW], refs, tmp_path)
    refs = retained(tmp_path, [feature()])
    (tmp_path / "response.json").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        claims_from_responses([ROW], refs, tmp_path)
    refs[0]["path"] = "../response.json"
    with pytest.raises(ValueError, match="escapes"):
        claims_from_responses([ROW], refs, tmp_path)


def test_403_stops_source_and_cannot_reclassify(tmp_path: Path) -> None:
    calls = []

    def denied(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(403, request=request)

    with httpx.Client(transport=httpx.MockTransport(denied)) as client:
        result = collect(client, [ROW, {**ROW, "source_key": "two"}], tmp_path)
    assert len(calls) == 1 and result["claims"] == {} and result["unprocessed"] == 1
    assert result["errors"]
