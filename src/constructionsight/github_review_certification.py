"""Verify an independent-review artifact against one GitHub pull-request review."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = "constructionsight.github-review-certification/v1"
_REVIEWER_PATTERN = re.compile(
    r"github:(?P<login>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)#"
    r"(?P<review_id>[1-9][0-9]*)"
)
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def parse_bound_reviewer(value: object) -> tuple[str, int]:
    """Return the GitHub login and review ID encoded by the review artifact."""

    if not isinstance(value, str):
        raise ValueError("reviewer must bind a GitHub login and review ID")
    match = _REVIEWER_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("reviewer must match github:<login>#<positive-review-id>")
    return match.group("login"), int(match.group("review_id"))


def verify_github_review_binding(
    review_report: Mapping[str, Any],
    github_review: Mapping[str, Any],
    *,
    pr_author: str,
    repository_owner: str,
) -> tuple[str, ...]:
    """Return deterministic findings for the external GitHub review binding."""

    findings: list[str] = []
    try:
        bound_login, bound_review_id = parse_bound_reviewer(review_report.get("reviewer"))
    except ValueError as exc:
        findings.append(str(exc))
        return tuple(findings)

    reviewed_commit = review_report.get("reviewed_commit")
    if not isinstance(reviewed_commit, str) or _COMMIT_PATTERN.fullmatch(
        reviewed_commit
    ) is None:
        findings.append("reviewed_commit must be a full lowercase commit SHA")

    if not _nonblank(pr_author) or not _nonblank(repository_owner):
        findings.append("PR author and repository owner identities must be nonblank")
    else:
        reviewer_key = bound_login.casefold()
        if reviewer_key == pr_author.casefold():
            findings.append("independent reviewer must differ from the PR author")
        if reviewer_key == repository_owner.casefold():
            findings.append("independent reviewer must differ from the repository owner")

    review_id = github_review.get("id")
    if isinstance(review_id, bool) or not isinstance(review_id, int):
        findings.append("GitHub review ID must be an integer")
    elif review_id != bound_review_id:
        findings.append("GitHub review ID does not match the artifact binding")

    if github_review.get("state") != "APPROVED":
        findings.append("GitHub review state must be APPROVED")

    user = github_review.get("user")
    if not isinstance(user, Mapping):
        findings.append("GitHub review user must be an object")
    else:
        login = user.get("login")
        if not isinstance(login, str) or login.casefold() != bound_login.casefold():
            findings.append("GitHub reviewer login does not match the artifact binding")
        if user.get("type") != "User":
            findings.append("independent GitHub reviewer must be a human User identity")

    commit_id = github_review.get("commit_id")
    if not isinstance(commit_id, str) or _COMMIT_PATTERN.fullmatch(commit_id) is None:
        findings.append("GitHub review commit_id must be a full lowercase commit SHA")
    elif isinstance(reviewed_commit, str) and commit_id != reviewed_commit:
        findings.append("GitHub review commit does not match reviewed_commit")

    return tuple(findings)


def build_report(
    review_report: Mapping[str, Any],
    github_review: Mapping[str, Any],
    *,
    pr_author: str,
    repository_owner: str,
) -> dict[str, Any]:
    """Build the deterministic CI report for one external review verification."""

    findings = verify_github_review_binding(
        review_report,
        github_review,
        pr_author=pr_author,
        repository_owner=repository_owner,
    )
    reviewer = review_report.get("reviewer")
    reviewed_commit = review_report.get("reviewed_commit")
    return {
        "schema_version": _SCHEMA_VERSION,
        "passed": not findings,
        "reviewer": reviewer if isinstance(reviewer, str) else None,
        "reviewed_commit": reviewed_commit if isinstance(reviewed_commit, str) else None,
        "github_review_id": github_review.get("id"),
        "findings": list(findings),
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload at {path} must be an object")
    return payload


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify ConstructionSight independent review against GitHub evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_id = subparsers.add_parser(
        "review-id", help="Print the GitHub review ID bound by the review artifact."
    )
    review_id.add_argument("--review-artifact", type=Path, required=True)

    verify = subparsers.add_parser(
        "verify", help="Verify one fetched GitHub review against the artifact."
    )
    verify.add_argument("--review-artifact", type=Path, required=True)
    verify.add_argument("--github-review", type=Path, required=True)
    verify.add_argument("--pr-author", required=True)
    verify.add_argument("--repository-owner", required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by canonical CI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        review_report = _read_json_object(args.review_artifact)
        if args.command == "review-id":
            _, review_id = parse_bound_reviewer(review_report.get("reviewer"))
            print(review_id)
            return 0

        github_review = _read_json_object(args.github_review)
        report = build_report(
            review_report,
            github_review,
            pr_author=args.pr_author,
            repository_owner=args.repository_owner,
        )
        _write_report(args.output, report)
    except ValueError as exc:
        parser.exit(1, f"github review certification failed: {exc}\n")

    if report["passed"]:
        print("Independent GitHub review certification passed.")
        return 0
    for finding in report["findings"]:
        print(f"- {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
