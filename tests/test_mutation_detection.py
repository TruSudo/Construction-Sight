from __future__ import annotations

import ast
from pathlib import Path

import pytest

from constructionsight.governance_certification_core import _mutation_lines
from constructionsight.mutation_certification import (
    MutationCase,
    MutationContractError,
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
