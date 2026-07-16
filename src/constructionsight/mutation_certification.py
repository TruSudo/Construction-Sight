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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Sequence

SCHEMA_VERSION: Final = "constructionsight.mutation-report/v1"
CONTRACT_SCHEMA_VERSION: Final = "constructionsight.mutation-contract/v1"


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


def _load_contract(root: Path) -> tuple[int, tuple[MutationCase, ...]]:
    path = root / "governance/mutation_contract.toml"
    if not path.is_file():
        raise MutationContractError("mutation contract is missing")
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise MutationContractError(f"mutation contract is malformed: {exc}") from exc
    if payload.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise MutationContractError("unsupported mutation contract schema")
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
            f"unknown mutation contract fields: {sorted(unknown_top)}"
        )
    timeout = payload.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout < 1 or timeout > 600:
        raise MutationContractError("mutation timeout must be between 1 and 600 seconds")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise MutationContractError("mutation contract requires at least one case")
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
    ids: set[str] = set()
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
        if case_id in ids:
            raise MutationContractError(f"duplicate mutation case ID: {case_id}")
        ids.add(case_id)
        tests = raw["tests"]
        if not isinstance(tests, list) or not tests or not all(
            isinstance(value, str) and value.startswith("tests/") for value in tests
        ):
            raise MutationContractError(
                f"mutation case {case_id} requires explicit tests/ targets"
            )
        case = MutationCase(
            id=case_id,
            path=str(raw["path"]),
            search=str(raw["search"]),
            replacement=str(raw["replacement"]),
            tests=tuple(tests),
            expected_output=str(raw["expected_output"]),
            risk=str(raw["risk"]),
        )
        _validate_case_path(root, case)
        cases.append(case)
    return timeout, tuple(cases)


def _validate_case_path(root: Path, case: MutationCase) -> None:
    relative = Path(case.path)
    if relative.is_absolute() or ".." in relative.parts:
        raise MutationContractError(f"unsafe mutation path: {case.path}")
    if not case.path.startswith("src/constructionsight/") or relative.suffix != ".py":
        raise MutationContractError(
            f"mutation case must target production Python: {case.path}"
        )
    absolute = root / relative
    if not absolute.is_file():
        raise MutationContractError(f"mutation target is missing: {case.path}")
    content = absolute.read_text(encoding="utf-8")
    count = content.count(case.search)
    if count != 1:
        raise MutationContractError(
            f"mutation search must occur exactly once for {case.id}; found {count}"
        )
    if case.search == case.replacement:
        raise MutationContractError(f"mutation {case.id} does not change the target")
    for test in case.tests:
        test_path = root / test.split("::", 1)[0]
        if not test_path.is_file():
            raise MutationContractError(
                f"mutation {case.id} references missing test target: {test}"
            )


def _run_case(root: Path, case: MutationCase, timeout: int) -> MutationResult:
    with tempfile.TemporaryDirectory(prefix="constructionsight-mutant-") as directory:
        temporary_root = Path(directory)
        overlay_src = temporary_root / "src"
        shutil.copytree(root / "src/constructionsight", overlay_src / "constructionsight")
        target = temporary_root / case.path
        content = target.read_text(encoding="utf-8")
        target.write_text(
            content.replace(case.search, case.replacement, 1),
            encoding="utf-8",
        )
        environment = os.environ.copy()
        original_pythonpath = environment.get("PYTHONPATH")
        values = [str(overlay_src), str(root / "src")]
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
                cwd=root,
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
            output = (exc.stdout or "") + (exc.stderr or "")
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
