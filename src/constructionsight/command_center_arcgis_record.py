"""Explicit one-record ArcGIS acquisition using the original reviewed engines.

No source or URL is supplied by the caller. A selected, independently verified
bounded proof dictates source, object ID and attributes. Exact evidence is
retained separately from parcel/site identity or commercial permissions.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.command_center_arcgis_proofs import (
    preview_arcgis_proof_bound_rows,
    preview_arcgis_proof_record_request,
)
from constructionsight.command_center_ceqanet_acquisition import _profile
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.http_transport import execute_bounded_http
from constructionsight.legal import AccessDecision, evaluate_access
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)
from constructionsight.parcel_source_acquisition_http import (
    ParcelArcGISHTTPPolicy,
    _exact_request_url,
    _require_success_body,
)
from constructionsight.storage.runtime_artifacts import (
    read_runtime_text,
    write_runtime_text,
)

_PLAN_KEYS = {
    "source_key", "expected_bundle_id", "expected_bundle_sha256",
    "expected_snapshot_id", "object_id", "expected_plan_id",
}
_REVIEW_KEYS = _PLAN_KEYS | {"access_review"}
_EXECUTE_KEYS = _REVIEW_KEYS | {"review_reason", "caller_confirmation"}
_MAX_RESPONSE_BYTES = 262_144
_TIMEOUT_SECONDS = 15.0


def preview_reviewed_arcgis_record_access(
    proof_path: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Recompute the exact source plan and assess evidenced current access."""
    if not isinstance(payload, dict) or set(payload) != _REVIEW_KEYS:
        raise ValueError("exact ArcGIS source record and access evidence required")
    plan = preview_arcgis_proof_record_request(
        proof_path, {key: payload[key] for key in _PLAN_KEYS},
    )
    if (
        type(payload["expected_plan_id"]) is not str
        or payload["expected_plan_id"] != plan["plan_id"]
    ):
        raise ValueError("record plan identity was changed since review")
    policy = evaluate_access(_profile(plan["query_url"], payload["access_review"]))
    identity = authorization_digest(
        "native-arcgis-single-record-read/v1",
        {"plan_id": plan["plan_id"], "access_review": payload["access_review"]},
    )
    return {
        "schema_version": "constructionsight.arcgis-record-access-preview/v1",
        "plan_id": plan["plan_id"],
        "source_key": plan["source_key"],
        "object_id": plan["object_id"],
        "query_url": plan["query_url"],
        "parameters": plan["parameters"],
        "expected_review_digest": identity,
        "access_decision": policy.decision.value,
        "access_reason": policy.reason,
        "may_request_approval": policy.decision is AccessDecision.ALLOWED,
        "maximum_requests": 1,
        "maximum_response_bytes": _MAX_RESPONSE_BYTES,
        "network_executed": False,
        "parcel_persisted": False,
        "site_identity_verified": False,
        "commercial_authority_granted": False,
    }


def _verify_exact_arcgis_feature(
    proof_path: Path | None, plan: dict[str, Any], body: bytes,
) -> dict[str, Any]:
    """Verify one exact ArcGIS response and run the existing parcel parser."""
    if len(body) > _MAX_RESPONSE_BYTES:
        raise ValueError("ArcGIS attribute evidence exceeds its byte ceiling")
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("official ArcGIS record body is not valid JSON") from exc
    if not isinstance(payload, dict) or "error" in payload:
        raise ValueError("ArcGIS record response is invalid or rejected")
    if payload.get("exceededTransferLimit") not in (None, False):
        raise ValueError("ArcGIS single-record response is incomplete")
    features = payload.get("features")
    if not isinstance(features, list) or len(features) != 1:
        raise ValueError("ArcGIS request must return exactly one feature")
    feature = features[0]
    if not isinstance(feature, dict) or "geometry" in feature:
        raise ValueError("record acquisition cannot contain geometry")
    attributes = feature.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("ArcGIS feature attributes must be an object")
    expected = set(plan["parameters"]["outFields"].split(","))
    if not attributes or any(
        type(key) is not str or key not in expected for key in attributes
    ):
        raise ValueError("ArcGIS response includes unrequested attributes")
    # The authoritative object ID is the snapshot's ordered probe identifier,
    # not a caller-supplied APN. The field name is from the requested plan.
    snapshot_field = next(
        (name for name in expected if name.casefold() == "objectid"), None,
    )
    if snapshot_field is None:
        raise ValueError("ArcGIS registered object ID field is missing")
    if type(attributes.get(snapshot_field)) is not int or (
        attributes[snapshot_field] != plan["object_id"]
    ):
        raise ValueError("ArcGIS response object ID differs from reviewed proof")
    row: dict[str, str] = {}
    for key, value in attributes.items():
        if value is None:
            continue
        if type(value) not in (str, int, float):
            raise ValueError("ArcGIS attribute has an unexpected structured value")
        if type(value) is float and (value != value or abs(value) == float("inf")):
            raise ValueError("ArcGIS numeric attribute must be finite")
        row[key] = str(value)
    report = preview_arcgis_proof_bound_rows(
        proof_path, {
            "source_key": plan["source_key"],
            "expected_bundle_id": plan["bundle_id"],
            "expected_bundle_sha256": plan["bundle_sha256"],
            "expected_snapshot_id": plan["snapshot_id"],
            "rows": [row],
        },
    )["report"]
    if report["usable_row_count"] != 1:
        raise ValueError("official source row is not usable as a parcel candidate")
    return report


def execute_reviewed_arcgis_record(
    directory: Path | None, proof_path: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """After explicit approval, retain one original bounded HTTP response.

    A verified *source response* is not yet a verified parcel/site identity.
    The durable effect lease forbids unreviewed retries across processes.
    """
    if directory is None or not isinstance(payload, dict) or set(payload) != _EXECUTE_KEYS:
        raise ValueError("private storage and exact single-record approval required")
    reason = payload["review_reason"]
    if (
        payload["caller_confirmation"] is not True
        or type(reason) is not str
        or not 10 <= len(reason.strip()) <= 2_000
    ):
        raise ValueError("specific reason and positive source-read consent required")
    approved = preview_reviewed_arcgis_record_access(
        proof_path, {key: payload[key] for key in _REVIEW_KEYS},
    )
    if not approved["may_request_approval"]:
        raise AuthorizationDeniedError("current ArcGIS source access remains blocked")
    plan = preview_arcgis_proof_record_request(
        proof_path, {key: payload[key] for key in _PLAN_KEYS},
    )
    request_url = _exact_request_url(plan["query_url"], plan["parameters"])
    policy = ParcelArcGISHTTPPolicy(
        timeout_seconds=_TIMEOUT_SECONDS,
        max_response_bytes=_MAX_RESPONSE_BYTES,
        max_attempts=1,
        retry_delays_seconds=(),
    ).bounded_policy(request_url)
    state = approved["expected_review_digest"]
    authorization = authorize_local_operator_operation(
        action="execute-parcel-arcgis-single-record-read",
        resource_type="verified-parcel-arcgis-object-id",
        resource_id=plan["plan_id"],
        exact_scope=(
            f"plan-id:{plan['plan_id']}",
            f"source:{plan['source_key']}",
            f"object-id:{plan['object_id']}",
            f"request-url:{request_url}",
            "CS-NET-004", "request-count:1", "geometry:false",
        ),
        current_state_identity=state,
        expected_identity=state,
        current_revocation_identity=state,
        granted_authority=("one exact public HTTPS attribute read and retained receipt",),
        denied_authority=(
            "bulk acquisition", "automatic retry", "redirect", "credential use",
            "geometry acquisition", "source promotion", "parcel or site merge",
            "outreach or bidding",
        ),
        limitations=(
            "historical object-ID membership is not current parcel identity",
            "record response does not authorize source recurrence or commerce",
        ),
        reason=reason.strip(),
        caller_confirmation=True,
    )

    def owned_read(observed_at: datetime) -> dict[str, Any]:
        observation = execute_bounded_http(request_url, "GET", policy)
        body = _require_success_body(observation)
        report = _verify_exact_arcgis_feature(proof_path, plan, body)
        return {
            "schema_version": "constructionsight.arcgis-single-record-body/v1",
            "plan_id": plan["plan_id"],
            "source_key": plan["source_key"],
            "bundle_id": plan["bundle_id"],
            "bundle_sha256": plan["bundle_sha256"],
            "snapshot_id": plan["snapshot_id"],
            "object_id": plan["object_id"],
            "request_url": request_url,
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "response_body_base64": base64.b64encode(body).decode("ascii"),
            "observed_at": observed_at.isoformat(),
            "report": report,
            "network_executed": True,
            "parcel_persisted": False,
            "site_identity_verified": False,
            "commercial_authority_granted": False,
        }

    result = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "arcgis-one-record-allowance", {"plan_id": plan["plan_id"]},
        ),
        content_identity=state,
        implementation_id=(
            "constructionsight.command_center_arcgis_record.owned_read"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=owned_read,
        encode_result=lambda value: value,
        decode_result=lambda value: dict(value),
    )
    filename = plan["plan_id"].replace(":", "-") + ".json"
    output = directory / "arcgis-record-evidence" / filename
    serialized = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if output.exists() or output.is_symlink():
        if read_runtime_text(output, max_bytes=2_000_000) != serialized:
            raise ValueError("existing retained record evidence differs from exact replay")
    else:
        write_runtime_text(output, serialized, overwrite=False, max_bytes=2_000_000)
    return {
        "schema_version": "constructionsight.arcgis-single-record-receipt/v1",
        "plan_id": result["plan_id"],
        "object_id": result["object_id"],
        "source_key": result["source_key"],
        "response_sha256": result["response_sha256"],
        "record_evidence_file": filename,
        "source_attributes_observed": True,
        "parcel_candidate_preview": result["report"],
        "network_executed": True,
        "original_response_retained": True,
        "parcel_persisted": False,
        "site_identity_verified": False,
        "commercial_authority_granted": False,
    }
