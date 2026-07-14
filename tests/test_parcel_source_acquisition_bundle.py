import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from constructionsight.parcel_source_acquisition import (
    build_arcgis_acquisition_assessment,
    build_arcgis_probe_plan,
    get_official_arcgis_capability_snapshots,
    parse_arcgis_probe_observation,
)
from constructionsight.parcel_source_acquisition_bundle import (
    build_arcgis_bounded_proof_bundle,
    build_arcgis_proof_persistence_receipt,
    load_arcgis_bounded_proof_bundle,
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_bundle_models import (
    ParcelArcGISBoundedProofBundle,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionStatus,
    ParcelArcGISProbeKind,
)
from constructionsight.parcel_source_verification import (
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)

_OBSERVED_AT = datetime(2026, 7, 14, 18, 0, tzinfo=UTC)


def _bounded_bundle(*, replay_ids: tuple[int, ...] = (1, 3)):
    snapshot = get_official_arcgis_capability_snapshots()[0]
    profile = next(
        item
        for item in get_verified_parcel_source_profiles()
        if item.profile_id == snapshot.profile_id
    )
    evidence_by_id = {
        item.evidence_id: item for item in get_parcel_source_evidence()
    }
    plan = build_arcgis_probe_plan(snapshot, generated_at=_OBSERVED_AT)
    response_by_kind = {
        ParcelArcGISProbeKind.COUNT: {"count": 6},
        ParcelArcGISProbeKind.INITIAL_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 1}},
                {"attributes": {"OBJECTID": 3}},
            ],
            "exceededTransferLimit": True,
        },
        ParcelArcGISProbeKind.NEXT_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": 5}},
                {"attributes": {"OBJECTID": 7}},
            ],
            "exceededTransferLimit": True,
        },
        ParcelArcGISProbeKind.REPLAY_PAGE: {
            "features": [
                {"attributes": {"OBJECTID": object_id}}
                for object_id in replay_ids
            ],
            "exceededTransferLimit": True,
        },
    }
    observations = tuple(
        parse_arcgis_probe_observation(
            request,
            response_by_kind[request.kind],
            observed_at=_OBSERVED_AT,
        )
        for request in plan.requests
    )
    assessment = build_arcgis_acquisition_assessment(
        snapshot,
        plan,
        observations,
        generated_at=_OBSERVED_AT,
    )
    return build_arcgis_bounded_proof_bundle(
        profile,
        (evidence_by_id[evidence_id] for evidence_id in profile.evidence_ids),
        snapshot,
        plan,
        observations,
        assessment,
        created_at=_OBSERVED_AT,
    )


def test_bundle_is_portable_backward_compatible_and_offline_verifiable() -> None:
    bundle = _bounded_bundle()
    verification = verify_arcgis_bounded_proof_bundle(
        bundle,
        verified_at=_OBSERVED_AT,
    )

    assert bundle.bundle_id.startswith("parcel-arcgis-bounded-proof-bundle:")
    assert bundle.assessment.status == ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED
    assert bundle.network_request_count == 5
    assert bundle.bulk_run_authorized is False
    assert {"snapshot", "plan", "observations", "assessment"} <= bundle.to_dict().keys()
    assert verification.valid is True
    assert verification.assessment_recomputed is True
    assert verification.response_digests_recomputed is True
    assert verification.bulk_run_authorized is False


def test_bundle_requires_exact_profile_evidence_and_canonical_plan_order() -> None:
    bundle = _bounded_bundle()

    with pytest.raises(ValidationError, match="evidence must exactly satisfy"):
        ParcelArcGISBoundedProofBundle.model_validate(
            {
                **bundle.to_dict(),
                "source_evidence": bundle.to_dict()["source_evidence"][:-1],
            }
        )

    reversed_observations = list(reversed(bundle.to_dict()["observations"]))
    with pytest.raises(ValidationError, match="follow the plan order"):
        ParcelArcGISBoundedProofBundle.model_validate(
            {
                **bundle.to_dict(),
                "observations": reversed_observations,
            }
        )


def test_bundle_rejects_response_tampering_before_offline_verification() -> None:
    bundle = _bounded_bundle()
    payload = bundle.to_dict()
    payload["observations"][0]["response_payload_json"] = '{"count":7}'

    with pytest.raises(ValidationError, match="response digest"):
        ParcelArcGISBoundedProofBundle.model_validate(payload)


def test_blocked_probe_is_preserved_without_bulk_authority() -> None:
    bundle = _bounded_bundle(replay_ids=(1, 4))
    verification = verify_arcgis_bounded_proof_bundle(bundle)

    assert bundle.assessment.status == ParcelArcGISAcquisitionStatus.BLOCKED
    assert verification.status == ParcelArcGISAcquisitionStatus.BLOCKED
    assert verification.bulk_run_authorized is False
    assert "resolve its explicit assessment gaps" in verification.next_action


def test_bundle_file_loader_recomputes_and_rejects_drift(tmp_path: Path) -> None:
    bundle = _bounded_bundle()
    bundle_path = tmp_path / "bounded-proof.json"
    bundle_path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")

    assert load_arcgis_bounded_proof_bundle(bundle_path) == bundle

    payload = bundle.to_dict()
    payload["limitations"] = ["Substituted limitation"]
    bundle_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid ArcGIS bounded-proof bundle"):
        load_arcgis_bounded_proof_bundle(bundle_path)


def test_persistence_receipt_binds_exact_bundle_and_remains_bounded() -> None:
    bundle = _bounded_bundle()
    receipt = build_arcgis_proof_persistence_receipt(
        bundle,
        persisted_at=_OBSERVED_AT,
    )

    assert receipt.bundle_id == bundle.bundle_id
    assert receipt.mutation_authorized is True
    assert receipt.replay_policy == "insert_or_exact_replay"
    assert receipt.bulk_run_authorized is False
    assert receipt.observation_ids == tuple(sorted(receipt.observation_ids))
