"""One continuous offline P8-04 acceptance: source response to shared graph.

This test never connects to external ArcGIS. The approved HTTP operation is
replaced with a single synthetic response; all downstream native stores,
permissions, worker, dossier and graph handlers are the real implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import httpx

from constructionsight.command_center_arcgis_investigation import (
    enqueue_arcgis_parcel_investigation,
    preview_arcgis_parcel_investigation,
)
from constructionsight.command_center_arcgis_parcel import (
    apply_reviewed_arcgis_parcel,
    preview_reviewed_arcgis_parcel,
)
from constructionsight.command_center_arcgis_record import (
    execute_reviewed_arcgis_record,
    preview_reviewed_arcgis_record_access,
)
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    HttpFailureKind,
)
from constructionsight.investigation_runtime import InvestigationRuntime
from tests.test_native_arcgis_proof_persistence import _serve
from tests.test_native_arcgis_single_record_acquisition import (
    _access,
    _body,
    _fixture,
)


def test_full_reviewed_arcgis_record_to_original_parcel_to_shared_investigation(
    tmp_path: Path,
) -> None:
    proof, exact, plan = _fixture(tmp_path)
    directory = tmp_path / "native"
    review = {
        **exact, "expected_plan_id": plan["plan_id"], "access_review": _access(),
    }
    authorization = preview_reviewed_arcgis_record_access(proof, review)
    assert authorization["may_request_approval"] is True
    assert authorization["network_executed"] is False

    data = _body()
    observation = BoundedHttpObservation(
        policy_id="CS-NET-004",
        method="GET",
        request_url=plan["query_url"],
        final_url=plan["query_url"],
        status_code=200,
        content_type="application/json",
        content_encoding="utf-8",
        response_body=data,
        response_size=len(data),
        body_truncated=False,
        failure_kind=HttpFailureKind.NONE,
        error_type=None,
        error_detail=None,
    )
    requests: list[str] = []

    def one_owned_read(_auth: object, **kwargs: object) -> object:
        requests.append("one bounded approved effect")
        effect = kwargs["effect"]
        assert callable(effect)
        return effect(datetime(2026, 10, 22, tzinfo=UTC))

    with (
        patch(
            "constructionsight.command_center_arcgis_record."
            "authorize_local_operator_operation",
            return_value=object(),
        ),
        patch(
            "constructionsight.command_center_arcgis_record._execute_owned_effect",
            side_effect=one_owned_read,
        ),
        patch(
            "constructionsight.command_center_arcgis_record.execute_bounded_http",
            return_value=observation,
        ) as transport,
    ):
        acquired = execute_reviewed_arcgis_record(directory, proof, {
            **review,
            "review_reason": "Approve one synthetic, bounded official row response",
            "caller_confirmation": True,
        })
    assert requests == ["one bounded approved effect"]
    assert transport.call_count == 1
    assert acquired["source_attributes_observed"] is True
    assert acquired["parcel_persisted"] is False
    assert acquired["commercial_authority_granted"] is False

    exact_source = {
        **exact, "expected_plan_id": plan["plan_id"],
        "expected_response_sha256": acquired["response_sha256"],
    }
    original = (
        directory / "arcgis-record-evidence" / acquired["record_evidence_file"]
    ).read_bytes()
    parcel = preview_reviewed_arcgis_parcel(directory, proof, exact_source)
    assert parcel["native_state"] == "absent"
    assert parcel["geometry_verified"] is False
    assert parcel["may_request_persistence"] is True
    assert not (directory / "investigations.sqlite3").exists()
    retained = apply_reviewed_arcgis_parcel(directory, proof, {
        **exact_source,
        "expected_parcel_sha256": parcel["parcel_sha256"],
        "expected_native_state": parcel["native_state"],
        "review_reason": "Separately retain exact observed source parcel record",
        "caller_confirmation": True,
    })
    assert retained["parcel_persisted"] is True
    assert retained["native_worker_enqueued"] is False
    worker_payload = {
        **exact_source, "expected_parcel_sha256": parcel["parcel_sha256"],
    }
    handoff = preview_arcgis_parcel_investigation(
        directory, proof, worker_payload,
    )
    assert handoff["replay_eligible"] is True
    assert handoff["native_evidence_id"] is None
    assert handoff["commercial_authority_granted"] is False

    server, thread = _serve(directory, proof)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
        ) as client:
            assert client.get("/api/investigations").json()["total"] == 0
            queued = enqueue_arcgis_parcel_investigation(directory, proof, {
                **worker_payload,
                "expected_native_evidence_id": None,
                "action": "retain_missing",
                "review_reason": "Third independent approval for original parcel worker",
                "caller_confirmation": True,
            })
            assert queued["native_worker_required"] is True
            assert queued["commercial_authority_granted"] is False
            runtime = InvestigationRuntime(directory)
            try:
                result = runtime.process(max_jobs=100)
                assert result["failed_jobs"] == 0
                assert result["processed_jobs"] >= 1
                assert runtime.process(max_jobs=100)["processed_jobs"] == 0
            finally:
                runtime.close()
            inventory = client.get("/api/investigations", params={
                "source": "parcel", "location": "unmapped",
            })
            assert inventory.status_code == 200, inventory.text
            listing = inventory.json()
            assert listing["total"] == 1
            assert listing["mapped_on_page"] == 0
            row = listing["rows"][0]
            assert row["points"] == []
            assert row["assessment"]["identity_independently_verified"] is False
            assert row["assessment"]["commercial_authority_granted"] is False
            identity = row["investigation_id"]
            dossier = client.get("/api/investigations/" + identity)
            assert dossier.status_code == 200, dossier.text
            viewed = dossier.json()
            assert viewed["source_claimed_points"] == []
            assert viewed["assessment"]["commercial_authority_granted"] is False
            assert viewed["source_observations"][0]["evidence"][
                "source_record_id"
            ] == "3"
            graph = client.get("/api/investigation-graph")
            assert graph.status_code == 200, graph.text
            assert identity in [node["id"] for node in graph.json()["nodes"]]
            assert graph.json()["commercial_authority_granted"] is False
            again = preview_arcgis_parcel_investigation(
                directory, proof, worker_payload,
            )
            assert again["replay_eligible"] is False
            assert again["native_state"] == "exact_observation_already_retained"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert (
        directory / "arcgis-record-evidence" / acquired["record_evidence_file"]
    ).read_bytes() == original
