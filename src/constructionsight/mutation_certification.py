"""Focused standard-library mutation certification for high-risk predicates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

SCHEMA_VERSION: Final = "constructionsight.mutation-report/v1"
CONTRACT_SCHEMA_VERSION: Final = "constructionsight.mutation-contract/v1"
CONTRACT_PATHS: Final = (
    "governance/mutation_contract.toml",
    "governance/mutation_contract_assurance.toml",
)
OVERRIDABLE_CASE_IDS: Final = frozenset(
    {"CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001"}
)


@dataclass(frozen=True)
class MutationCase:
    id: str
    path: str
    search: str
    replacement: str
    tests: tuple[str, ...]
    expected_output: str
    risk: str


@dataclass(frozen=True)
class MutationResult:
    id: str
    path: str
    status: str
    return_code: int | None
    output_sha256: str
    output_excerpt: str
    risk: str


class MutationContractError(RuntimeError):
    """Raised when the mutation contract cannot be evaluated safely."""


def _load_contract_file(
    root: Path,
    relative_path: str,
) -> tuple[int, tuple[MutationCase, ...]]:
    try:
        _relative, path = resolve_repository_file(root, relative_path)
    except RepositoryPathError as exc:
        raise MutationContractError(
            f"mutation contract is missing: {relative_path}"
        ) from exc
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise MutationContractError(
            f"mutation contract is malformed at {relative_path}: {exc}"
        ) from exc
    if payload.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise MutationContractError(
            f"unsupported mutation contract schema at {relative_path}"
        )
    allowed_top = {
        "schema_version",
        "contract_id",
        "execution",
        "timeout_seconds",
        "cases",
    }
    unknown_top = set(payload) - allowed_top
    if unknown_top:
        raise MutationContractError(
            f"unknown mutation contract fields at {relative_path}: {sorted(unknown_top)}"
        )
    timeout = payload.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout < 1 or timeout > 600:
        raise MutationContractError(
            f"mutation timeout must be between 1 and 600 seconds at {relative_path}"
        )
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise MutationContractError(
            f"mutation contract requires at least one case at {relative_path}"
        )
    required = {
        "id",
        "path",
        "search",
        "replacement",
        "tests",
        "expected_output",
        "risk",
    }
    cases: list[MutationCase] = []
    local_ids: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise MutationContractError("mutation cases must be tables")
        missing = required - set(raw)
        unknown = set(raw) - required
        if missing or unknown:
            raise MutationContractError(
                "mutation case fields disagree with schema; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        case_id = raw["id"]
        if not isinstance(case_id, str) or not case_id.startswith("CS-MUT-"):
            raise MutationContractError("mutation case ID must begin with CS-MUT-")
        if case_id in local_ids:
            raise MutationContractError(f"duplicate mutation case ID: {case_id}")
        local_ids.add(case_id)
        tests = raw["tests"]
        if not isinstance(tests, list) or not tests or not all(
            isinstance(value, str) and value.startswith("tests/") for value in tests
        ):
            raise MutationContractError(
                f"mutation case {case_id} requires explicit tests/ targets"
            )
        cases.append(
            MutationCase(
                id=case_id,
                path=str(raw["path"]),
                search=str(raw["search"]),
                replacement=str(raw["replacement"]),
                tests=tuple(tests),
                expected_output=str(raw["expected_output"]),
                risk=str(raw["risk"]),
            )
        )
    return timeout, tuple(cases)


def _load_contract(root: Path) -> tuple[int, tuple[MutationCase, ...]]:
    timeouts: set[int] = set()
    combined: dict[str, MutationCase] = {}
    for contract_index, relative_path in enumerate(CONTRACT_PATHS):
        timeout, cases = _load_contract_file(root, relative_path)
        timeouts.add(timeout)
        for case in cases:
            prior = combined.get(case.id)
            if prior is not None and (
                contract_index == 0 or case.id not in OVERRIDABLE_CASE_IDS
            ):
                raise MutationContractError(
                    f"duplicate mutation case ID across contracts: {case.id}"
                )
            combined[case.id] = case
    if len(timeouts) != 1:
        raise MutationContractError(
            f"mutation contract timeouts disagree: {sorted(timeouts)}"
        )
    cases = tuple(combined.values())
    for case in cases:
        _validate_case_path(root, case)
    return next(iter(timeouts)), cases


def _validate_case_path(root: Path, case: MutationCase) -> None:
    try:
        _relative, absolute = resolve_repository_file(
            root,
            case.path,
            required_prefix="src/constructionsight",
            required_suffix=".py",
        )
    except RepositoryPathError as exc:
        raise MutationContractError(f"unsafe mutation path: {case.path}") from exc
    if not case.path.startswith("src/constructionsight/"):
        raise MutationContractError(
            f"mutation case must target production Python: {case.path}"
        )
    content = absolute.read_text(encoding="utf-8")
    count = content.count(case.search)
    if count != 1:
        raise MutationContractError(
            f"mutation search must occur exactly once for {case.id}; found {count}"
        )
    if case.search == case.replacement:
        raise MutationContractError(f"mutation {case.id} does not change the target")
    for test in case.tests:
        try:
            resolve_repository_file(
                root,
                test.split("::", 1)[0],
                required_prefix="tests",
                required_suffix=".py",
            )
        except RepositoryPathError as exc:
            raise MutationContractError(
                f"mutation {case.id} references missing test target: {test}"
            ) from exc


def _copy_tracked_tree(root: Path, temporary_root: Path) -> None:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")
        raise MutationContractError(f"cannot enumerate tracked tree: {detail}")
    for raw_entry in completed.stdout.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_relative = raw_entry.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[2] != b"0":
            raise MutationContractError("git index entry has an unexpected shape")
        mode = fields[0]
        relative_text = raw_relative.decode("utf-8")
        if mode == b"120000":
            raise MutationContractError(
                f"tracked symbolic link is prohibited: {relative_text}"
            )
        try:
            relative, source = resolve_repository_file(root, relative_text)
        except RepositoryPathError as exc:
            raise MutationContractError(
                f"unsafe tracked path: {relative_text}"
            ) from exc
        destination = temporary_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_case(root: Path, case: MutationCase, timeout: int) -> MutationResult:
    with tempfile.TemporaryDirectory(prefix="constructionsight-mutant-") as directory:
        temporary_root = Path(directory)
        _copy_tracked_tree(root, temporary_root)
        target = temporary_root / case.path
        content = target.read_text(encoding="utf-8")
        target.write_text(
            content.replace(case.search, case.replacement, 1),
            encoding="utf-8",
        )
        environment = os.environ.copy()
        original_pythonpath = environment.get("PYTHONPATH")
        values = [str(temporary_root / "src")]
        if original_pythonpath:
            values.append(original_pythonpath)
        environment["PYTHONPATH"] = os.pathsep.join(values)
        command = [
            sys.executable,
            "-m",
            "pytest",
            "--strict-config",
            "--strict-markers",
            "-W",
            "error",
            "-q",
            *case.tests,
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=temporary_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = completed.stdout + completed.stderr
            if completed.returncode == 0:
                status = "survived"
            elif case.expected_output not in output:
                status = "invalid_failure"
            else:
                status = "killed"
            return_code: int | None = completed.returncode
        except subprocess.TimeoutExpired as exc:
            output = _timeout_output(exc.stdout) + _timeout_output(exc.stderr)
            status = "timeout"
            return_code = None
        digest = hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()
        excerpt = output[-4000:]
        return MutationResult(
            id=case.id,
            path=case.path,
            status=status,
            return_code=return_code,
            output_sha256=digest,
            output_excerpt=excerpt,
            risk=case.risk,
        )


def run_mutation_certification(
    root: Path,
    *,
    case_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Run declared mutants in isolated source overlays and return stable evidence."""

    repository_root = root.resolve()
    timeout, cases = _load_contract(repository_root)
    selected = tuple(
        case for case in cases if case_ids is None or case.id in case_ids
    )
    if case_ids is not None:
        missing = case_ids - {case.id for case in selected}
        if missing:
            raise MutationContractError(
                f"unknown requested mutation IDs: {sorted(missing)}"
            )
    results = tuple(_run_case(repository_root, case, timeout) for case in selected)
    killed = sum(result.status == "killed" for result in results)
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "case_count": len(results),
        "killed_count": killed,
        "survived_count": sum(result.status == "survived" for result in results),
        "invalid_failure_count": sum(
            result.status == "invalid_failure" for result in results
        ),
        "timeout_count": sum(result.status == "timeout" for result in results),
        "passed": bool(results) and killed == len(results),
        "results": [asdict(result) for result in results],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run focused high-risk mutation certification."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json-output", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run mutation certification and return a process status."""

    arguments = _parser().parse_args(argv)
    try:
        report = run_mutation_certification(
            arguments.root,
            case_ids=(
                frozenset(arguments.case_id) if arguments.case_id else None
            ),
        )
    except (OSError, UnicodeError, MutationContractError) as exc:
        print(f"Mutation certification could not run: {exc}", file=sys.stderr)
        return 2
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized, encoding="utf-8")
    if arguments.json_output:
        print(serialized, end="")
    elif report["passed"]:
        print(
            "Mutation certification passed: "
            f"{report['killed_count']}/{report['case_count']} mutants killed."
        )
    else:
        print(
            "Mutation certification failed: "
            f"killed={report['killed_count']}, survived={report['survived_count']}, "
            f"invalid={report['invalid_failure_count']}, "
            f"timeout={report['timeout_count']}."
        )
        for result in report["results"]:
            if result["status"] != "killed":
                print(f"- {result['id']}: {result['status']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
