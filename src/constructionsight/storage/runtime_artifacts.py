"""Handle-relative access to bounded runtime evidence without symlink traversal."""

from __future__ import annotations

import json
import os
import secrets
import stat
from collections.abc import Iterable, Iterator
from contextlib import contextmanager, suppress
from itertools import chain
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO

_DIRECTORY_RELATIVE_OPEN_SUPPORTED = os.open in os.supports_dir_fd
_DIRECTORY_RELATIVE_STAT_SUPPORTED = os.stat in os.supports_dir_fd
_DIRECTORY_RELATIVE_REPLACEMENT_SUPPORTED = os.rename in os.supports_dir_fd
_DIRECTORY_RELATIVE_PUBLICATION_SUPPORTED = all(
    operation in os.supports_dir_fd for operation in (os.mkdir, os.rmdir, os.unlink, os.link)
)
_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"com{number}" for number in (*range(1, 10), "¹", "²", "³")}
    | {f"lpt{number}" for number in (*range(1, 10), "¹", "²", "³")}
)


class RuntimeArtifactError(ValueError):
    """Runtime evidence could not be accessed within its authorized path."""


class RuntimeArtifactLimitError(RuntimeArtifactError):
    """Runtime evidence exceeds its governed byte ceiling."""


def runtime_artifact_parts(reference: str) -> tuple[str, ...]:
    """Validate portable canonical relative names before interpreting any path."""

    if (
        not reference
        or reference != reference.strip()
        or "\\" in reference
        or any(character in reference for character in ':<>"|?*')
        or any(ord(character) < 32 or ord(character) == 127 for character in reference)
        or PureWindowsPath(reference).drive
    ):
        raise RuntimeArtifactError("artifact reference must be a canonical relative name")
    parts = tuple(reference.split("/"))
    if (
        PurePosixPath(reference).is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or any(part != part.strip() or part.endswith(".") for part in parts)
        or any(part.split(".", 1)[0].rstrip().casefold() in _DEVICE_NAMES for part in parts)
    ):
        raise RuntimeArtifactError("artifact reference must be a canonical relative name")
    return parts


def _require_anchored_access() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    if (
        os.name != "posix"
        or not nofollow
        or not directory
        or not getattr(os, "O_NONBLOCK", 0)
        or not _DIRECTORY_RELATIVE_OPEN_SUPPORTED
        or not _DIRECTORY_RELATIVE_STAT_SUPPORTED
    ):
        raise RuntimeArtifactError(
            "atomic directory-relative no-follow artifact access is unavailable"
        )
    return os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)


def _require_same_entry(parent: int, name: str, descriptor: int) -> None:
    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    opened = os.fstat(descriptor)
    if (
        stat.S_ISLNK(current.st_mode)
        or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
    ):
        raise RuntimeArtifactError("artifact path changed during handle-relative access")


@contextmanager
def anchored_artifact_parent(
    path: Path, *, create_parents: bool = False,
) -> Iterator[tuple[int, str]]:
    """Pin every existing parent and reject path changes before returning success.

    Every open is relative to an already pinned directory. Replacing an ancestor
    with a symlink cannot redirect the subsequent file open outside that object.
    Unsupported platforms fail before opening evidence; they never downgrade to
    an ordinary path-based open.
    """

    flags = _require_anchored_access()
    absolute = path.absolute()
    if absolute.anchor != "/" or any(part == ".." for part in absolute.parts):
        raise RuntimeArtifactError("artifact path must have a canonical absolute root")
    parts = runtime_artifact_parts("/".join(absolute.parts[1:]))
    descriptors: list[int] = []
    bindings: list[tuple[int, str, int]] = []
    try:
        parent = os.open(absolute.anchor, flags)
        descriptors.append(parent)
        for component in parts[:-1]:
            if create_parents:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                else:
                    os.fsync(parent)
            child = os.open(component, flags, dir_fd=parent)
            descriptors.append(child)
            bindings.append((parent, component, child))
            parent = child
        for binding in bindings:
            _require_same_entry(*binding)
        try:
            yield parent, parts[-1]
        finally:
            for binding in bindings:
                _require_same_entry(*binding)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextmanager
def open_runtime_artifact(path: Path, *, durable: bool = False) -> Iterator[BinaryIO]:
    """Open one regular evidence file without following any path component."""

    with anchored_artifact_parent(path) as (parent, name):
        flags = (
            os.O_RDONLY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | getattr(os, "O_CLOEXEC", 0)
        )
        descriptor = os.open(name, flags, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise RuntimeArtifactError("artifact evidence must be a regular file")
            _require_same_entry(parent, name, descriptor)
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                yield stream
                if durable:
                    os.fsync(stream.fileno())
                    os.fsync(parent)
                _require_same_entry(parent, name, stream.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def read_runtime_artifact(path: Path, *, max_bytes: int) -> bytes:
    """Return the bounded bytes from the same no-follow handle that was checked."""

    _require_byte_limit(max_bytes)
    with open_runtime_artifact(path) as stream:
        content = read_bounded_artifact_stream(stream, max_bytes=max_bytes)
    return content


def read_runtime_text(path: Path, *, max_bytes: int = 16 * 1024 * 1024) -> str:
    """Decode one contained UTF-8 snapshot with a pre-materialization ceiling.

    Operator JSON and stored HTML inputs share the 16-MiB evidence-file ceiling.
    Specialized binary formats retain their own, potentially tighter limits.
    """

    return read_runtime_artifact(path, max_bytes=max_bytes).decode("utf-8")


def read_bounded_artifact_stream(stream: BinaryIO, *, max_bytes: int) -> bytes:
    """Read bounded bytes while a caller holds and verifies the same artifact handle."""

    _require_byte_limit(max_bytes)
    if os.fstat(stream.fileno()).st_size > max_bytes:
        raise RuntimeArtifactLimitError("artifact evidence exceeds the file byte limit")
    content = stream.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise RuntimeArtifactLimitError("artifact evidence exceeds the file byte limit")
    return content


def _require_byte_limit(max_bytes: int) -> None:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("artifact byte limit must be a positive integer")


def publish_runtime_artifact(
    path: Path, chunks: Iterable[bytes], *, max_bytes: int, replace_existing: bool = False,
) -> None:
    """Durably publish one complete artifact, create-only unless replacement is explicit.

    Stage in an exclusively created private directory, hold its descriptor for
    every write/publication/cleanup, fsync the complete file, then create the final
    name with an atomic no-replace link or explicitly requested replacement of a
    regular file. Replacement changes the directory entry, never the old inode.
    FileExistsError delegates exact replay to the
    caller's bounded semantic verifier. An error after publication never claims
    success; a retry can independently verify the complete existing artifact.
    """

    directory_flags = _require_anchored_access()
    if not _DIRECTORY_RELATIVE_PUBLICATION_SUPPORTED:
        raise RuntimeArtifactError("atomic directory-relative publication is unavailable")
    if not isinstance(replace_existing, bool):
        raise ValueError("artifact replacement policy must be Boolean")
    if replace_existing and not _DIRECTORY_RELATIVE_REPLACEMENT_SUPPORTED:
        raise RuntimeArtifactError("atomic directory-relative replacement is unavailable")
    _require_byte_limit(max_bytes)
    with anchored_artifact_parent(path, create_parents=True) as (parent, name):
        if replace_existing:
            _require_regular_replacement_target(parent, name)
        staging_name = f".runtime-artifact-{secrets.token_hex(16)}"
        os.mkdir(staging_name, mode=0o700, dir_fd=parent)
        staging = os.open(staging_name, directory_flags, dir_fd=parent)
        staging_owned = False
        descriptor = -1
        try:
            _require_same_entry(parent, staging_name, staging)
            staging_stat = os.fstat(staging)
            if staging_stat.st_uid != os.geteuid() or stat.S_IMODE(staging_stat.st_mode) != 0o700:
                raise RuntimeArtifactError("artifact staging directory is not private and owned")
            staging_owned = True
            descriptor = os.open(
                "content.tmp",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=staging,
            )
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                byte_count = 0
                for chunk in chunks:
                    if not isinstance(chunk, bytes) or not chunk:
                        raise RuntimeArtifactError("artifact chunks must be nonempty bytes")
                    byte_count += len(chunk)
                    if byte_count > max_bytes:
                        raise RuntimeArtifactLimitError(
                            "artifact evidence exceeds the file byte limit"
                        )
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
                os.fsync(staging)
                _require_same_entry(parent, staging_name, staging)
                _require_same_entry(staging, "content.tmp", stream.fileno())
                if replace_existing:
                    _require_regular_replacement_target(parent, name)
                    os.replace("content.tmp", name, src_dir_fd=staging, dst_dir_fd=parent)
                    _require_same_entry(parent, name, stream.fileno())
                    os.fsync(parent)
                    return
                os.link(
                    "content.tmp", name,
                    src_dir_fd=staging, dst_dir_fd=parent, follow_symlinks=False,
                )
                _require_same_entry(parent, name, stream.fileno())
                os.fsync(parent)
        finally:
            try:
                if descriptor >= 0:
                    os.close(descriptor)
                if staging_owned:
                    with suppress(FileNotFoundError):
                        os.unlink("content.tmp", dir_fd=staging)
                    _require_same_entry(parent, staging_name, staging)
                    os.rmdir(staging_name, dir_fd=parent)
                    os.fsync(parent)
            finally:
                os.close(staging)


def _require_regular_replacement_target(parent: int, name: str) -> None:
    try:
        target = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(target.st_mode):
        raise RuntimeArtifactError("artifact replacement target must be a regular file")


def write_runtime_text(
    path: Path, content: str, *, overwrite: bool = True, max_bytes: int = 16 * 1024 * 1024,
) -> None:
    """Write bounded UTF-8 through the same contained atomic publication protocol."""

    chunks = (
        content[start:start + 16_384].encode("utf-8")
        for start in range(0, len(content), 16_384)
    )
    publish_runtime_artifact(path, chunks, max_bytes=max_bytes, replace_existing=overwrite)


def runtime_json_chunks(value: object) -> Iterator[bytes]:
    """Encode canonical JSON in bounded UTF-8 chunks with one final newline."""

    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"))
    for fragment in chain(encoder.iterencode(value), ("\n",)):
        for start in range(0, len(fragment), 16_384):
            yield fragment[start : start + 16_384].encode("utf-8")
