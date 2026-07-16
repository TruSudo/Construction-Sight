"""Canonical repository and semantic governance certification entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from constructionsight.governance_certification import audit_governance
from constructionsight.repository_certification import (
    CertificationError,
    _tracked_files,
    audit_repository,
)

SCHEMA_VERSION: Final = "constructionsight.repository-certification/v2"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit the complete tracked tree and semantic governance."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--require-clean-worktree", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def certify_repository(
    root: Path,
    *,
    require_clean_worktree: bool = False,
) -> dict[str, Any]:
    """Return deterministic versioned certification for one exact tree."""

    repository_root = root.resolve()
    base_report = audit_repository(
        repository_root,
        require_clean_worktree=require_clean_worktree,
    )
    governance_report = audit_governance(
        repository_root,
        _tracked_files(repository_root),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": base_report.passed and governance_report.passed,
        "finding_count": base_report.finding_count + governance_report.finding_count,
        "repository": base_report.to_dict(),
        "governance": governance_report.to_dict(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run exact-tree certification and return a process status."""

    arguments = _parser().parse_args(argv)
    try:
        report = certify_repository(
            arguments.root,
            require_clean_worktree=arguments.require_clean_worktree,
        )
    except CertificationError as exc:
        print(f"Certification audit could not run: {exc}", file=sys.stderr)
        return 2

    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized, encoding="utf-8")
    if arguments.json_output:
        print(serialized, end="")
    elif report["passed"]:
        governance = report["governance"]
        metrics = governance["metrics"]
        repository = report["repository"]
        print(
            "Repository certification passed: "
            f"{repository['tracked_file_count']} tracked files, "
            f"{metrics['architecture_nodes']} architecture nodes, "
            f"{metrics['architecture_edges']} edges, "
            f"{metrics['architecture_cycles']} cycles, 0 findings."
        )
    else:
        print(f"Repository certification failed with {report['finding_count']} finding(s).")
        for group in ("repository", "governance"):
            for finding in report[group]["findings"]:
                location = finding["path"]
                if finding["line"] is not None:
                    location = f"{location}:{finding['line']}"
                print(f"- {finding['code']} {location}: {finding['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
