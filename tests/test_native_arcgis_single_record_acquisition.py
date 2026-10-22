"""Bounded ArcGIS single-record authorization and exact-source evidence checks.

All responses are in-memory fixtures. Tests never contact external GIS servers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from constructionsight.command_center_arcgis_proofs import (
    preview_arcgis_proof_record_request,
    retained_arcgis_proof_preview,
)
from constructionsight.command_center_arcgis_record import (
    _verify_exact_arcgis_feature,
    execute_reviewed_arcgis_record,
    preview_reviewed_arcgis_record_access,
)
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    HttpFailureKind,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text
from tests.test_parcel_source_acquisition_bundle_storage import _bounded_bundle


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    bundle = _bounded_bundle()
    proof = tmp_path / "verified-arcgis-bounded.json"
    proof.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
    inventory = retained_arcgis_proof_preview(proof)
    payload: dict[str, object] = {
        "source_key": bundle.source_key,
        "expected_bundle_id": bundle.bundle_id,
        "expected_bundle_sha256": inventory["bundle_sha256"],
        "expected_snapshot_id": bundle.snapshot.snapshot_id,
        "object_id": 3,
    }
    plan = preview_arcgis_proof_record_request(proof, payload)
    return proof, payload, plan


def _access() -> dict[str, object]:
    return {
        "requires_login": False,
        "has_captcha": False,
        "robots_disallows_collection": False,
        "terms_disallow_collection": False,
        "paywalled": False,
        "access_fact_basis": "review:" + ("c" * 64),
    }


def _body(object_id: int = 3) -> bytes:
    return json.dumps({"features": [{
        "attributes": {"OBJECTID": object_id, "APN": "123-456-789"},
    }]}).encode()


def test_record_access_review_denies_unknown_or_stale_without_network(
    tmp_path: Path,
) -> None:
    proof, payload, plan = _fixture(tmp_path)
    request = {
        **payload, "expected_plan_id": plan["plan_id"],
        "access_review": _access(),
    }
    approved = preview_reviewed_arcgis_record_access(proof, request)
    assert approved["may_request_approval"] is True
    assert approved["maximum_requests"] == 1
    assert approved["network_executed"] is False
    assert approved["parcel_persisted"] is False
    denied = preview_reviewed_arcgis_record_access(
        proof, {**request, "access_review": {
            **_access(), "terms_disallow_collection": None,
        }},
    )
    assert denied["may_request_approval"] is False
    with pytest.raises(ValueError, match="plan identity"):
        preview_reviewed_arcgis_record_access(
            proof, {**request, "expected_plan_id": "counterfeit"},
        )
    with pytest.raises(ValueError):
        preview_reviewed_arcgis_record_access(
            proof, {**request, "host": "untrusted.invalid"},
        )


def test_original_parcel_parser_rejects_forged_attribute_responses(
    tmp_path: Path,
) -> None:
    proof, _, plan = _fixture(tmp_path)
    report = _verify_exact_arcgis_feature(proof, plan, _body())
    assert report["usable_row_count"] == 1
    assert report["rows"][0]["normalized_apn"] == "123456789"
    for fake in (
        {"features": []},
        {"features": [{"attributes": {"OBJECTID": 3, "APN": "123"}}, {
            "attributes": {"OBJECTID": 3, "APN": "123"},
        }]},
        {"features": [{"attributes": {"OBJECTID": 4, "APN": "123"}}]},
        {"features": [{"attributes": {"OBJECTID": 3, "APN": ""}}]},
        {"features": [{
            "attributes": {"OBJECTID": 3, "APN": "123"},
            "geometry": {"x": -117, "y": 34},
        }]},
        {"features": [{"attributes": {
            "OBJECTID": 3, "APN": "123", "unknown_name": "injection",
        }}]},
        {"error": {"code": 499, "message": "rejected"}},
        {"features": [{"attributes": {"OBJECTID": 3, "APN": "123"}}],
         "exceededTransferLimit": True},
    ):
        with pytest.raises(ValueError):
            _verify_exact_arcgis_feature(proof, plan, json.dumps(fake).encode())


def test_reviewed_record_executes_exact_one_bounded_transport_and_retains_bytes(
    tmp_path: Path,
) -> None:
    proof, payload, plan = _fixture(tmp_path)
    access = {**payload, "expected_plan_id": plan["plan_id"], "access_review": _access()}
    confirmed = {
        **access, "review_reason": "Reviewed one official bounded source record",
        "caller_confirmation": True,
    }
    body = _body()
    response = BoundedHttpObservation(
        policy_id="CS-NET-004",
        method="GET",
        request_url="https://source.example.invalid/query",
        final_url="https://source.example.invalid/query",
        status_code=200,
        content_type="application/json",
        content_encoding="utf-8",
        response_body=body,
        response_size=len(body),
        body_truncated=False,
        failure_kind=HttpFailureKind.NONE,
        error_type=None,
        error_detail=None,
    )
    calls = []
    def fake_owned(_authorization: object, **kwargs: object) -> object:
        effect = kwargs["effect"]
        assert callable(effect)
        calls.append("reserved")
        return effect(datetime(2026, 10, 21, tzinfo=UTC))

    with (
        patch(
            "constructionsight.command_center_arcgis_record."
            "authorize_local_operator_operation",
            return_value=object(),
        ),
        patch(
            "constructionsight.command_center_arcgis_record._execute_owned_effect",
            side_effect=fake_owned,
        ),
        patch(
            "constructionsight.command_center_arcgis_record.execute_bounded_http",
            return_value=response,
        ) as transport,
    ):
        receipt = execute_reviewed_arcgis_record(tmp_path / "native", proof, confirmed)
    assert calls == ["reserved"]
    assert transport.call_count == 1
    args = transport.call_args.args
    assert args[1] == "GET"
    assert "objectIds=3" in args[0]
    assert args[2].allowed_request_urls == (args[0],)
    assert args[2].max_response_bytes == 262_144
    assert receipt["network_executed"] is True
    assert receipt["original_response_retained"] is True
    assert receipt["parcel_persisted"] is False
    assert receipt["site_identity_verified"] is False
    assert receipt["commercial_authority_granted"] is False
    evidence = json.loads(read_runtime_text(
        tmp_path / "native" / "arcgis-record-evidence" / receipt["record_evidence_file"]
    ))
    import base64
    import hashlib

    assert base64.b64decode(evidence["response_body_base64"]) == body
    assert evidence["response_sha256"] == hashlib.sha256(body).hexdigest()
    assert evidence["plan_id"] == plan["plan_id"]
    assert evidence["report"]["rows"][0]["normalized_apn"] == "123456789"

    with pytest.raises(ValueError):
        execute_reviewed_arcgis_record(tmp_path / "native", proof, {
            **confirmed, "caller_confirmation": False,
        })
    with pytest.raises(ValueError):
        execute_reviewed_arcgis_record(tmp_path / "native", proof, {
            **confirmed, "commercial_authority": True,
        })
    with pytest.raises(Exception):
        execute_reviewed_arcgis_record(tmp_path / "native", proof, {
            **confirmed, "access_review": {
                **_access(), "robots_disallows_collection": True,
            },
        })
