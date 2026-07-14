from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_bulk_rehearsal import (
    JSONFileParcelArcGISCheckpointStore,
    ParcelArcGISBulkRehearsalError,
    ParcelArcGISBulkRehearsalPolicy,
    ParcelArcGISBulkTransientError,
    execute_arcgis_complete_rehearsal,
    parse_arcgis_object_id_page,
)


@dataclass
class _Clock:
    value: datetime = datetime(2026, 7, 14, 20, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        current = self.value
        self.value = self.value + timedelta(seconds=1)
        return current


@dataclass
class _Source:
    counts: list[int]
    pages: dict[int, tuple[int, ...]]
    transient_failures: dict[tuple[int, int], str] = field(default_factory=dict)
    feature_mode: bool = False
    calls: list[tuple[int, int, int]] = field(default_factory=list)

    def fetch_count(self) -> int:
        if not self.counts:
            raise AssertionError("unexpected count request")
        return self.counts.pop(0)

    def fetch_object_id_page(
        self,
        *,
        offset: int,
        record_count: int,
        attempt_number: int,
    ) -> dict[str, Any]:
        self.calls.append((offset, record_count, attempt_number))
        failure_kind = self.transient_failures.get((offset, attempt_number))
        if failure_kind is not None:
            raise ParcelArcGISBulkTransientError(failure_kind)
        object_ids = self.pages[offset]
        if self.feature_mode:
            return {
                "features": [{"attributes": {"OBJECTID": object_id}} for object_id in object_ids]
            }
        return {"objectIds": list(object_ids)}


def _snapshot():
    return get_official_arcgis_capability_snapshots()[0]


def _policy(**overrides: Any) -> ParcelArcGISBulkRehearsalPolicy:
    values: dict[str, Any] = {
        "page_size": 2,
        "checkpoint_after_pages": 1,
        "injected_retry_page_index": 1,
        "max_attempts": 3,
        "retry_delays_seconds": (0.0, 0.0),
    }
    values.update(overrides)
    return ParcelArcGISBulkRehearsalPolicy(**values)


def test_complete_rehearsal_persists_reloads_retries_and_reconciles(
    tmp_path: Path,
) -> None:
    source = _Source(
        counts=[6, 6],
        pages={0: (1, 2), 2: (3, 4), 4: (5, 6)},
    )
    store = JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints")

    result = execute_arcgis_complete_rehearsal(
        _snapshot(),
        source,
        store,
        policy=_policy(),
        now=_Clock(),
        sleep=lambda _: None,
    )

    manifest = result.manifest
    evidence = manifest.rehearsal_evidence
    assert result.bulk_run_authorized is False
    assert result.checkpoint_reloaded is True
    assert manifest.starting_count == 6
    assert manifest.ending_count == 6
    assert manifest.retrieved_count == 6
    assert manifest.unique_object_id_count == 6
    assert manifest.duplicate_object_id_count == 0
    assert manifest.page_count == 3
    assert manifest.terminal_page_observed is True
    assert manifest.checkpoint_resume_verified is True
    assert manifest.retry_recovery_verified is True
    assert evidence.checkpoint.completed_page_count == 1
    assert evidence.resume.first_resumed_page_evidence_id == (
        evidence.page_evidence[1].page_evidence_id
    )
    assert len(evidence.retry_events) == 1
    assert evidence.retry_events[0].fault_injected is True
    assert evidence.retry_events[0].failed_attempt_count == 1
    assert evidence.page_evidence[1].attempt_count == 2
    assert source.calls == [(0, 2, 1), (2, 2, 2), (4, 2, 1)]

    checkpoint_path = store.path_for(evidence.checkpoint.checkpoint_id)
    assert checkpoint_path.is_file()
    assert store.load(evidence.checkpoint.checkpoint_id) == evidence.checkpoint


def test_complete_rehearsal_accepts_feature_attribute_pages(tmp_path: Path) -> None:
    snapshot = _snapshot()
    source = _Source(
        counts=[5, 5],
        pages={0: (10, 11), 2: (12, 13), 4: (14,)},
        feature_mode=True,
    )

    class _FieldMappedSource(_Source):
        def fetch_object_id_page(
            self,
            *,
            offset: int,
            record_count: int,
            attempt_number: int,
        ) -> dict[str, Any]:
            self.calls.append((offset, record_count, attempt_number))
            return {
                "features": [
                    {"attributes": {snapshot.object_id_field: object_id}}
                    for object_id in self.pages[offset]
                ]
            }

    mapped_source = _FieldMappedSource(
        counts=source.counts,
        pages=source.pages,
        feature_mode=True,
    )
    result = execute_arcgis_complete_rehearsal(
        snapshot,
        mapped_source,
        JSONFileParcelArcGISCheckpointStore(tmp_path),
        policy=_policy(),
        now=_Clock(),
        sleep=lambda _: None,
    )

    assert result.manifest.retrieved_count == 5
    assert result.manifest.page_count == 3
    assert len(result.manifest.rehearsal_evidence.page_evidence[-1].object_ids) == 1


def test_complete_rehearsal_rejects_count_drift(tmp_path: Path) -> None:
    source = _Source(
        counts=[6, 7],
        pages={0: (1, 2), 2: (3, 4), 4: (5, 6)},
    )

    with pytest.raises(ParcelArcGISBulkRehearsalError, match="count changed"):
        execute_arcgis_complete_rehearsal(
            _snapshot(),
            source,
            JSONFileParcelArcGISCheckpointStore(tmp_path),
            policy=_policy(),
            now=_Clock(),
            sleep=lambda _: None,
        )


def test_complete_rehearsal_rejects_short_page_before_count(tmp_path: Path) -> None:
    source = _Source(
        counts=[6],
        pages={0: (1, 2), 2: (3,), 4: (4, 5)},
    )

    with pytest.raises(ParcelArcGISBulkRehearsalError, match="short page"):
        execute_arcgis_complete_rehearsal(
            _snapshot(),
            source,
            JSONFileParcelArcGISCheckpointStore(tmp_path),
            policy=_policy(),
            now=_Clock(),
            sleep=lambda _: None,
        )


def test_complete_rehearsal_rejects_global_duplicate_or_reordering(
    tmp_path: Path,
) -> None:
    source = _Source(
        counts=[6],
        pages={0: (1, 2), 2: (2, 3), 4: (4, 5)},
    )

    with pytest.raises(ParcelArcGISBulkRehearsalError, match="globally ascending"):
        execute_arcgis_complete_rehearsal(
            _snapshot(),
            source,
            JSONFileParcelArcGISCheckpointStore(tmp_path),
            policy=_policy(),
            now=_Clock(),
            sleep=lambda _: None,
        )


def test_complete_rehearsal_fails_closed_after_bounded_retry_exhaustion(
    tmp_path: Path,
) -> None:
    source = _Source(
        counts=[8],
        pages={0: (1, 2), 2: (3, 4), 4: (5, 6), 6: (7, 8)},
        transient_failures={(4, 1): "transport", (4, 2): "transport", (4, 3): "transport"},
    )

    with pytest.raises(ParcelArcGISBulkRehearsalError, match="exhausted bounded retries"):
        execute_arcgis_complete_rehearsal(
            _snapshot(),
            source,
            JSONFileParcelArcGISCheckpointStore(tmp_path),
            policy=_policy(),
            now=_Clock(),
            sleep=lambda _: None,
        )


def test_checkpoint_store_rejects_tampered_retained_content(tmp_path: Path) -> None:
    source = _Source(
        counts=[6, 6],
        pages={0: (1, 2), 2: (3, 4), 4: (5, 6)},
    )
    store = JSONFileParcelArcGISCheckpointStore(tmp_path)
    result = execute_arcgis_complete_rehearsal(
        _snapshot(),
        source,
        store,
        policy=_policy(),
        now=_Clock(),
        sleep=lambda _: None,
    )
    checkpoint = result.manifest.rehearsal_evidence.checkpoint
    path = store.path_for(checkpoint.checkpoint_id)
    path.write_text(
        path.read_text(encoding="utf-8").replace('"object_id_count":2', '"object_id_count":9'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checkpoint|object-ID|identity"):
        store.load(checkpoint.checkpoint_id)


def test_policy_and_snapshot_refuse_invalid_rehearsal_scope(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="resumed execution segment"):
        _policy(injected_retry_page_index=0)

    snapshot = _snapshot()
    source = _Source(counts=[2], pages={0: (1, 2)})
    with pytest.raises(ValueError, match="exceeds the capability snapshot"):
        execute_arcgis_complete_rehearsal(
            snapshot,
            source,
            JSONFileParcelArcGISCheckpointStore(tmp_path),
            policy=_policy(page_size=snapshot.max_record_count + 1),
            now=_Clock(),
            sleep=lambda _: None,
        )


def test_object_id_page_parser_rejects_non_integer_values() -> None:
    with pytest.raises(ParcelArcGISBulkRehearsalError, match="JSON integers"):
        parse_arcgis_object_id_page(
            {"objectIds": [1, "2"]},
            object_id_field="OBJECTID",
        )
