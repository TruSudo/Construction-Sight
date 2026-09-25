import json
from pathlib import Path

import pytest

from constructionsight.parcel_source_acquisition_bundle import (
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_bundle_io import (
    load_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionStatus,
    ParcelArcGISProbeKind,
)

_ROOT = Path(__file__).resolve().parents[1]
_EVIDENCE = _ROOT / "evidence" / "source_verification"

_CASES = (
    (
        "San Bernardino",
        "san-bernardino:county-gis-parcels",
        "san_bernardino",
        839_794,
        "parcel-arcgis-bounded-proof-bundle:"
        "c3edb797417fef70d4a34672193e53679c811d91e0cab58dd5aa44dd1101d2a1",
    ),
    (
        "Riverside",
        "riverside:county-gis-parcels",
        "riverside",
        846_251,
        "parcel-arcgis-bounded-proof-bundle:"
        "49c20754f092ac960601ee7d03a4bcc9ef0c1fb4c71deefa295c3863e151f3f5",
    ),
)


@pytest.mark.parametrize(
    ("county", "source_key", "file_prefix", "expected_count", "expected_bundle_id"),
    _CASES,
)
def test_retained_county_arcgis_bounded_proof_is_exact_and_offline_verifiable(
    county: str,
    source_key: str,
    file_prefix: str,
    expected_count: int,
    expected_bundle_id: str,
) -> None:
    bundle_path = _EVIDENCE / f"{file_prefix}_arcgis_bounded_proof_2026-07-14.json"
    verification_path = (
        _EVIDENCE
        / f"{file_prefix}_arcgis_bounded_proof_verification_2026-07-14.json"
    )
    receipt_path = (
        _EVIDENCE
        / f"{file_prefix}_arcgis_bounded_proof_persistence_2026-07-14.json"
    )

    bundle = load_arcgis_bounded_proof_bundle(bundle_path)
    recomputed = verify_arcgis_bounded_proof_bundle(bundle)
    retained_verification = json.loads(verification_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    observations = {observation.kind: observation for observation in bundle.observations}
    initial = observations[ParcelArcGISProbeKind.INITIAL_PAGE]
    adjacent = observations[ParcelArcGISProbeKind.NEXT_PAGE]
    replay = observations[ParcelArcGISProbeKind.REPLAY_PAGE]

    assert bundle.bundle_id == expected_bundle_id
    assert bundle.county == county
    assert bundle.source_key == source_key
    assert bundle.network_request_count == 5
    assert bundle.assessment.status == ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED
    assert bundle.assessment.expected_record_count == expected_count
    assert bundle.assessment.bulk_acquisition_verified is False
    assert bundle.bulk_run_authorized is False
    assert len(bundle.observations) == 4

    assert initial.object_ids == (1, 2)
    assert adjacent.object_ids == (3, 4)
    assert replay.object_ids == initial.object_ids
    assert replay.response_digest == initial.response_digest

    assert recomputed.valid is True
    assert recomputed.assessment_recomputed is True
    assert recomputed.response_digests_recomputed is True
    assert recomputed.bulk_run_authorized is False

    assert retained_verification["bundle_id"] == expected_bundle_id
    assert retained_verification["valid"] is True
    assert retained_verification["status"] == "bounded_query_verified"
    assert retained_verification["network_request_count"] == 5
    assert retained_verification["bulk_run_authorized"] is False

    assert receipt["bundle_id"] == expected_bundle_id
    assert receipt["mutation_authorized"] is True
    assert receipt["replay_policy"] == "insert_or_exact_replay"
    assert receipt["bulk_run_authorized"] is False
    assert len(receipt["observation_ids"]) == 4
