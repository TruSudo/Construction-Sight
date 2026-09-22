from __future__ import annotations

from pathlib import Path

import pytest

from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)


def test_repository_file_resolution_accepts_canonical_contained_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tests/test_example.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_example() -> None:\n    assert True\n", encoding="utf-8")

    relative, resolved = resolve_repository_file(
        tmp_path,
        "tests/test_example.py",
        required_prefix="tests",
        required_suffix=".py",
    )

    assert relative == Path("tests/test_example.py")
    assert resolved == target


@pytest.mark.parametrize(
    "reference",
    [
        "../outside.md",
        "/absolute.md",
        "docs/../outside.md",
        "docs\\outside.md",
        " docs/evidence.md",
    ],
)
def test_repository_file_resolution_rejects_noncanonical_reference(
    tmp_path: Path,
    reference: str,
) -> None:
    with pytest.raises(RepositoryPathError):
        resolve_repository_file(tmp_path, reference)


def test_repository_file_resolution_rejects_external_and_internal_symlinks(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "external.md").symlink_to(outside)
    (docs / "target.md").write_text("target\n", encoding="utf-8")
    (docs / "internal.md").symlink_to(docs / "target.md")

    for reference in ("docs/external.md", "docs/internal.md"):
        with pytest.raises(RepositoryPathError):
            resolve_repository_file(tmp_path, reference)


def test_repository_file_resolution_enforces_expected_kind(tmp_path: Path) -> None:
    target = tmp_path / "docs/evidence.md"
    target.parent.mkdir(parents=True)
    target.write_text("evidence\n", encoding="utf-8")

    with pytest.raises(RepositoryPathError):
        resolve_repository_file(
            tmp_path,
            "docs/evidence.md",
            required_prefix="tests",
            required_suffix=".py",
        )
