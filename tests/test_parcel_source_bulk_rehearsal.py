from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISCapabilitySnapshot,
)
from constructionsight.parcel_source_bulk_rehearsal import (
    JSONFileParcelArcGISCheckpointStore,
    ParcelArcGISBulkRehearsalError,
    ParcelArcGISBulkRehearsalPolicy,
    ParcelArcGISBulkTransientError,
    execute_arcgis_complete_rehearsal,
    parse_arcgis_object_id_page,
)
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    JSONFileParcelArcGISBulkArtifactStore,
    ParcelArcGISBulkArtifactError,
    ParcelArcGISBulkArtifactKind,
    ParcelArcGISBulkArtifactReceipt,
    ParcelArcGISBulkCountResponse,
    ParcelArcGISBulkPageResponse,
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
    raw_page_bodies: dict[int, bytes] = field(default_factory=dict)
    calls: list[tuple[int, int, int]] = field(default_factory=list)

    def fetch_count(self) -> ParcelArcGISBulkCountResponse:
        if not self.counts:
            raise AssertionError("unexpected count request")
        return ParcelArcGISBulkCountResponse.from_count(self.counts.pop(0))

    def fetch_object_id_page(
        self,
        *,
        offset: int,
        record_count: int,
        attempt_number: int,
    ) -> ParcelArcGISBulkPageResponse:
        self.calls.append((offset, record_count, attempt_number))
        failure_kind = self.transient_failures.get((offset, attempt_number))
        if failure_kind is not None:
            raise ParcelArcGISBulkTransientError(failure_kind)
        if offset in self.raw_page_bodies:
            return ParcelArcGISBulkPageResponse(
                response_body=self.raw_page_bodies[offset]
            )
        return ParcelArcGISBulkPageResponse.from_payload(
            {"objectIds": list(self.pages[offset])}
        )


def _snapshot() -> ParcelArcGISCapabilitySnapshot:
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


def test_complete_rehearsal_retains_exact_bodies_and_reconciles(
    tmp_path: Path,
) -> None:
    exact_first_page = b'{ "objectIds" : [1, 2] }'
    source = _Source(
        counts=[6, 6],
        pages={0: (1, 2), 2: (3, 4), 4: (5, 6)},
        raw_page_bodies={0: exact_first_page},
    )
    checkpoint_store = JSONFileParcelArcGISCheckpointStore(
        tmp_path / "checkpoints"
    )
    artifact_store = JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts")

    result = execute_arcgis_complete_rehearsal(
        _snapshot(),
        source,
        checkpoint_store,
        artifact_store,
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

    kinds = tuple(receipt.kind for receipt in result.artifact_receipts)
    assert kinds == (
        ParcelArcGISBulkArtifactKind.STARTING_COUNT,
        ParcelArcGISBulkArtifactKind.PAGE,
        ParcelArcGISBulkArtifactKind.PAGE,
        ParcelArcGISBulkArtifactKind.PAGE,
        ParcelArcGISBulkArtifactKind.ENDING_COUNT,
    )
    assert artifact_store.read(result.artifact_receipts[1]) == exact_first_page
    assert tuple(
        receipt.response_digest for receipt in result.artifact_receipts[1:-1]
    ) == manifest.page_response_digests

    checkpoint_path = checkpoint_store.path_for(evidence.checkpoint.checkpoint_id)
    assert checkpoint_path.is_file()
    assert checkpoint_store.load(evidence.checkpoint.checkpoint_id) == evidence.checkpoint


def test_complete_rehearsal_accepts_feature_attribute_pages(tmp_path: Path) -> None:
    snapshot = _snapshot()

    class _FieldMappedSource(_Source):
        def fetch_object_id_page(
            self,
            *,
            offset: int,
            record_count: int,
            attempt_number: int,
        ) -> ParcelArcGISBulkPageResponse:
            self.calls.append((offset, record_count, attempt_number))
            return ParcelArcGISBulkPageResponse.from_payload(
                {
                    "features": [
                        {"attributes": {snapshot.object_id_field: object_id}}
                        for object_id in self.pages[offset]
                    ]
                }
            )

    source = _FieldMappedSource(
        counts=[5, 5],
        pages={0: (10, 11), 2: (12, 13), 4: (14,)},
    )
    result = execute_arcgis_complete_rehearsal(
        snapshot,
        source,
        JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
        JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
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
            JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
            JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
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
            JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
            JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
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
            JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
            JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
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
        transient_failures={
            (4, 1): "transport",
            (4, 2): "transport",
            (4, 3): "transport",
        },
    )

    with pytest.raises(ParcelArcGISBulkRehearsalError, match="exhausted bounded retries"):
        execute_arcgis_complete_rehearsal(
            _snapshot(),
            source,
            JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
            JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
            policy=_policy(),
            now=_Clock(),
            sleep=lambda _: None,
        )


def test_checkpoint_store_rejects_tampered_retained_content(tmp_path: Path) -> None:
    source = _Source(
        counts=[6, 6],
        pages={0: (1, 2), 2: (3, 4), 4: (5, 6)},
    )
    checkpoint_store = JSONFileParcelArcGISCheckpointStore(
        tmp_path / "checkpoints"
    )
    result = execute_arcgis_complete_rehearsal(
        _snapshot(),
        source,
        checkpoint_store,
        JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
        policy=_policy(),
        now=_Clock(),
        sleep=lambda _: None,
    )
    checkpoint = result.manifest.rehearsal_evidence.checkpoint
    path = checkpoint_store.path_for(checkpoint.checkpoint_id)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"object_id_count":2',
            '"object_id_count":9',
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checkpoint|object-ID|identity"):
        checkpoint_store.load(checkpoint.checkpoint_id)


def test_artifact_store_rejects_tampered_retained_bytes(tmp_path: Path) -> None:
    source = _Source(
        counts=[6, 6],
        pages={0: (1, 2), 2: (3, 4), 4: (5, 6)},
    )
    artifact_directory = tmp_path / "artifacts"
    artifact_store = JSONFileParcelArcGISBulkArtifactStore(artifact_directory)
    result = execute_arcgis_complete_rehearsal(
        _snapshot(),
        source,
        JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
        artifact_store,
        policy=_policy(),
        now=_Clock(),
        sleep=lambda _: None,
    )
    receipt = result.artifact_receipts[1]
    path = artifact_directory / receipt.artifact_reference
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(ParcelArcGISBulkArtifactError, match="size changed"):
        artifact_store.read(receipt)


def test_response_and_receipt_contracts_fail_closed() -> None:
    with pytest.raises(ValueError, match="does not match"):
        ParcelArcGISBulkCountResponse(
            count=2,
            response_body=b'{"count":3}',
        )
    with pytest.raises(ValueError, match="strict UTF-8 JSON"):
        ParcelArcGISBulkPageResponse(response_body=b"\xff")
    with pytest.raises(ValueError, match="safe file name"):
        ParcelArcGISBulkArtifactReceipt(
            kind=ParcelArcGISBulkArtifactKind.PAGE,
            sequence_index=1,
            response_digest="0" * 64,
            response_size=1,
            artifact_reference="../outside.json",
        )


def test_policy_and_snapshot_refuse_invalid_rehearsal_scope(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="resumed execution segment"):
        _policy(injected_retry_page_index=0)

    snapshot = _snapshot()
    source = _Source(counts=[2], pages={0: (1, 2)})
    with pytest.raises(ValueError, match="exceeds the capability snapshot"):
        execute_arcgis_complete_rehearsal(
            snapshot,
            source,
            JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints"),
            JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts"),
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


def test_arcgis_artifact_read_rejects_oversized_retained_file_before_full_read(
    tmp_path: Path,
) -> None:
    store = JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts")
    receipt = store.retain(
        kind=ParcelArcGISBulkArtifactKind.PAGE,
        sequence_index=0,
        response_body=b'{"objectIds":[]}',
    )
    path = tmp_path / "artifacts" / receipt.artifact_reference
    with path.open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)
    with pytest.raises(ParcelArcGISBulkArtifactError, match="size changed"):
        store.read(receipt)
    with pytest.raises(ParcelArcGISBulkArtifactError, match="digest conflicts"):
        store.retain(
            kind=ParcelArcGISBulkArtifactKind.PAGE,
            sequence_index=0,
            response_body=b'{"objectIds":[]}',
        )


def test_arcgis_artifact_store_rejects_oversized_new_body(
    tmp_path: Path,
) -> None:
    store = JSONFileParcelArcGISBulkArtifactStore(tmp_path / "artifacts")
    with pytest.raises(ParcelArcGISBulkArtifactError, match="artifact byte limit"):
        store.retain(
            kind=ParcelArcGISBulkArtifactKind.PAGE,
            sequence_index=0,
            response_body=b"x" * (16 * 1024 * 1024 + 1),
        )
