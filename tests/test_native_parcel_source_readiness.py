"""Native parcel/GIS source evidence is the original operator view, not a second registry."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from constructionsight.command_center_parcel_readiness import (
    parcel_source_readiness_snapshot,
    preview_retained_parcel_sample,
)
from constructionsight.parcel_schema_preview import preview_schema_for_source_key
from constructionsight.parcel_source_registry import get_parcel_sources
from constructionsight.parcel_source_verification import get_parcel_source_evidence
from tests.test_native_source_inspection import _native


def test_native_parcel_registry_schema_and_verified_source_evidence_are_exact_and_offline(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "private"
    expected = parcel_source_readiness_snapshot()
    sources = get_parcel_sources()
    assert len(sources) == 4
    assert set(expected["schemas"]) == {source.source_key for source in sources}
    assert expected["network_executed"] is False
    assert expected["parcel_source_persisted"] is False
    assert expected["identity_independently_verified"] is False
    assert expected["commercial_authority_granted"] is False
    assert expected["evidence"] == [
        source.to_dict() for source in get_parcel_source_evidence()
    ]
    assert expected["schemas"][sources[0].source_key] == (
        preview_schema_for_source_key(sources[0].source_key).model_dump(
            mode="json", exclude={"created_at"}
        )
    )
    server, worker = _native(directory)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            result = client.get("/api/parcel-source-readiness")
            assert result.status_code == 200, result.text
            actual = result.json()
            # The original coverage service timestamps each fresh assessment.
            # All evidence, gaps and IDs must match, but generated_at is not
            # a fixed historical source-observation timestamp.
            assert actual["county_coverage"].pop("generated_at")
            expected["county_coverage"].pop("generated_at")
            # Registry report uses created_at, unlike coverage's generated_at.
            assert actual["registry_report"].pop("created_at")
            expected["registry_report"].pop("created_at")
            assert actual == expected
            assert json.loads(result.content)["county_coverage"]["generated_at"]
            assert client.get("/api/parcel-source-readiness?source_key=not-allowed"
                              ).status_code == 409
            assert client.get("/api/parcel-source-readiness?source_key="
                              ).status_code == 409
            assert client.post("/api/parcel-source-readiness", json={}
                               ).status_code in {403, 404}
            assert not (directory / "investigations.sqlite3").exists()
            assert not (directory / "constructionsight.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_original_parcel_row_sample_preview_requires_exact_verified_source_and_does_not_persist(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "private"
    source = get_parcel_sources()[0]
    valid = {"source_key": source.source_key, "rows": [{"ParcelNumber": "123-456-789"}]}
    original = preview_retained_parcel_sample(valid)
    assert original["manual_unverified_sample"] is True
    assert original["rows_retained"] is False
    assert original["network_executed"] is False
    assert original["report"]["row_count"] == 1
    assert original["report"]["usable_row_count"] == 1
    assert original["report"]["rows"][0]["normalized_apn"] is not None

    server, worker = _native(directory)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            endpoint = "/api/parcel-source-row-preview"
            assert client.post(endpoint, json=valid).status_code == 403
            accepted = client.post(endpoint, json=valid, headers={"Origin": base})
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["report"]["rows"] == original["report"]["rows"]
            assert accepted.json()["commercial_authority_granted"] is False
            for bad in (
                {**valid, "source_key": "regrid:licensed-parcel-provider"},
                {**valid, "extra": "not part of the original review contract"},
                {**valid, "rows": [{"InventedField": "synthetic"}]},
                {**valid, "rows": [{"ParcelNumber": 100}]},
                {**valid, "rows": []},
                {**valid, "rows": [{"ParcelNumber": "a"}] * 21},
                {**valid, "rows": [{"ParcelNumber": "x" * 33_000}]},
            ):
                response = client.post(endpoint, json=bad, headers={"Origin": base})
                assert response.status_code == 400, (bad, response.text)
            assert client.post(endpoint+"?allow=1", json=valid,
                               headers={"Origin":base}).status_code == 400
            assert not (directory / "investigations.sqlite3").exists()
            assert not (directory / "constructionsight.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()



def test_original_arcgis_persisted_proof_chain_is_visible_and_unchanged_from_native(
    tmp_path: Path,
) -> None:
    from sqlalchemy.orm import Session

    from constructionsight.storage.database import create_database_engine, initialize_database
    from constructionsight.storage.parcel_source_acquisition_bundle_store import (
        store_arcgis_bounded_proof_bundle_chain,
    )
    from tests.test_parcel_source_acquisition_bundle_storage import _bounded_bundle

    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    bundle = _bounded_bundle()
    with Session(engine) as session, session.begin():
        store_arcgis_bounded_proof_bundle_chain(session, bundle)
    engine.dispose()
    before = database.read_bytes()
    directory = tmp_path / "private"
    server, worker = _native(directory, operator_database=database)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            response = client.get("/api/source-parcel-proofs")
            assert response.status_code == 200, response.text
            report = response.json()
            assert report["available"] is True
            assert report["total"] == 1
            assert report["proof_chain_validated"] is True
            assert report["network_collection_enabled"] is False
            assert report["bulk_acquisition_authorized"] is False
            assert report["identity_independently_verified"] is False
            assert report["commercial_actions_authorized"] is False
            assert report["bundles"] == [bundle.to_dict()]
            assert client.get("/api/source-parcel-proofs?kind=parcel").status_code == 409
            assert client.get("/api/source-parcel-proofs").json() == report
            assert database.read_bytes() == before
            assert not (directory / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_native_arcgis_proof_listing_rejects_corrupt_original_index_without_writing(
    tmp_path: Path,
) -> None:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from constructionsight.storage.database import create_database_engine, initialize_database
    from constructionsight.storage.parcel_source_acquisition_bundle_store import (
        store_arcgis_bounded_proof_bundle_chain,
    )
    from tests.test_parcel_source_acquisition_bundle_storage import _bounded_bundle

    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        store_arcgis_bounded_proof_bundle_chain(session, _bounded_bundle())
    with Session(engine) as session, session.begin():
        session.execute(text(
            "UPDATE parcel_arcgis_bounded_proof_bundles SET county='Altered County'"
        ))
    engine.dispose()
    before = database.read_bytes()
    directory = tmp_path / "private"
    server, worker = _native(directory, operator_database=database)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            response = client.get("/api/source-parcel-proofs")
            assert response.status_code == 409
            assert "indexed fields disagree" in response.text
            assert database.read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_native_arcgis_proof_listing_never_invents_unconfigured_history(
    tmp_path: Path,
) -> None:
    server, worker = _native(tmp_path / "private")
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False
        ) as client:
            response = client.get("/api/source-parcel-proofs")
            assert response.status_code == 200
            assert response.json()["available"] is False
            assert "total" not in response.json()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
