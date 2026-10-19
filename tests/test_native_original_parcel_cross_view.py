"""Reviewed original parcel evidence uses one persistent map/dossier/graph reality.

Only an exact approved original source observation is queued. A declared
geodetic centroid may appear as a *source claim*; never a verified site or lead.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from constructionsight.investigation_runtime import InvestigationRuntime
from constructionsight.parcel_core_models import ParcelGeometry, ParcelGeometryKind
from constructionsight.storage.database import create_database_engine
from constructionsight.storage.parcel_site_store import store_parcel_core_record
from tests.test_native_original_parcel_reconciliation import _parcel_database
from tests.test_native_source_inspection import _native


def test_exact_original_parcel_replay_drives_one_source_claimed_point_across_views(
    tmp_path: Path,
) -> None:
    database, previous = _parcel_database(tmp_path)
    parcel = previous.model_copy(update={
        "geometry": ParcelGeometry(
            geometry_kind=ParcelGeometryKind.POINT,
            centroid_latitude=34.1,
            centroid_longitude=-117.3,
            spatial_reference="EPSG:4326",
        ),
    })
    engine = create_database_engine(f"sqlite:///{database}")
    try:
        with Session(engine) as session, session.begin():
            store_parcel_core_record(session, parcel)
    finally:
        engine.dispose()
    unchanged_original_bytes = database.read_bytes()
    directory = tmp_path / "private"
    selection = {"parcel_record_id": parcel.parcel_record_id}
    canonical_id = None
    recorded_point = None
    recorded_nodes = None
    for iteration in (0, 1):
        server, thread = _native(directory, operator_database=database)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with httpx.Client(base_url=base, trust_env=False) as client:
                if iteration == 0:
                    preview = client.get(
                        "/api/source-parcel-reconciliation", params=selection
                    )
                    assert preview.status_code == 200, preview.text
                    state = preview.json()
                    assert state["replay_eligible"] is True
                    assert state["parcel_to_project_identity_verified"] is False
                    approved = client.post(
                        "/api/source-parcel-reconciliation-queue",
                        json={
                            **selection,
                            "expected_source_sha256": state["original_source"][
                                "source_sha256"
                            ],
                            "expected_native_evidence_id": None,
                            "action": "retain_missing",
                            "review_reason": (
                                "Review the original bounded geodetic parcel source claim."
                            ),
                            "caller_confirmation": True,
                        },
                        headers={"Origin": base},
                    )
                    assert approved.status_code == 200, approved.text
                    receipt = approved.json()
                    assert receipt["unverified_parcel_claim_only"] is True
                    assert receipt["outreach_authorized"] is False
                    assert receipt["bid_authorized"] is False
                    runtime = InvestigationRuntime(directory)
                    try:
                        assert runtime.process(max_jobs=100)["failed_jobs"] == 0
                    finally:
                        runtime.close()
                worker_bytes = (directory / "investigations.sqlite3").read_bytes()
                inventory = client.get("/api/investigations")
                assert inventory.status_code == 200, inventory.text
                listing = inventory.json()
                assert listing["total"] == 1
                assert listing["mapped_on_page"] == 1
                assert listing["unmapped_on_page"] == []
                assert len(listing["rows"]) == 1
                row = listing["rows"][0]
                assert row["source_records"] == [{
                    "source_name": parcel.source_key,
                    "source_family": "parcel",
                    "source_record_id": parcel.source_record_id,
                }]
                assert row["assessment"]["identity_independently_verified"] is False
                assert row["assessment"]["commercial_authority_granted"] is False
                assert len(row["points"]) == 1
                point = row["points"][0]
                assert point["certainty"] == "source_claimed"
                assert (point["latitude"], point["longitude"]) == (34.1, -117.3)
                if canonical_id is None:
                    canonical_id, recorded_point = row["investigation_id"], point
                assert row["investigation_id"] == canonical_id
                assert point == recorded_point
                dossier = client.get(
                    "/api/investigations/" + quote(canonical_id, safe="")
                )
                assert dossier.status_code == 200, dossier.text
                report = dossier.json()
                assert report["investigation"]["project_cluster_id"] == canonical_id
                assert report["source_claimed_points"] == [point]
                assert len(report["source_observations"]) == 1
                evidence = report["source_observations"][0]["evidence"]
                assert evidence["source_family"] == "parcel"
                assert evidence["source_record_id"] == parcel.source_record_id
                assert evidence["raw_observations"]["parcel_record"]["apn"] == parcel.apn
                assert report["assessment"]["commercial_authority_granted"] is False
                assert report["assessment"]["identity_independently_verified"] is False
                graph = client.get("/api/investigation-graph")
                assert graph.status_code == 200, graph.text
                graph_data = graph.json()
                assert graph_data["commercial_authority_granted"] is False
                node_ids = [node["id"] for node in graph_data["nodes"]]
                assert canonical_id in node_ids
                assert len(node_ids) == len(set(node_ids))
                if recorded_nodes is None:
                    recorded_nodes = node_ids
                assert node_ids == recorded_nodes
                assert client.get(
                    "/api/investigations", params={"source": "parcel", "location": "mapped"}
                ).json()["total"] == 1
                assert client.get(
                    "/api/investigations", params={"location": "unmapped"}
                ).json()["rows"] == []
                reviewed = client.get(
                    "/api/source-parcel-reconciliation", params=selection
                ).json()
                assert reviewed["canonical_investigation_id"] == canonical_id
                assert reviewed["native_state"] == "exact_observation_already_retained"
                assert database.read_bytes() == unchanged_original_bytes
                assert (directory / "investigations.sqlite3").read_bytes() == worker_bytes
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
