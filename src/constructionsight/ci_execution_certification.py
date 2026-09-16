"""Bind every canonical CI setting to reviewed bytes, including settings outside jobs.

Workflow edits require explicit review and an updated literal digest. The digest
is a drift control, not analytical assurance or authenticated owner acceptance.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from constructionsight.repository_certification import CertificationFinding
from constructionsight.repository_path_certification import resolve_repository_file

_CANONICAL_WORKFLOW: Final = ".github/workflows/ci.yml"
_REVIEWED_WORKFLOW_SHA256: Final = (
    "43b322c11badaeceac0c56d87e22cb986a974f4f45bb700fa04cd2c203087228"
)


def audit_ci_execution(root: Path) -> tuple[CertificationFinding, ...]:
    """Reject any unreviewed workflow change, regardless of YAML spelling or scope."""

    try:
        _relative, workflow = resolve_repository_file(root, _CANONICAL_WORKFLOW)
        actual_digest = hashlib.sha256(workflow.read_bytes()).hexdigest()
        if actual_digest != _REVIEWED_WORKFLOW_SHA256:
            raise ValueError("canonical CI differs from its complete reviewed execution contract")
    except (OSError, ValueError) as exc:
        return (
            CertificationFinding(
                code="CERT-CI-008", path=_CANONICAL_WORKFLOW, line=None, message=str(exc)
            ),
        )
    return ()
