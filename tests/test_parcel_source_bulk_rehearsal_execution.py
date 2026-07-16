from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_bulk_rehearsal import (
    JSONFileParcelArcGISCheckpointStore,
    ParcelArcGISBulkRehearsalPolicy,
    execute_arcgis_complete_rehearsal,
)
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    JSONFileParcelArcGISBulkArtifactStore,
    ParcelArcGISBulkCountResponse,
    ParcelArcGISBulkPageResponse,
)


class _Clock:
    def __init__(self) -> None:
        self._value = datetime(2026, 7, 14, 21, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        value = self._value
        self._value += timedelta(seconds=1)
        return value


class _Source:
    def __init__(self) -> None:
        self._counts = [4, 4]
        self._pages = {0: (1, 2), 2: (3, 4)}

    def fetch_count(self) -> ParcelArcGISBulkCountResponse:
        return ParcelArcGISBulkCountResponse.from_count(self._counts.pop(0))

    def fetch_object_id_page(
        self,
        *,
        offset: int,
        record_count: int,
        attempt_number: int,
    ) -> ParcelArcGISBulkPageResponse:
        assert record_count == 2
        assert attempt_number in {1, 2}
        return ParcelArcGISBulkPageResponse.from_payload({"objectIds": list(self._pages[offset])})


def test_execution_binds_count_response_digests_to_retained_receipts(
    tmp_path: Path,
) -> None:
    execution = execute_arcgis_complete_rehearsal(
        get_official_arcgis_capability_snapshots()[0],
        _Source(),
        JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
        JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
        policy=ParcelArcGISBulkRehearsalPolicy(
            page_size=2,
            checkpoint_after_pages=1,
            injected_retry_page_index=1,
            retry_delays_seconds=(0.0, 0.0),
        ),
        now=_Clock(),
        sleep=lambda _: None,
    )

    assert (
        execution.starting_count_response_digest == execution.artifact_receipts[0].response_digest
    )
    assert execution.ending_count_response_digest == execution.artifact_receipts[-1].response_digest

    with pytest.raises(ValueError, match="starting-count artifact"):
        replace(execution, starting_count_response_digest="0" * 64)
