"""Certify canonical GitHub Action identities and reviewed runtime classes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, NamedTuple

from constructionsight.repository_certification import CertificationFinding
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

_CANONICAL_WORKFLOW: Final = ".github/workflows/ci.yml"
_ACTION_USE = re.compile(
    r"^\s*uses:\s+(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@"
    r"(?P<commit>[0-9a-f]{40})\s+#\s+(?P<review>\S.*)$"
)


class _ReviewedAction(NamedTuple):
    commit: str
    release: str
    runtime: str
    reviewed_on: str
    occurrences: int


_REVIEWED_ACTIONS: Final = {
    "actions/checkout": _ReviewedAction(
        commit="3d3c42e5aac5ba805825da76410c181273ba90b1",
        release="v7.0.1",
        runtime="node24",
        reviewed_on="2026-09-14",
        occurrences=2,
    ),
    "actions/setup-python": _ReviewedAction(
        commit="5fda3b95a4ea91299a34e894583c3862153e4b97",
        release="v7.0.0",
        runtime="node24",
        reviewed_on="2026-09-14",
        occurrences=2,
    ),
    "actions/upload-artifact": _ReviewedAction(
        commit="043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        release="v7.0.1",
        runtime="node24",
        reviewed_on="2026-09-14",
        occurrences=2,
    ),
    "pypa/gh-action-pip-audit": _ReviewedAction(
        commit="fb241f581674a1bb995061d62504857a9ea4b69e",
        release="immutable-reviewed-commit",
        runtime="composite",
        reviewed_on="2026-07-15",
        occurrences=1,
    ),
}


def _finding(message: str, line: int | None = None) -> CertificationFinding:
    return CertificationFinding(
        code="CERT-CI-006",
        path=_CANONICAL_WORKFLOW,
        line=line,
        message=message,
    )


def _review_comment(action: _ReviewedAction) -> str:
    return (
        f"{action.release}; reviewed {action.reviewed_on}; "
        f"runtime={action.runtime}"
    )


def audit_ci_actions(root: Path) -> tuple[CertificationFinding, ...]:
    """Require exact reviewed Action source identities and runtime annotations."""

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

    findings: list[CertificationFinding] = []
    counts = {repository: 0 for repository in _REVIEWED_ACTIONS}
    for line_number, raw in enumerate(workflow.splitlines(), start=1):
        if "uses:" not in raw:
            continue
        match = _ACTION_USE.fullmatch(raw)
        if match is None:
            findings.append(
                _finding(
                    "every Action use must bind an exact 40-hex commit and reviewed runtime comment",
                    line_number,
                )
            )
            continue

        repository = match.group("repository")
        commit = match.group("commit")
        review = match.group("review")
        expected = _REVIEWED_ACTIONS.get(repository)
        if expected is None:
            findings.append(
                _finding(f"unreviewed GitHub Action repository: {repository}", line_number)
            )
            continue
        counts[repository] += 1
        if commit != expected.commit:
            findings.append(
                _finding(
                    f"{repository} must use reviewed commit {expected.commit}",
                    line_number,
                )
            )
        if review != _review_comment(expected):
            findings.append(
                _finding(
                    f"{repository} review annotation must bind release, date, and runtime={expected.runtime}",
                    line_number,
                )
            )

    for repository, expected in _REVIEWED_ACTIONS.items():
        if counts[repository] != expected.occurrences:
            findings.append(
                _finding(
                    f"{repository} must occur exactly {expected.occurrences} time(s); "
                    f"found {counts[repository]}"
                )
            )
    return tuple(findings)
