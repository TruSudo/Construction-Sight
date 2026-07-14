from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from constructionsight.parcel_source_acquisition import build_arcgis_bulk_manifest
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISBulkManifest,
    digest_identity,
    digest_json_payload,
)
from constructionsight.parcel_source_bulk_rehearsal_models import (
    ParcelArcGISBulkRehearsalEvidence,
    assemble_arcgis_bulk_rehearsal_evidence,
)
from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)

_OBSERVED_AT = datetime(2026, 7, 14, 19, 0, tzinfo=UTC)


def _evidence():
    snapshot = get_official_arcgis_capability_snapshots()[0]
    evidence = assemble_arcgis_bulk_rehearsal_evidence(
        snapshot,
        page_size=2,
        page_object_ids=((1, 3), (5, 7), (9, 11)),
        page_response_digests=tuple(
  digest_json_payload({"page": value}) for value in range(3)
        ),
        page_attempt_counts=(1, 2, 1),
        page_observed_at=(
  _OBSERVED_AT,
  _OBSERVED_AT + timedelta(seconds=30),
  _OBSERVED_AT + timedelta(minutes=2),
        ),
        checkpoint_completed_page_count=1,
        checkpoint_created_at=_OBSERVED_AT + timedelta(seconds=10),
        resumed_at=_OBSERVED_AT + timedelta(seconds=20),
        retry_page_index=1,
        retry_failure_kind="injected_pre_request_transient",
        retry_failed_attempt_count=1,
        retry_fault_injected=True,
        retry_recorded_at=_OBSERVED_AT + timedelta(seconds=25),
        created_at=_OBSERVED_AT + timedelta(minutes=3),
    )
    return snapshot, evidence


def test_structured_rehearsal_evidence_recomputes_manifest_summaries() -> None:
    snapshot, evidence = _evidence()
    manifest = build_arcgis_bulk_manifest(
        snapshot,
        started_at=_OBSERVED_AT,
        completed_at=_OBSERVED_AT + timedelta(minutes=4),
        starting_count=6,
        ending_count=6,
        rehearsal_evidence=evidence,
    )

    assert manifest.page_count == 3
    assert manifest.retrieved_count == 6
    assert manifest.unique_object_id_count == 6
    assert manifest.duplicate_object_id_count == 0
    assert manifest.checkpoint_resume_verified is True
    assert manifest.retry_recovery_verified is True
    assert manifest.rehearsal_evidence == evidence


def test_manifest_rejects_summary_claims_that_disagree_with_evidence() -> None:
    snapshot, evidence = _evidence()
    manifest = build_arcgis_bulk_manifest(
        snapshot,
        started_at=_OBSERVED_AT,
        completed_at=_OBSERVED_AT + timedelta(minutes=4),
        starting_count=6,
        ending_count=6,
        rehearsal_evidence=evidence,
    )
    payload = manifest.to_dict()
    payload["retrieved_count"] = 7
    identity_payload = {key: value for key, value in payload.items() if key != "manifest_id"}
    payload["manifest_id"] = digest_identity(
        "parcel-arcgis-bulk-manifest",
        identity_payload,
    )

    with pytest.raises(ValidationError, match="retrieved count mismatch|reconcile"):
        ParcelArcGISBulkManifest.model_validate(payload)


def test_legacy_boolean_only_manifest_payload_is_rejected() -> None:
    snapshot, evidence = _evidence()
    manifest = build_arcgis_bulk_manifest(
        snapshot,
        started_at=_OBSERVED_AT,
        completed_at=_OBSERVED_AT + timedelta(minutes=4),
        starting_count=6,
        ending_count=6,
        rehearsal_evidence=evidence,
    )
    payload = manifest.to_dict()
    payload.pop("rehearsal_evidence")

    with pytest.raises(ValidationError, match="rehearsal_evidence"):
        ParcelArcGISBulkManifest.model_validate(payload)


def test_rehearsal_evidence_rejects_checkpoint_and_retry_tampering() -> None:
    _, evidence = _evidence()
    checkpoint_payload = evidence.checkpoint.to_dict()
    checkpoint_payload["object_id_count"] = 99
    evidence_payload = evidence.to_dict()
    evidence_payload["checkpoint"] = checkpoint_payload

    with pytest.raises(ValidationError, match="checkpoint|object-ID"):
        ParcelArcGISBulkRehearsalEvidence.model_validate(evidence_payload)

    retry_payload = evidence.retry_events[0].to_dict()
    retry_payload["recovered_response_digest"] = "0" * 64
    evidence_payload = evidence.to_dict()
    evidence_payload["retry_events"] = [retry_payload]

    with pytest.raises(ValidationError, match="retry|response digest"):
        ParcelArcGISBulkRehearsalEvidence.model_validate(evidence_payload)
