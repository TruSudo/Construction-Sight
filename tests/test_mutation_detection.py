from __future__ import annotations

import ast
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import constructionsight.mutation_certification as mutation_certification

from constructionsight.governance_certification_core import _mutation_lines
from constructionsight.mutation_certification import (
    MutationCase,
    MutationContractError,
    _classify_mutant,
    _read_test_evidence,
    _run_case,
    _validate_case_path,
)


def test_string_replace_is_not_classified_as_filesystem_mutation() -> None:
    tree = ast.parse("value = source.replace('old', 'new')\n")

    assert _mutation_lines(tree) == ()


def test_path_write_is_classified_as_filesystem_mutation() -> None:
    tree = ast.parse(
        "from pathlib import Path\n"
        "output_path = Path('result.json')\n"
        "output_path.write_text('{}', encoding='utf-8')\n"
    )

    assert _mutation_lines(tree) == (3,)


def test_resolved_path_replace_is_classified_as_filesystem_mutation() -> None:
    tree = ast.parse(
        "from pathlib import Path\n"
        "temporary_path = Path('result.tmp')\n"
        "temporary_path.resolve().replace(Path('result.json'))\n"
    )

    assert _mutation_lines(tree) == (3,)


def test_mutation_contract_rejects_symlinked_source_and_test_references(
    tmp_path: Path,
) -> None:
    outside_source = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside_source.write_text("VALUE = True\n", encoding="utf-8")
    source = tmp_path / "src/constructionsight/target.py"
    source.parent.mkdir(parents=True)
    source.symlink_to(outside_source)
    tests = tmp_path / "tests"
    tests.mkdir()
    outside_test = tmp_path.parent / f"{tmp_path.name}-test.py"
    outside_test.write_text("def test_target() -> None:\n    assert True\n", encoding="utf-8")
    (tests / "test_target.py").symlink_to(outside_test)
    case = MutationCase(
        id="CS-MUT-TEST",
        path="src/constructionsight/target.py",
        search="VALUE = True",
        replacement="VALUE = False",
        tests=("tests/test_target.py::test_target",),
        expected_output="failed",
        risk="symlink escape",
    )

    with pytest.raises(MutationContractError):
        _validate_case_path(tmp_path, case)

    source.unlink()
    source.write_text("VALUE = True\n", encoding="utf-8")
    with pytest.raises(MutationContractError):
        _validate_case_path(tmp_path, case)


def _runner_fixture(
    tmp_path: Path,
    body: str,
    *,
    replacement: str = "VALUE = False",
    expected_output: str = "test_target",
) -> MutationCase:
    source = tmp_path / "src/constructionsight"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    (source / "mutation_sample.py").write_text("VALUE = True\n", encoding="utf-8")
    test_root = tmp_path / "tests"
    test_root.mkdir()
    (test_root / "__init__.py").write_text("", encoding="utf-8")
    (test_root / "test_sample.py").write_text(
        "import pytest\n"
        "from constructionsight import mutation_sample\n\n" + body,
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "src", "tests"],
        check=True,
        capture_output=True,
    )
    return MutationCase(
        id="CS-MUT-RUNNER-FIXTURE",
        path="src/constructionsight/mutation_sample.py",
        search="VALUE = True",
        replacement=replacement,
        tests=("tests/test_sample.py::test_target",),
        expected_output=expected_output,
        risk="mutation verdict fixture",
    )


def _verdict_case() -> MutationCase:
    return MutationCase(
        id="CS-MUT-VERDICT-FIXTURE",
        path="src/constructionsight/mutation_sample.py",
        search="VALUE = True",
        replacement="VALUE = False",
        tests=("tests/test_sample.py::test_target",),
        expected_output="test_target",
        risk="structured mutation evidence fixture",
    )


def _junit_report(
    tmp_path: Path,
    *,
    file_name: str = "result.xml",
    test_name: str = "test_target",
    failure: str | None = None,
) -> Path:
    root = ET.Element("testsuites")
    suite = ET.SubElement(
        root, "testsuite",
        tests="1", failures=str(int(failure is not None)), errors="0", skipped="0",
    )
    testcase = ET.SubElement(
        suite, "testcase",
        file="tests/test_sample.py", classname="tests.test_sample", name=test_name,
    )
    if failure is not None:
        node = ET.SubElement(testcase, "failure", message=failure)
        node.text = failure
    path = tmp_path / file_name
    path.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
    return path


def test_mutation_runner_kills_assertion_after_clean_baseline(tmp_path: Path) -> None:
    case = _runner_fixture(
        tmp_path, "def test_target():\n    assert mutation_sample.VALUE is True\n"
    )

    result = _run_case(tmp_path, case, 45)

    assert result.status == "killed"
    assert result.return_code == 1


def test_mutation_runner_retains_real_survivor(tmp_path: Path) -> None:
    case = _runner_fixture(
        tmp_path,
        "def test_target():\n    assert mutation_sample.VALUE is True\n",
        replacement="VALUE = bool(1)",
    )

    result = _run_case(tmp_path, case, 45)

    assert result.status == "survived"
    assert result.return_code == 0


def test_mutation_runner_accepts_missing_expected_exception_witness(tmp_path: Path) -> None:
    case = _runner_fixture(
        tmp_path,
        "def test_target():\n"
        "    with pytest.raises(ValueError):\n"
        "        if mutation_sample.VALUE:\n"
        "            raise ValueError('denied')\n",
    )

    assert _run_case(tmp_path, case, 45).status == "killed"


def test_mutation_runner_rejects_failed_baseline(tmp_path: Path) -> None:
    case = _runner_fixture(tmp_path, "def test_target():\n    assert False\n")

    result = _run_case(tmp_path, case, 45)

    assert result.status == "invalid_failure"
    assert "\nmutant:\n" not in result.output_excerpt


@pytest.mark.parametrize(
    ("replacement", "body"),
    [
        ("VALUE =", "def test_target():\n    assert mutation_sample.VALUE\n"),
        (
            "raise ImportError('test_target')",
            "def test_target():\n    assert mutation_sample.VALUE\n",
        ),
        (
            "VALUE = False",
            "@pytest.fixture\n"
            "def ready():\n"
            "    if not mutation_sample.VALUE:\n"
            "        raise RuntimeError('test_target setup')\n"
            "def test_target(ready):\n"
            "    assert True\n",
        ),
        (
            "VALUE = False",
            "@pytest.fixture\n"
            "def ready():\n"
            "    yield\n"
            "    if not mutation_sample.VALUE:\n"
            "        raise RuntimeError('test_target teardown')\n"
            "def test_target(ready):\n"
            "    assert True\n",
        ),
        (
            "VALUE = False",
            "def test_target():\n"
            "    if not mutation_sample.VALUE:\n"
            "        raise RuntimeError('test_target call')\n"
            "    assert True\n",
        ),
        (
            "VALUE = False",
            "@pytest.fixture\n"
            "def ready():\n"
            "    yield\n"
            "    if not mutation_sample.VALUE:\n"
            "        raise RuntimeError('test_target teardown')\n"
            "def test_target(ready):\n"
            "    assert mutation_sample.VALUE is True\n",
        ),
    ],
    ids=["syntax", "import", "setup", "teardown", "runtime", "failure-and-error"],
)
def test_mutation_runner_rejects_nonsemantic_failures(
    tmp_path: Path, replacement: str, body: str,
) -> None:
    case = _runner_fixture(tmp_path, body, replacement=replacement)

    assert _run_case(tmp_path, case, 45).status == "invalid_failure"


@pytest.mark.parametrize("return_code", [2, 3, 4, 5, 6, -9])
def test_mutation_verdict_rejects_non_test_exit_codes(
    tmp_path: Path, return_code: int,
) -> None:
    case = _verdict_case()
    baseline = _read_test_evidence(_junit_report(tmp_path), case)
    evidence = _read_test_evidence(
        _junit_report(tmp_path, file_name="mutant.xml", failure="assert False"), case
    )
    assert baseline is not None
    assert evidence is not None

    assert _classify_mutant(return_code, baseline, evidence, case) == "invalid_failure"


def test_mutation_verdict_requires_retained_report(tmp_path: Path) -> None:
    case = _verdict_case()
    baseline = _read_test_evidence(_junit_report(tmp_path), case)
    assert baseline is not None
    assert _read_test_evidence(tmp_path / "missing.xml", case) is None

    assert _classify_mutant(1, baseline, None, case) == "invalid_failure"


def test_mutation_verdict_rejects_changed_parameter_selection(tmp_path: Path) -> None:
    case = _verdict_case()
    baseline = _read_test_evidence(
        _junit_report(tmp_path, test_name="test_target[one]"), case
    )
    evidence = _read_test_evidence(
        _junit_report(
            tmp_path, file_name="mutant.xml",
            test_name="test_target[two]", failure="assert False",
        ),
        case,
    )
    assert baseline is not None
    assert evidence is not None

    assert _classify_mutant(1, baseline, evidence, case) == "invalid_failure"


@pytest.mark.parametrize(
    "damage",
    ["malformed", "empty", "count", "wrong-node", "duplicate", "runtime", "doctype", "skipped"],
)
def test_mutation_report_rejects_invalid_evidence(tmp_path: Path, damage: str) -> None:
    case = _verdict_case()
    path = _junit_report(tmp_path, failure="assert False")
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    suite = root.find("testsuite")
    assert suite is not None
    testcase = suite.find("testcase")
    assert testcase is not None
    if damage == "empty":
        suite.remove(testcase)
        suite.set("tests", "0")
        suite.set("failures", "0")
    elif damage == "count":
        suite.set("tests", "2")
    elif damage == "wrong-node":
        testcase.set("name", "test_other")
    elif damage == "duplicate":
        suite.append(ET.fromstring(ET.tostring(testcase)))
        suite.set("tests", "2")
        suite.set("failures", "2")
    elif damage == "skipped":
        suite.set("skipped", "1")
        ET.SubElement(testcase, "skipped", message="skipped result fixture")
    elif damage == "runtime":
        failure = testcase.find("failure")
        assert failure is not None
        failure.set("message", "RuntimeError: test_target")
    serialized = ET.tostring(root, encoding="unicode")
    if damage == "malformed":
        serialized = "<broken"
    elif damage == "doctype":
        serialized = '<!DOCTYPE testsuites [<!ENTITY x "expanded">]>' + serialized
    path.write_text(serialized, encoding="utf-8")

    assert _read_test_evidence(path, case) is None


def test_mutation_runner_timeout_is_not_a_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _runner_fixture(tmp_path, "def test_target():\n    assert True\n")

    def timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("pytest", 1, output=b"partial", stderr=b"timed out")

    monkeypatch.setattr(mutation_certification, "_execute_test_run", timeout)

    result = _run_case(tmp_path, case, 45)

    assert result.status == "timeout"
    assert result.return_code is None
    assert "partial" in result.output_excerpt


def test_mutation_verdict_requires_expected_failure_marker(tmp_path: Path) -> None:
    baseline_case = _verdict_case()
    case = MutationCase(
        id=baseline_case.id,
        path=baseline_case.path,
        search=baseline_case.search,
        replacement=baseline_case.replacement,
        tests=baseline_case.tests,
        expected_output="unrelated success message",
        risk=baseline_case.risk,
    )
    baseline = _read_test_evidence(_junit_report(tmp_path), case)
    evidence = _read_test_evidence(
        _junit_report(tmp_path, file_name="mutant.xml", failure="assert False"), case
    )
    assert baseline is not None
    assert evidence is not None

    assert _classify_mutant(1, baseline, evidence, case) == "invalid_failure"


def test_mutation_runner_provides_isolated_tracked_file_index(tmp_path: Path) -> None:
    case = _runner_fixture(
        tmp_path,
        "import subprocess\n"
        "def test_target():\n"
        "    tracked = subprocess.check_output(['git', 'ls-files'], text=True)\n"
        "    assert 'src/constructionsight/mutation_sample.py' in tracked\n"
        "    assert mutation_sample.VALUE is True\n",
    )

    assert _run_case(tmp_path, case, 45).status == "killed"
