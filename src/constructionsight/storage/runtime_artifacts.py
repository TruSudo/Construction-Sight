"""Handle-relative access to bounded runtime evidence without symlink traversal."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO

_DIRECTORY_RELATIVE_OPEN_SUPPORTED = os.open in os.supports_dir_fd
_DIRECTORY_RELATIVE_STAT_SUPPORTED = os.stat in os.supports_dir_fd
_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"com{number}" for number in (*range(1, 10), "¹", "²", "³")}
    | {f"lpt{number}" for number in (*range(1, 10), "¹", "²", "³")}
)


class RuntimeArtifactError(ValueError):
    """Runtime evidence could not be accessed within its authorized path."""


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
def anchored_artifact_parent(path: Path) -> Iterator[tuple[int, str]]:
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
            child = os.open(component, flags, dir_fd=parent)
            descriptors.append(child)
            bindings.append((parent, component, child))
            parent = child
        for binding in bindings:
            _require_same_entry(*binding)
        yield parent, parts[-1]
        for binding in bindings:
            _require_same_entry(*binding)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextmanager
def open_runtime_artifact(path: Path) -> Iterator[BinaryIO]:
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
                _require_same_entry(parent, name, stream.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def read_runtime_artifact(path: Path, *, max_bytes: int) -> bytes:
    """Return the bounded bytes from the same no-follow handle that was checked."""

    if isinstance(max_bytes, bool) or max_bytes < 1:
        raise ValueError("artifact byte limit must be positive")
    with open_runtime_artifact(path) as stream:
        if os.fstat(stream.fileno()).st_size > max_bytes:
            raise RuntimeArtifactError("artifact evidence exceeds the file byte limit")
        content = stream.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise RuntimeArtifactError("artifact evidence exceeds the file byte limit")
    return content
