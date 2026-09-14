"""Pre-assurance structural certification for an exact ConstructionSight candidate."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from constructionsight.governance_certification import audit_governance
from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.repository_certification import _tracked_files

_SCHEMA_VERSION: Final = "constructionsight.assurance-preflight/v1"
_ALLOWED_TRANSACTION_BLOCKERS: Final = frozenset(
    {"ASSURANCE-001", "DEFECT-ACTIVE-001"}
)


def preflight_findings(
    findings: Sequence[GovernanceFinding],
) -> tuple[GovernanceFinding, ...]:
    """Return findings that are not expected pre-assurance transaction blockers."""

    return tuple(
        finding
        for finding in findings
        if finding.code not in _ALLOWED_TRANSACTION_BLOCKERS
    )


def build_report(root: Path) -> dict[str, object]:
    """Build a fail-closed report for the assurance-covered candidate tree."""

    governance = audit_governance(root, _tracked_files(root))
    blockers = preflight_findings(governance.findings)
    return {
        "schema_version": _SCHEMA_VERSION,
        "passed": not blockers,
        "allowed_transaction_blocker_count": (
            governance.finding_count - len(blockers)
        ),
        "finding_count": len(blockers),
        "findings": [
            {
                "code": finding.code,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in blockers
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Certify architecture, capability, governance, and semantic invariants "
            "before final assurance artifacts and defect closure exist."
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
