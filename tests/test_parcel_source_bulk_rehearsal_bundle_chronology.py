from __future__ import annotations

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
    verify_arcgis_bulk_rehearsal_proof_bundle,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    build_arcgis_bulk_rehearsal_plan,
)

_NOW = datetime(2026, 7, 14, 23, 0, tzinfo=UTC)


@dataclass
class _Clock:
    value: datetime = _NOW

    def __call__(self) -> datetime:
        current = self.value
        self.value = self.value + timedelta(seconds=1)
        return current


@dataclass
class _Source:
    counts_remaining: int = 2

    def fetch_count(self) -> ParcelArcGISBulkCountResponse:
        if self.counts_remaining < 1:
            raise AssertionError("unexpected count request")
        self.counts_remaining -= 1
        return ParcelArcGISBulkCountResponse.from_count(6)

    def fetch_object_id_page(
        self,
        *,
        offset: int,
        record_count: int,
        attempt_number: int,
    ) -> ParcelArcGISBulkPageResponse:
        assert record_count == 2
        assert 1 <= attempt_number <= 3
        pages = {
            0: [1, 2],
            2: [3, 4],
            4: [5, 6],
        }
        return ParcelArcGISBulkPageResponse.from_payload({"objectIds": pages[offset]})


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
        _Source(),
        JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
        artifact_store,
        policy=plan.rehearsal_policy,
        now=_Clock(),
        sleep=lambda _delay: None,
    )
    return snapshot, plan, execution, artifact_store


def test_bundle_binds_creation_and_verification_chronology(tmp_path: Path) -> None:
    snapshot, plan, execution, artifact_store = _completed_rehearsal(tmp_path)

    with pytest.raises(ValueError, match="created_at cannot precede"):
        build_arcgis_bulk_rehearsal_proof_bundle(
            snapshot,
            plan,
            execution,
            artifact_store,
            created_at=execution.manifest.completed_at - timedelta(seconds=1),
        )

    bundle = build_arcgis_bulk_rehearsal_proof_bundle(
        snapshot,
        plan,
        execution,
        artifact_store,
        created_at=execution.manifest.completed_at + timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="verification time cannot precede"):
        verify_arcgis_bulk_rehearsal_proof_bundle(
            bundle,
            verified_at=bundle.created_at - timedelta(seconds=1),
        )
