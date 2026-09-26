"""Strict repository-relative file resolution for certification evidence."""

from __future__ import annotations

from pathlib import Path


class RepositoryPathError(ValueError):
    """Raised when a repository reference is unsafe, missing, or escapes the tree."""


def resolve_repository_file(
    root: Path,
    value: object,
    *,
    required_prefix: str | None = None,
    required_suffix: str | None = None,
) -> tuple[Path, Path]:
    """Return the canonical relative and resolved paths for one regular file.

    References must use canonical POSIX repository-relative spelling. Every path
    component is rejected if it is a symbolic link, and the fully resolved target
    must remain beneath the resolved repository root.
    """

    if not isinstance(value, str) or not value or value != value.strip():
        raise RepositoryPathError("reference must be nonblank trimmed text")
    if "\\" in value or "\x00" in value:
        raise RepositoryPathError("reference must use canonical POSIX separators")
    relative = Path(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or relative.as_posix() != value
    ):
        raise RepositoryPathError("reference must be canonical and repository-relative")

    if required_prefix is not None:
        prefix = Path(required_prefix)
        if relative.parts[: len(prefix.parts)] != prefix.parts:
            raise RepositoryPathError(
                f"reference must remain beneath {prefix.as_posix()}"
            )
    if required_suffix is not None and relative.suffix != required_suffix:
        raise RepositoryPathError(f"reference must end with {required_suffix}")

    try:
        repository_root = root.resolve(strict=True)
    except OSError as exc:
        raise RepositoryPathError(f"repository root cannot be resolved: {exc}") from exc

    candidate = repository_root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise RepositoryPathError("symbolic-link path components are prohibited")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(repository_root)
    except (OSError, ValueError) as exc:
        raise RepositoryPathError(
            "reference is missing or resolves outside the repository"
        ) from exc
    if not resolved.is_file():
        raise RepositoryPathError("reference must resolve to a regular file")
    return relative, resolved
