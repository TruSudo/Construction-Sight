"""Verify optional independent-human assurance against GitHub source evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = "constructionsight.github-review-certification/v1"
_ASSURANCE_SCHEMA_VERSION = "constructionsight.assurance-review/v1"
_REVIEWER_PATTERN = re.compile(
    r"github:(?P<login>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)#"
    r"(?P<review_id>[1-9][0-9]*)"
)
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _positive_integer(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def parse_bound_reviewer(value: object) -> tuple[str, int]:
    """Return the GitHub login and review ID encoded by the assurance artifact."""

    if not isinstance(value, str):
        raise ValueError("reviewer must bind a GitHub login and review ID")
    match = _REVIEWER_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("reviewer must match github:<login>#<positive-review-id>")
    return match.group("login"), int(match.group("review_id"))


def verify_github_review_binding(
    assurance_report: Mapping[str, Any],
    github_review: Mapping[str, Any],
    github_pull_request: Mapping[str, Any],
    *,
    repository_owner: str,
) -> tuple[str, ...]:
    """Return deterministic findings for independent-human GitHub assurance."""

    findings: list[str] = []
    if assurance_report.get("schema_version") != _ASSURANCE_SCHEMA_VERSION:
        findings.append("assurance report schema is unsupported")
    if assurance_report.get("assurance_mode") != "independent_human":
        findings.append("GitHub approval only verifies independent_human assurance mode")
    if assurance_report.get("independence_claim") != "independent_human":
        findings.append("assurance report does not make the exact human-independence claim")
    try:
        bound_login, bound_review_id = parse_bound_reviewer(
            assurance_report.get("reviewer")
        )
    except ValueError as exc:
        findings.append(str(exc))
        return tuple(findings)

    reviewed_commit = assurance_report.get("reviewed_commit")
    if not isinstance(reviewed_commit, str) or _COMMIT_PATTERN.fullmatch(
        reviewed_commit
    ) is None:
        findings.append("reviewed_commit must be a full lowercase commit SHA")

    bound_pr_number = assurance_report.get("pull_request_number")
    if not _positive_integer(bound_pr_number):
        findings.append("assurance report must bind a positive pull-request number")

    source_pr_number = github_pull_request.get("number")
    if not _positive_integer(source_pr_number):
        findings.append("GitHub pull-request number must be a positive integer")
    elif source_pr_number != bound_pr_number:
        findings.append("GitHub pull request does not match the assurance binding")

    pr_user = github_pull_request.get("user")
    pr_author: str | None = None
    if not isinstance(pr_user, Mapping) or not _nonblank(pr_user.get("login")):
        findings.append("GitHub pull-request author must be a user login")
    else:
        pr_author = str(pr_user["login"])

    if not _nonblank(repository_owner):
        findings.append("repository owner identity must be nonblank")
    else:
        reviewer_key = bound_login.casefold()
        if pr_author is not None and reviewer_key == pr_author.casefold():
            findings.append("independent reviewer must differ from the PR author")
        if reviewer_key == repository_owner.casefold():
            findings.append("independent reviewer must differ from the repository owner")

    review_id = github_review.get("id")
    if isinstance(review_id, bool) or not isinstance(review_id, int):
        findings.append("GitHub review ID must be an integer")
    elif review_id != bound_review_id:
        findings.append("GitHub review ID does not match the assurance binding")

    if github_review.get("state") != "APPROVED":
        findings.append("GitHub review state must be APPROVED")

    user = github_review.get("user")
    if not isinstance(user, Mapping):
        findings.append("GitHub review user must be an object")
    else:
        login = user.get("login")
        if not isinstance(login, str) or login.casefold() != bound_login.casefold():
            findings.append("GitHub reviewer login does not match the assurance binding")
        if user.get("type") != "User":
            findings.append("independent GitHub reviewer must be a human User identity")

    commit_id = github_review.get("commit_id")
    if not isinstance(commit_id, str) or _COMMIT_PATTERN.fullmatch(commit_id) is None:
        findings.append("GitHub review commit_id must be a full lowercase commit SHA")
    elif isinstance(reviewed_commit, str) and commit_id != reviewed_commit:
        findings.append("GitHub review commit does not match reviewed_commit")

    return tuple(findings)


def build_report(
    assurance_report: Mapping[str, Any],
    github_review: Mapping[str, Any],
    github_pull_request: Mapping[str, Any],
    *,
    repository_owner: str,
) -> dict[str, Any]:
    """Build the deterministic CI report for one human-review verification."""

    findings = verify_github_review_binding(
        assurance_report,
        github_review,
        github_pull_request,
        repository_owner=repository_owner,
    )
    reviewer = assurance_report.get("reviewer")
    reviewed_commit = assurance_report.get("reviewed_commit")
    return {
        "schema_version": _SCHEMA_VERSION,
        "passed": not findings,
        "reviewer": reviewer if isinstance(reviewer, str) else None,
        "reviewed_commit": reviewed_commit if isinstance(reviewed_commit, str) else None,
        "pull_request_number": assurance_report.get("pull_request_number"),
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
        description="Verify ConstructionSight human assurance against GitHub evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_id = subparsers.add_parser(
        "review-id", help="Print the GitHub review ID bound by the assurance artifact."
    )
    review_id.add_argument("--review-artifact", type=Path, required=True)

    verify = subparsers.add_parser(
        "verify", help="Verify fetched GitHub pull-request and review evidence."
    )
    verify.add_argument("--review-artifact", type=Path, required=True)
    verify.add_argument("--github-review", type=Path, required=True)
    verify.add_argument("--github-pull-request", type=Path, required=True)
    verify.add_argument("--repository-owner", required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by canonical CI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        assurance_report = _read_json_object(args.review_artifact)
        if args.command == "review-id":
            if assurance_report.get("assurance_mode") != "independent_human":
                raise ValueError("review-id requires independent_human assurance mode")
            _, review_id = parse_bound_reviewer(assurance_report.get("reviewer"))
            print(review_id)
            return 0

        github_review = _read_json_object(args.github_review)
        github_pull_request = _read_json_object(args.github_pull_request)
        report = build_report(
            assurance_report,
            github_review,
            github_pull_request,
            repository_owner=args.repository_owner,
        )
        _write_report(args.output, report)
    except ValueError as exc:
        parser.exit(1, f"github review certification failed: {exc}\n")

    if report["passed"]:
        print("Independent human GitHub review certification passed.")
        return 0
    for finding in report["findings"]:
        print(f"- {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
