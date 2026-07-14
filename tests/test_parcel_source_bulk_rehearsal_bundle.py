from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_bulk_rehearsal import (
    JSONFileParcelArcGISCheckpointStore,
    execute_arcgis_complete_rehearsal,
)
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    JSONFileParcelArcGISBulkArtifactStore,
    ParcelArcGISBulkCountResponse,
    ParcelArcGISBulkPageResponse,
)
from constructionsight.parcel_source_bulk_rehearsal_bundle import (
    build_arcgis_bulk_rehearsal_proof_bundle,
    load_arcgis_bulk_rehearsal_proof_bundle,
    save_arcgis_bulk_rehearsal_proof_bundle,
    verify_arcgis_bulk_rehearsal_proof_bundle,
)
from constructionsight.parcel_source_bulk_rehearsal_bundle_models import (
    ParcelArcGISBulkRehearsalProofBundle,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    build_arcgis_bulk_rehearsal_plan,
)

_NOW = datetime(2026, 7, 14, 22, 0, tzinfo=UTC)


@dataclass
class _Clock:
    value: datetime = _NOW

    def __call__(self) -> datetime:
        current = self.value
        self.value = self.value + timedelta(seconds=1)
        return current


@dataclass
class _Source:
    count_bodies: list[bytes]
    page_bodies: dict[int, bytes]

    def fetch_count(self) -> ParcelArcGISBulkCountResponse:
        body = self.count_bodies.pop(0)
        return ParcelArcGISBulkCountResponse(count=6, response_body=body)

    def fetch_object_id_page(
        self,
        *,
        offset: int,
        record_count: int,
        attempt_number: int,
    ) -> ParcelArcGISBulkPageResponse:
        assert record_count == 2
        assert 1 <= attempt_number <= 3
        return ParcelArcGISBulkPageResponse(response_body=self.page_bodies[offset])


def _completed_rehearsal(tmp_path: Path):
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_bulk_rehearsal_plan(
        snapshot,
        generated_at=_NOW,
        page_size=2,
        checkpoint_after_pages=1,
        injected_retry_page_index=1,
        max_attempts=3,
        retry_delays_seconds=(0.0, 0.0),
    )
    artifact_store = JSONFileParcelArcGISBulkArtifactStore(tmp_path / "responses")
    execution = execute_arcgis_complete_rehearsal(
        snapshot,
        _Source(
            count_bodies=[b'{  "count" : 6 }\n', b'{"count":6}\n'],
            page_bodies={
                0: b'{ "objectIds" : [1, 2] }\n',
                2: b'{"objectIds":[3,4]}\n',
                4: b'{"objectIds":[5,6]}\n',
            },
        ),
        JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
        artifact_store,
        policy=plan.rehearsal_policy,
        now=_Clock(),
        sleep=lambda _delay: None,
    )
    return snapshot, plan, execution, artifact_store


def test_bundle_embeds_exact_responses_and_verifies_offline(tmp_path: Path) -> None:
    snapshot, plan, execution, artifact_store = _completed_rehearsal(tmp_path)

    bundle = build_arcgis_bulk_rehearsal_proof_bundle(
        snapshot,
        plan,
        execution,
        artifact_store,
        created_at=_NOW + timedelta(minutes=1),
    )
    verification = verify_arcgis_bulk_rehearsal_proof_bundle(
        bundle,
        verified_at=_NOW + timedelta(minutes=2),
    )

    assert bundle.bundle_id.startswith("parcel-arcgis-bulk-rehearsal-proof-bundle:")
    assert bundle.bulk_run_authorized is False
    assert bundle.checkpoint_reloaded is True
    assert len(bundle.artifacts) == execution.manifest.page_count + 2
    assert bundle.artifacts[0].response_body() == b'{  "count" : 6 }\n'
    assert bundle.artifacts[1].response_body() == b'{ "objectIds" : [1, 2] }\n'
    assert bundle.artifacts[-1].response_body() == b'{"count":6}\n'
    assert verification.valid is True
    assert verification.plan_recomputed is True
    assert verification.manifest_recomputed is True
    assert verification.response_bytes_recomputed is True
    assert verification.object_ids_recomputed is True
    assert verification.bulk_run_authorized is False


def test_bundle_json_round_trip_and_exact_replay_save(tmp_path: Path) -> None:
    snapshot, plan, execution, artifact_store = _completed_rehearsal(tmp_path)
    bundle = build_arcgis_bulk_rehearsal_proof_bundle(
        snapshot,
        plan,
        execution,
        artifact_store,
        created_at=_NOW + timedelta(minutes=1),
    )
    path = tmp_path / "portable" / "rehearsal-proof.json"

    save_arcgis_bulk_rehearsal_proof_bundle(
        bundle,
        path,
        expected_bundle_id=bundle.bundle_id,
    )
    first_bytes = path.read_bytes()
    save_arcgis_bulk_rehearsal_proof_bundle(
        bundle,
        path,
        expected_bundle_id=bundle.bundle_id,
    )
    loaded = load_arcgis_bulk_rehearsal_proof_bundle(path)

    assert path.read_bytes() == first_bytes
    assert loaded == bundle
    assert ParcelArcGISBulkRehearsalProofBundle.model_validate_json(
        json.dumps(bundle.to_dict())
    ) == bundle


def test_bundle_rejects_embedded_response_tampering(tmp_path: Path) -> None:
    snapshot, plan, execution, artifact_store = _completed_rehearsal(tmp_path)
    bundle = build_arcgis_bulk_rehearsal_proof_bundle(
        snapshot,
        plan,
        execution,
        artifact_store,
        created_at=_NOW + timedelta(minutes=1),
    )
    payload = bundle.to_dict()
    payload["artifacts"][1]["response_body_base64"] = base64.b64encode(
        b'{"objectIds":[1,9]}\n'
    ).decode("ascii")

    with pytest.raises(ValueError, match="digest|body|evidence"):
        ParcelArcGISBulkRehearsalProofBundle.model_validate(payload)


def test_bundle_rejects_plan_manifest_and_sequence_disagreement(tmp_path: Path) -> None:
    snapshot, plan, execution, artifact_store = _completed_rehearsal(tmp_path)
    bundle = build_arcgis_bulk_rehearsal_proof_bundle(
        snapshot,
        plan,
        execution,
        artifact_store,
        created_at=_NOW + timedelta(minutes=1),
    )

    plan_payload = bundle.to_dict()
    plan_payload["plan"]["page_size"] = 3
    with pytest.raises(ValueError, match="plan|page size|identity"):
        ParcelArcGISBulkRehearsalProofBundle.model_validate(plan_payload)

    manifest_payload = bundle.to_dict()
    manifest_payload["manifest"]["starting_count"] = 7
    with pytest.raises(ValueError, match="count|manifest"):
        ParcelArcGISBulkRehearsalProofBundle.model_validate(manifest_payload)

    sequence_payload = bundle.to_dict()
    sequence_payload["artifacts"][1]["sequence_index"] = 9
    with pytest.raises(ValueError, match="sequence"):
        ParcelArcGISBulkRehearsalProofBundle.model_validate(sequence_payload)


def test_bundle_save_requires_exact_identity_and_rejects_conflict(tmp_path: Path) -> None:
    snapshot, plan, execution, artifact_store = _completed_rehearsal(tmp_path)
    bundle = build_arcgis_bulk_rehearsal_proof_bundle(
        snapshot,
        plan,
        execution,
        artifact_store,
        created_at=_NOW + timedelta(minutes=1),
    )
    path = tmp_path / "proof.json"

    with pytest.raises(ValueError, match="expected bundle identity"):
        save_arcgis_bulk_rehearsal_proof_bundle(
            bundle,
            path,
            expected_bundle_id="parcel-arcgis-bulk-rehearsal-proof-bundle:" + ("0" * 64),
        )

    save_arcgis_bulk_rehearsal_proof_bundle(
        bundle,
        path,
        expected_bundle_id=bundle.bundle_id,
    )
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid|conflicting"):
        save_arcgis_bulk_rehearsal_proof_bundle(
            bundle,
            path,
            expected_bundle_id=bundle.bundle_id,
        )


def test_bundle_rejects_unsafe_artifact_reference(tmp_path: Path) -> None:
    snapshot, plan, execution, artifact_store = _completed_rehearsal(tmp_path)
    bundle = build_arcgis_bulk_rehearsal_proof_bundle(
        snapshot,
        plan,
        execution,
        artifact_store,
        created_at=_NOW + timedelta(minutes=1),
    )
    payload = bundle.to_dict()
    payload["artifacts"][0]["artifact_reference"] = "../count.json"

    with pytest.raises(ValueError, match="reference"):
        ParcelArcGISBulkRehearsalProofBundle.model_validate(payload)
