import errno
import os
from pathlib import Path

import pytest

import constructionsight.storage.runtime_artifacts as artifacts
from constructionsight.storage.runtime_artifacts import (
    RuntimeArtifactError,
    open_runtime_artifact,
    read_runtime_artifact,
    runtime_artifact_parts,
)


@pytest.mark.parametrize(
    "reference",
    [
        "", "/absolute", "../parent", "a/../b", "./dot", "a//b", "a/",
        "a\\b", "C:relative", "C:/absolute", "//server/share", "proof:stream",
        "CON", "nul.json", "a/LPT9.txt", "proof.", " proof", "a/ b",
        "proof\x00.json", "proof\n.json", "proof\x7f.json",
        "proof?", "proof*", "proof<", "proof>", 'proof"', "proof|", "COM¹", "CON .txt",
    ],
)
def test_runtime_reference_rejects_noncanonical_or_platform_aliased_names(
    reference: str,
) -> None:
    with pytest.raises(RuntimeArtifactError):
        runtime_artifact_parts(reference)


def test_runtime_reference_accepts_canonical_nested_names() -> None:
    assert runtime_artifact_parts("evidence/response-1.json") == (
        "evidence", "response-1.json",
    )


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_runtime_reader_rejects_nonregular_files_without_blocking(
    tmp_path: Path, kind: str,
) -> None:
    path = tmp_path / "evidence"
    if kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    with pytest.raises(RuntimeArtifactError, match="regular file"):
        read_runtime_artifact(path, max_bytes=64)


@pytest.mark.parametrize(
    "capability",
    ["O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "dir_fd_open", "dir_fd_stat", "posix"],
)
def test_runtime_reader_fails_before_open_without_required_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capability: str,
) -> None:
    path = tmp_path / "evidence.json"
    path.write_bytes(b"{}")

    def forbidden_open(*args, **kwargs):
        raise AssertionError("unsupported access attempted to open evidence")

    monkeypatch.setattr(os, "open", forbidden_open)
    if capability == "dir_fd_open":
        monkeypatch.setattr(artifacts, "_DIRECTORY_RELATIVE_OPEN_SUPPORTED", False)
    elif capability == "dir_fd_stat":
        monkeypatch.setattr(artifacts, "_DIRECTORY_RELATIVE_STAT_SUPPORTED", False)
    elif capability == "posix":
        monkeypatch.setattr(artifacts.os, "name", "nt")
    else:
        monkeypatch.delattr(os, capability)
    with pytest.raises(RuntimeArtifactError, match="unavailable"):
        read_runtime_artifact(path, max_bytes=64)


def test_runtime_reader_detects_regular_file_replacement_before_return(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.json"
    path.write_bytes(b"original")
    with (
        pytest.raises(RuntimeArtifactError, match="path changed"),
        open_runtime_artifact(path) as stream,
    ):
        path.rename(tmp_path / "original.json")
        path.write_bytes(b"replacement")
        assert stream.read(64) == b"original"


def test_runtime_reader_never_opens_a_symlinked_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "proof.json").write_bytes(b"{}")
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    identity = outside.stat()
    original_open = os.open
    outside_opened = False

    def observed_open(*args, **kwargs):
        nonlocal outside_opened
        descriptor = original_open(*args, **kwargs)
        result = os.fstat(descriptor)
        if (result.st_dev, result.st_ino) == (identity.st_dev, identity.st_ino):
            outside_opened = True
        return descriptor

    monkeypatch.setattr(os, "open", observed_open)
    with pytest.raises((OSError, RuntimeArtifactError)):
        read_runtime_artifact(alias / "proof.json", max_bytes=64)
    assert not outside_opened


def test_runtime_reader_bounds_growth_even_when_initial_size_was_small(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "growing.json"
    path.write_bytes(b"x" * 65)
    original_fstat = os.fstat

    def stale_size(descriptor):
        result = original_fstat(descriptor)
        fields = list(result)
        fields[6] = 1
        return os.stat_result(fields)

    monkeypatch.setattr(os, "fstat", stale_size)
    with pytest.raises(RuntimeArtifactError, match="file byte limit"):
        read_runtime_artifact(path, max_bytes=64)


def test_runtime_reader_closes_every_descriptor_after_rejected_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    path = parent / "evidence.json"
    path.write_bytes(b"x" * 65)
    descriptors = []
    original_open = os.open

    def observed_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", observed_open)
    with pytest.raises(RuntimeArtifactError, match="file byte limit"):
        read_runtime_artifact(path, max_bytes=64)
    assert len(descriptors) >= 3
    for descriptor in descriptors:
        with pytest.raises(OSError) as error:
            os.fstat(descriptor)
        assert error.value.errno == errno.EBADF
