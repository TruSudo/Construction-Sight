"""Production CI tests the shipped dependencies and product, without owner review prerequisites."""

from pathlib import Path


def test_ci_uses_actual_project_environment_and_mandatory_gates() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "fetch-depth: 0" in workflow
    assert "-e '.[dev]'" in workflow
    for command in (
        "python -m pytest -q",
        "python -m ruff check src tests",
        "python -m mypy src/constructionsight",
        "node --check",
        "python -m pip_audit --strict --no-deps --disable-pip",
    ):
        assert command in workflow
    assert "continue-on-error" not in workflow
    assert "owner_acceptance_certification" not in workflow
    assert "repository_certification" not in workflow


def test_browser_workflow_does_not_repeat_full_python_suite() -> None:
    workflow = Path(".github/workflows/command-center-visual.yml").read_text()
    assert "python -m pytest" not in workflow
    assert "tests/ui/click_through.js" in workflow
    assert "compare_mockup.py" in workflow
    assert "push:" in workflow
