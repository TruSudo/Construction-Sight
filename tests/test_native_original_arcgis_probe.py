"""Original bounded ArcGIS probe: exact reviewed native authority, no implicit GET."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from constructionsight.command_center_arcgis_probe import (
    execute_reviewed_original_arcgis_probe,
    preview_original_arcgis_probe,
)
from constructionsight.command_center_arcgis_proofs import retained_arcgis_proof_preview
from constructionsight.live_command_center import make_server
from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
)
from constructionsight.parcel_source_acquisition_bundle import (
    build_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_verification import (
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_parcel_arcgis_operator_service import _probe_result

_ALLOW = {
    "requires_login": False,
    "has_captcha": False,
    "robots_disallows_collection": False,
    "terms_disallow_collection": False,
    "paywalled": False,
    "access_fact_basis": "review:" + "d" * 64,
}


def _selection(allowed: bool = True) -> dict[str, object]:
    return {
        "source_key": get_verified_parcel_source_profiles()[0].source_key,
        "sample_size": 2,
        "access_review": _ALLOW if allowed else {
            **_ALLOW, "terms_disallow_collection": None,
        },
    }


def _original_bundle():
    profile = get_verified_parcel_source_profiles()[0]
    indexed = {x.evidence_id: x for x in get_parcel_source_evidence()}
    snap, plan, observations = _probe_result(profile, sample_size=2)
    assessment = build_arcgis_acquisition_assessment(snap, plan, observations)
    return build_arcgis_bounded_proof_bundle(
        profile, (indexed[x] for x in profile.evidence_ids),
        snap, plan, observations, assessment,
        created_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
    )


def test_native_original_arcgis_review_denies_unknown_current_access(
    tmp_path: Path,
) -> None:
    choice = _selection(False)
    reviewed = preview_original_arcgis_probe(tmp_path, choice)
    assert reviewed["may_request_approval"] is False
    assert reviewed["access_decision"] != "allowed"
    assert reviewed["network_executed"] is False
    assert reviewed["maximum_exact_requests"] == 5
    assert reviewed["bulk_acquisition_authorized"] is False
    assert not (tmp_path / "arcgis-bounded-proofs").exists()
    with pytest.raises(ValueError, match="denied"):
        execute_reviewed_original_arcgis_probe(tmp_path, {
            **choice, "expected_preview_digest": reviewed["expected_preview_digest"],
            "review_reason": "Manual reviewed source access is unknown",
            "caller_confirmation": True,
        })
    with pytest.raises(ValueError, match="sample"):
        preview_original_arcgis_probe(tmp_path, {
            **choice, "sample_size": 101,
        })


def test_native_original_arcgis_uses_original_service_and_retains_verifiable_bundle(
    tmp_path: Path,
) -> None:
    selected = _selection()
    preview = preview_original_arcgis_probe(tmp_path, selected)
    assert preview["may_request_approval"] is True
    approved = {
        **selected,
        "expected_preview_digest": preview["expected_preview_digest"],
        "review_reason": "Execute one reviewed original bounded ArcGIS proof",
        "caller_confirmation": True,
    }
    with pytest.raises(ValueError, match="stale"):
        execute_reviewed_original_arcgis_probe(tmp_path, {
            **approved, "expected_preview_digest": "0" * 64,
        })
    bundle = _original_bundle()
    fake = SimpleNamespace(
        bundle=bundle,
        authorization=SimpleNamespace(
            decision=SimpleNamespace(audit_identity="original:parcel-operator-review"),
        ),
    )
    with patch(
        "constructionsight.command_center_arcgis_probe.execute_authorized_arcgis_probe",
        return_value=fake,
    ) as executor:
        receipt = execute_reviewed_original_arcgis_probe(tmp_path, approved)
    assert executor.call_count == 1
    assert executor.call_args.kwargs["sample_size"] == 2
    assert executor.call_args.kwargs["timeout_seconds"] == 15.0
    assert executor.call_args.kwargs["caller_confirmation"] is True
    assert receipt["retained_proof_written"] is True
    assert receipt["native_proof_persisted"] is False
    assert receipt["bulk_acquisition_authorized"] is False
    retained = Path(receipt["retained_proof_path"])
    assert retained.is_file()
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == receipt[
        "bundle_sha256"
    ]
    assert json.loads(retained.read_text())["network_request_count"] == 5
    independently_reviewed = retained_arcgis_proof_preview(retained)
    assert independently_reviewed["bundle_id"] == bundle.bundle_id
    assert independently_reviewed["available"] is True
    assert preview_original_arcgis_probe(tmp_path, selected)["may_request_approval"] is False
    with pytest.raises(ValueError, match="already retained"):
        execute_reviewed_original_arcgis_probe(tmp_path, approved)


def test_original_arcgis_native_http_denies_forgery_and_unapproved_execution(
    tmp_path: Path,
) -> None:
    server = make_server(snapshot(), 0, tmp_path)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            forged = client.post(
                "/api/parcel-arcgis-probe-preview", json=_selection(),
                headers={"Origin": "https://malicious.invalid"},
            )
            assert forged.status_code == 403
            denied = client.post(
                "/api/parcel-arcgis-probe-preview", json=_selection(False),
                headers={"Origin": host},
            )
            assert denied.status_code == 200, denied.text
            assert denied.json()["may_request_approval"] is False
            assert client.post(
                "/api/parcel-arcgis-probe", json={
                    **_selection(),
                    "expected_preview_digest": "0" * 64,
                    "review_reason": "Reviewed exact original ArcGIS source",
                    "caller_confirmation": False,
                }, headers={"Origin": host},
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        worker.join()



def test_native_original_arcgis_positive_http_selects_new_proof_without_import(
    tmp_path: Path,
) -> None:
    """One same-origin consented original proof feeds the existing offline path."""
    bundle = _original_bundle()
    source_effect = SimpleNamespace(
        bundle=bundle,
        authorization=SimpleNamespace(
            decision=SimpleNamespace(audit_identity="original:approved-arcgis"),
        ),
    )
    server = make_server(snapshot(), 0, tmp_path)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            original_view = client.get("/api/parcel-arcgis-proof")
            assert original_view.status_code == 200
            assert original_view.json()["available"] is False
            reviewed = client.post(
                "/api/parcel-arcgis-probe-preview",
                json=_selection(), headers={"Origin": host},
            )
            assert reviewed.status_code == 200, reviewed.text
            proof = reviewed.json()
            assert proof["may_request_approval"] is True
            with patch(
                "constructionsight.command_center_arcgis_probe."
                "execute_authorized_arcgis_probe",
                return_value=source_effect,
            ) as original_executor:
                applied = client.post(
                    "/api/parcel-arcgis-probe", json={
                        **_selection(),
                        "expected_preview_digest": proof["expected_preview_digest"],
                        "review_reason": "Single independently reviewed bounded ArcGIS source",
                        "caller_confirmation": True,
                    },
                    headers={"Origin": host},
                )
            assert applied.status_code == 200, applied.text
            assert original_executor.call_count == 1
            assert applied.json()["bundle_id"] == bundle.bundle_id
            selected = client.get("/api/parcel-arcgis-proof")
            assert selected.status_code == 200, selected.text
            assert selected.json()["available"] is True
            assert selected.json()["bundle_id"] == bundle.bundle_id
            # Reviewed source proof alone must not mutate the shared parcel/
            # site/graph identity database or create an import.
            assert not (tmp_path / "investigations.sqlite3").exists()
            assert applied.json()["native_proof_persisted"] is False
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
