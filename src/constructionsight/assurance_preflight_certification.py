"""Pre-assurance structural certification for an exact ConstructionSight candidate."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from constructionsight.ci_action_certification import audit_ci_actions
from constructionsight.ci_permissions_certification import audit_ci_permissions
from constructionsight.governance_certification import audit_governance
from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.repository_certification import (
    CertificationFinding,
    _tracked_files,
    audit_repository,
)

_SCHEMA_VERSION: Final = "constructionsight.assurance-preflight/v1"
_ALLOWED_TRANSACTION_BLOCKERS: Final = frozenset(
    {"ASSURANCE-001", "DEFECT-ACTIVE-001"}
)


def _is_transaction_blocker(code: str) -> bool:
    return code in _ALLOWED_TRANSACTION_BLOCKERS


def preflight_findings(
    findings: Sequence[GovernanceFinding],
) -> tuple[GovernanceFinding, ...]:
    """Return governance findings not expected during assurance finalization."""

    return tuple(
        finding for finding in findings if not _is_transaction_blocker(finding.code)
    )


def _finding_row(
    finding: CertificationFinding | GovernanceFinding,
) -> dict[str, object]:
    return {
        "code": finding.code,
        "path": finding.path,
        "line": finding.line,
        "message": finding.message,
    }


def build_report(root: Path) -> dict[str, object]:
    """Build a fail-closed report for the assurance-covered candidate tree."""

    repository = audit_repository(root, require_clean_worktree=True)
    permission_blockers = audit_ci_permissions(root)
    action_blockers = audit_ci_actions(root)
    governance = audit_governance(root, _tracked_files(root))
    governance_blockers = preflight_findings(governance.findings)

    finding_rows = [_finding_row(finding) for finding in repository.findings]
    finding_rows.extend(_finding_row(finding) for finding in permission_blockers)
    finding_rows.extend(_finding_row(finding) for finding in action_blockers)
    finding_rows.extend(_finding_row(finding) for finding in governance_blockers)

    allowed_count = governance.finding_count - len(governance_blockers)
    return {
        "schema_version": _SCHEMA_VERSION,
        "passed": not finding_rows,
        "allowed_transaction_blocker_count": allowed_count,
        "finding_count": len(finding_rows),
        "findings": finding_rows,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Certify repository, architecture, capability, governance, and semantic "
            "invariants before final assurance artifacts and defect closure exist."
        )
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_report(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if report["passed"]:
        print(
            "Native assurance preflight passed; only finalization transaction "
            "blockers remain."
        )
        return 0
    print(
        f"Native assurance preflight failed with {report['finding_count']} finding(s)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
