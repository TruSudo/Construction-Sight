import errno
import hashlib
import io
import os
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

import constructionsight.parcel_source_bulk_rehearsal as rehearsal
import constructionsight.storage.runtime_artifacts as runtime_artifacts
from constructionsight.parcel_source_bulk_rehearsal import JSONFileParcelArcGISCheckpointStore
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    JSONFileParcelArcGISBulkArtifactStore,
    ParcelArcGISBulkArtifactError,
    ParcelArcGISBulkArtifactKind,
)
from constructionsight.parcel_source_bulk_rehearsal_models import (
    ParcelArcGISBulkCheckpointEvidence,
    build_arcgis_bulk_checkpoint_evidence,
    build_arcgis_bulk_page_evidence,
)
from constructionsight.storage.runtime_artifacts import publish_runtime_artifact

_BODY = b'{"objectIds":[1,2]}'


def _retain(directory: Path):
    return JSONFileParcelArcGISBulkArtifactStore(directory).retain(
        kind=ParcelArcGISBulkArtifactKind.PAGE, sequence_index=0, response_body=_BODY,
    )


def _filename() -> str:
    return f"00000000-page-{hashlib.sha256(_BODY).hexdigest()}.json"


def test_artifact_publication_does_not_follow_predictable_temporary_symlink(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"must remain unchanged")
    (directory / _filename()).with_suffix(".tmp").symlink_to(outside)

    receipt = _retain(directory)
    assert outside.read_bytes() == b"must remain unchanged"
    assert not (directory / receipt.artifact_reference).is_symlink()
    assert JSONFileParcelArcGISBulkArtifactStore(directory).read(receipt) == _BODY


def test_artifact_publication_rejects_symlinked_parent_before_writing(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    with pytest.raises((OSError, ValueError, ParcelArcGISBulkArtifactError)):
        _retain(alias / "new-directory")
    assert list(outside.iterdir()) == []


def test_artifact_publication_never_replaces_a_racing_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    target = directory / _filename()
    winner = b"conflicting concurrent writer"
    injected = False
    original_link, original_replace = os.link, os.replace

    def inject(destination):
        nonlocal injected
        if Path(destination).name == target.name and not injected:
            injected = True
            target.write_bytes(winner)

    def racing_link(source, destination, *args, **kwargs):
        inject(destination)
        return original_link(source, destination, *args, **kwargs)

    def racing_replace(source, destination, *args, **kwargs):
        inject(destination)
        return original_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "link", racing_link)
    monkeypatch.setattr(os, "replace", racing_replace)
    with pytest.raises((ValueError, ParcelArcGISBulkArtifactError)):
        _retain(directory)
    assert injected
    assert target.read_bytes() == winner


def test_artifact_publication_rejects_parent_swap_without_outside_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    parked = tmp_path / "parked"
    original_os_open, original_io_open = os.open, io.open
    swapped = False

    def swap(path):
        nonlocal swapped
        if not isinstance(path, int) and str(path).endswith(".tmp") and not swapped:
            swapped = True
            directory.rename(parked)
            directory.symlink_to(outside, target_is_directory=True)

    def swapped_os_open(path, flags, *args, **kwargs):
        if flags & os.O_CREAT:
            swap(path)
        return original_os_open(path, flags, *args, **kwargs)

    def swapped_io_open(path, mode="r", *args, **kwargs):
        if "w" in mode:
            swap(path)
        return original_io_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "open", swapped_os_open)
    monkeypatch.setattr(io, "open", swapped_io_open)
    with pytest.raises((OSError, ValueError, ParcelArcGISBulkArtifactError)):
        _retain(directory)
    assert swapped
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("linked_parent", [False, True])
def test_artifact_read_rejects_symlink_traversal(
    tmp_path: Path, linked_parent: bool,
) -> None:
    directory = tmp_path / "artifacts"
    receipt = _retain(directory)
    if linked_parent:
        alias = tmp_path / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        store = JSONFileParcelArcGISBulkArtifactStore(alias)
    else:
        path = directory / receipt.artifact_reference
        outside = tmp_path / "outside.json"
        path.rename(outside)
        path.symlink_to(outside)
        store = JSONFileParcelArcGISBulkArtifactStore(directory)
    with pytest.raises((OSError, ValueError, ParcelArcGISBulkArtifactError)):
        store.read(receipt)


def test_artifact_concurrent_exact_replay_retains_one_complete_body(tmp_path: Path) -> None:
    barrier = threading.Barrier(2)

    def retain_once():
        barrier.wait(timeout=10)
        return _retain(tmp_path / "artifacts")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(retain_once) for _ in range(2)]
        receipts = [future.result(timeout=10) for future in futures]
    assert receipts[0] == receipts[1]
    directory = tmp_path / "artifacts"
    assert [path.name for path in directory.iterdir()] == [receipts[0].artifact_reference]
    assert JSONFileParcelArcGISBulkArtifactStore(directory).read(receipts[0]) == _BODY


def test_artifact_exact_replay_rejects_parent_replacement_during_failed_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    replacement = tmp_path / "replacement"
    _retain(directory)
    _retain(replacement)
    parked = tmp_path / "parked"
    original_link = os.link
    swapped = False

    def replace_parent_then_link(*args, **kwargs):
        nonlocal swapped
        directory.rename(parked)
        replacement.rename(directory)
        swapped = True
        return original_link(*args, **kwargs)

    monkeypatch.setattr(os, "link", replace_parent_then_link)
    with pytest.raises(ValueError, match="path changed"):
        _retain(directory)
    assert swapped
    assert (directory / _filename()).read_bytes() == _BODY
    assert (parked / _filename()).read_bytes() == _BODY


def test_artifact_data_is_synced_before_publish_and_directory_after_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    events = []
    original_fsync, original_link = os.fsync, os.link

    def observe_fsync(descriptor):
        events.append("data-sync" if stat.S_ISREG(os.fstat(descriptor).st_mode) else "dir-sync")
        return original_fsync(descriptor)

    def observe_link(*args, **kwargs):
        events.append("publish")
        return original_link(*args, **kwargs)

    monkeypatch.setattr(os, "fsync", observe_fsync)
    monkeypatch.setattr(os, "link", observe_link)
    _retain(directory)
    assert events.index("data-sync") < events.index("publish")
    assert "dir-sync" in events[events.index("publish") + 1 :]


def test_artifact_exact_replay_syncs_verified_file_and_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    receipt = _retain(directory)
    identity = (directory / receipt.artifact_reference).stat().st_ino
    parent_identity = directory.stat().st_ino
    synced = []
    original_fsync = os.fsync

    def observed_fsync(descriptor):
        synced.append(os.fstat(descriptor).st_ino)
        return original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", observed_fsync)
    assert _retain(directory) == receipt
    assert identity in synced
    assert parent_identity in synced[synced.index(identity) + 1 :]


def test_artifact_conflicting_replay_never_syncs_unverified_existing_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    receipt = _retain(directory)
    target = directory / receipt.artifact_reference
    target.write_bytes(b"x" * len(_BODY))
    identity = target.stat().st_ino
    synced = []
    original_fsync = os.fsync

    def observed_fsync(descriptor):
        synced.append(os.fstat(descriptor).st_ino)
        return original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", observed_fsync)
    with pytest.raises(ParcelArcGISBulkArtifactError, match="digest conflicts"):
        _retain(directory)
    assert identity not in synced
    assert target.read_bytes() == b"x" * len(_BODY)


def test_artifact_writer_rejects_unsupported_publication_before_directory_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_mkdir(*args, **kwargs):
        raise AssertionError("unsupported publication attempted filesystem mutation")

    monkeypatch.setattr(runtime_artifacts, "_DIRECTORY_RELATIVE_PUBLICATION_SUPPORTED", False)
    monkeypatch.setattr(os, "mkdir", forbidden_mkdir)
    with pytest.raises(ValueError, match="publication is unavailable"):
        _retain(tmp_path / "artifacts")


def test_artifact_stream_construction_failure_closes_all_descriptors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptors = []
    original_open = os.open

    def observed_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        descriptors.append(descriptor)
        return descriptor

    def fail_fdopen(*args, **kwargs):
        raise OSError("injected stream construction failure")

    monkeypatch.setattr(os, "open", observed_open)
    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    with pytest.raises(OSError, match="stream construction"):
        _retain(tmp_path / "artifacts")
    assert descriptors
    for descriptor in descriptors:
        with pytest.raises(OSError) as error:
            os.fstat(descriptor)
        assert error.value.errno == errno.EBADF
    assert list((tmp_path / "artifacts").iterdir()) == []


def test_artifact_publish_failure_removes_staging_and_allows_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    original_link = os.link

    def fail_publish(*args, **kwargs):
        raise OSError("injected publication failure")

    monkeypatch.setattr(os, "link", fail_publish)
    with pytest.raises(OSError, match="publication failure"):
        _retain(directory)
    assert list(directory.iterdir()) == []
    monkeypatch.setattr(os, "link", original_link)
    receipt = _retain(directory)
    assert JSONFileParcelArcGISBulkArtifactStore(directory).read(receipt) == _BODY


def test_artifact_post_publish_failure_retains_complete_recoverable_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "artifacts"
    directory.mkdir()
    original_fsync, original_link = os.fsync, os.link
    published = False
    failed = False

    def observe_link(*args, **kwargs):
        nonlocal published
        result = original_link(*args, **kwargs)
        published = True
        return result

    def fail_once_after_publish(descriptor):
        nonlocal failed
        if published and not failed:
            failed = True
            raise OSError("injected post-publication sync failure")
        return original_fsync(descriptor)

    monkeypatch.setattr(os, "link", observe_link)
    monkeypatch.setattr(os, "fsync", fail_once_after_publish)
    with pytest.raises(OSError, match="post-publication"):
        _retain(directory)
    assert failed
    assert (directory / _filename()).read_bytes() == _BODY
    receipt = _retain(directory)
    assert JSONFileParcelArcGISBulkArtifactStore(directory).read(receipt) == _BODY
    assert [path.name for path in directory.iterdir()] == [receipt.artifact_reference]


def test_artifact_writer_stops_before_publishing_oversize_and_cleans_staging(
    tmp_path: Path,
) -> None:
    observed = []

    def chunks():
        for index in range(100):
            observed.append(index)
            yield b"x" * 16

    with pytest.raises(ValueError, match="file byte limit"):
        publish_runtime_artifact(tmp_path / "bounded.json", chunks(), max_bytes=32)
    assert observed == [0, 1, 2]
    assert list(tmp_path.iterdir()) == []


def _checkpoint():
    observed = datetime(2026, 7, 14, 20, tzinfo=UTC)
    page = build_arcgis_bulk_page_evidence(
        page_index=0, page_size=2, object_ids=(1, 2),
        response_digest=hashlib.sha256(_BODY).hexdigest(),
        attempt_count=1, terminal_page=False, observed_at=observed,
    )
    return build_arcgis_bulk_checkpoint_evidence(
        (page,), completed_page_count=1, page_size=2, created_at=observed,
    )


def test_checkpoint_publication_does_not_follow_predictable_temporary_symlink(
    tmp_path: Path,
) -> None:
    store = JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints")
    checkpoint = _checkpoint()
    path = store.path_for(checkpoint.checkpoint_id)
    path.parent.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"unchanged")
    path.with_suffix(".tmp").symlink_to(outside)

    store.save(checkpoint)
    assert outside.read_bytes() == b"unchanged"
    assert not path.is_symlink()
    assert store.load(checkpoint.checkpoint_id) == checkpoint


def test_checkpoint_publication_rejects_symlinked_parent_before_writing(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    with pytest.raises((OSError, ValueError, rehearsal.ParcelArcGISBulkRehearsalError)):
        JSONFileParcelArcGISCheckpointStore(alias / "new-checkpoints").save(_checkpoint())
    assert list(outside.iterdir()) == []


def test_checkpoint_loader_bounds_input_before_json_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JSONFileParcelArcGISCheckpointStore(tmp_path)
    checkpoint = _checkpoint()
    path = store.path_for(checkpoint.checkpoint_id)
    with path.open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)

    def forbidden_parse(*args, **kwargs):
        raise AssertionError("oversized checkpoint reached JSON materialization")

    monkeypatch.setattr(ParcelArcGISBulkCheckpointEvidence, "model_validate_json", forbidden_parse)
    with pytest.raises(ValueError, match="file byte limit"):
        store.load(checkpoint.checkpoint_id)


@pytest.mark.parametrize("linked_parent", [False, True])
def test_checkpoint_loader_rejects_symlink_traversal(
    tmp_path: Path, linked_parent: bool,
) -> None:
    store = JSONFileParcelArcGISCheckpointStore(tmp_path / "checkpoints")
    checkpoint = _checkpoint()
    store.save(checkpoint)
    if linked_parent:
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path / "checkpoints", target_is_directory=True)
        store = JSONFileParcelArcGISCheckpointStore(alias)
    else:
        path = store.path_for(checkpoint.checkpoint_id)
        outside = tmp_path / "outside.json"
        path.rename(outside)
        path.symlink_to(outside)
    with pytest.raises((OSError, ValueError, rehearsal.ParcelArcGISBulkRehearsalError)):
        store.load(checkpoint.checkpoint_id)
