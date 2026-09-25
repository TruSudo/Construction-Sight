"""Semantic certification of the canonical GitHub Actions token permissions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from constructionsight.repository_certification import CertificationFinding
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

_CANONICAL_WORKFLOW: Final = ".github/workflows/ci.yml"
_EXPECTED_TOP_LEVEL_PERMISSIONS: Final = {
    "actions": "read",
    "contents": "read",
    "pull-requests": "read",
}
_PERMISSION_LINE = re.compile(r"  ([A-Za-z0-9_-]+):[ ]*([A-Za-z0-9_-]+)[ ]*(?:#.*)?$")


def _finding(message: str) -> CertificationFinding:
    return CertificationFinding(
        code="CERT-CI-005",
        path=_CANONICAL_WORKFLOW,
        line=None,
        message=message,
    )


def top_level_permissions(workflow: str) -> dict[str, str] | None:
    """Return the exact top-level permissions map or None for ambiguous YAML."""

    lines = workflow.splitlines()
    anchors = [index for index, line in enumerate(lines) if line == "permissions:"]
    if len(anchors) != 1:
        return None

    permissions: dict[str, str] = {}
    index = anchors[0] + 1
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if raw == raw.lstrip():
            break
        match = _PERMISSION_LINE.fullmatch(raw)
        if match is None:
            return None
        key, value = match.groups()
        if key in permissions:
            return None
        permissions[key] = value
        index += 1
    return permissions


def audit_ci_permissions(root: Path) -> tuple[CertificationFinding, ...]:
    """Require the canonical workflow to expose only the approved read scopes."""

    try:
        _relative, path = resolve_repository_file(
            root,
            _CANONICAL_WORKFLOW,
            required_prefix=".github/workflows",
            required_suffix=".yml",
        )
    except RepositoryPathError:
        return (_finding("canonical CI workflow is missing or unsafe"),)

    try:
        workflow = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return (_finding("canonical CI workflow cannot be read as UTF-8 text"),)

    permissions = top_level_permissions(workflow)
    if permissions != _EXPECTED_TOP_LEVEL_PERMISSIONS:
        return (
            _finding(
                "CI top-level permissions must equal the exact read-only allowlist: "
                "actions=read, contents=read, pull-requests=read"
            ),
        )
    return ()
