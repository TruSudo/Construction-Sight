from __future__ import annotations

import ast

from constructionsight.governance_certification_core import _mutation_lines


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
