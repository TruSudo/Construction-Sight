"""CS-SR-072: bind the full workflow and exercise the declared shell at launch."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest

from constructionsight.ci_execution_certification import audit_ci_execution
from constructionsight.vulnerability_ci_certification import audit_vulnerability_job

_SHELL = "/bin/bash --noprofile --norc -p -e -o pipefail {0}"
_LEGACY_SHELL = "/bin/bash --noprofile --norc -e -o pipefail {0}"


def _workflow() -> str:
    return Path(".github/workflows/ci.yml").read_text(encoding="utf-8")


def _write(root: Path, workflow: str) -> None:
    path = root / ".github/workflows/ci.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow, encoding="utf-8")


def _declared_shells() -> list[str]:
    return re.findall(r"^        shell: (.+)$", _workflow(), re.MULTILINE)


def _run(script: Path, shell: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command = [str(script) if part == "{0}" else part for part in shlex.split(shell)]
    return subprocess.run(
        command,
        env={"PATH": os.defpath, "BASH_ENV": "/dev/null", **environment},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_complete_reviewed_workflow_passes(tmp_path: Path) -> None:
    _write(tmp_path, _workflow())
    assert audit_ci_execution(tmp_path) == ()


def test_every_ci_run_step_uses_the_reviewed_isolated_shell() -> None:
    steps = re.split(r"^      - name: ", _workflow(), flags=re.MULTILINE)[1:]
    run_steps = [block for block in steps if re.search(r"^        run:", block, re.MULTILINE)]
    assert len(run_steps) == 25
    for step in run_steps:
        declarations = re.findall(r"^        shell: (.+)$", step, re.MULTILINE)
        assert declarations == [_SHELL], step.splitlines()[0]


@pytest.mark.parametrize(
    "before,after",
    [
        ("env:\n", "env:\n  SHELLOPTS: noexec\n"),
        ("env:\n", "env:\n  BASH_ENV: /tmp/startup.sh\n"),
        ("env:\n", "env:\n  BASH_FUNC_test%%: '() { return 0; }'\n"),
        ("env:\n", "env:\n  PATH: /tmp/unreviewed-bin\n"),
        ("env:\n", "env:\n  PYTHONHOME: /tmp/unreviewed-python\n"),
        ("env:\n", "env:\n  LD_PRELOAD: /tmp/unreviewed.so\n"),
        ("/tmp/constructionsight-reports", "/tmp/other-reports"),
        ("jobs:\n", "defaults:\n  run:\n    working-directory: /tmp\njobs:\n"),
        ("  quality:\n", "  quality:\n    env:\n      SHELLOPTS: noexec\n"),
        ("  quality:\n", "  quality:\n    defaults:\n      run:\n        shell: sh\n"),
        ("          fetch-depth: 0", "          fetch-depth: 1"),
        ("id: assurance-preflight", "id: assurance-preflight-disabled"),
    ],
)
def test_changes_outside_vulnerability_job_fail_closed(
    tmp_path: Path, before: str, after: str
) -> None:
    workflow = _workflow()
    assert before in workflow
    _write(tmp_path, workflow.replace(before, after, 1))
    # The old literal-job certifier accepts these changes; the whole-workflow seal must not.
    assert audit_vulnerability_job(tmp_path) == ()
    assert [finding.code for finding in audit_ci_execution(tmp_path)] == ["CERT-CI-008"]


@pytest.mark.parametrize("suffix", ["env:\n  SHELLOPTS: noexec\n", "jobs: {}\n", "---\n{}"])
def test_trailing_yaml_overrides_are_rejected(tmp_path: Path, suffix: str) -> None:
    _write(tmp_path, _workflow() + suffix)
    assert audit_ci_execution(tmp_path)


@pytest.mark.parametrize("shell", ["bash", _LEGACY_SHELL, _SHELL.replace("/bin/bash", "bash")])
def test_unreviewed_shell_launch_is_rejected(tmp_path: Path, shell: str) -> None:
    _write(tmp_path, _workflow().replace(_SHELL, shell, 1))
    assert audit_ci_execution(tmp_path)


def test_missing_or_symlinked_workflow_fails_closed(tmp_path: Path) -> None:
    assert audit_ci_execution(tmp_path)
    path = tmp_path / ".github/workflows/ci.yml"
    path.parent.mkdir(parents=True)
    target = tmp_path / "outside.yml"
    target.write_text(_workflow(), encoding="utf-8")
    path.symlink_to(target)
    assert audit_ci_execution(tmp_path)


@pytest.mark.parametrize(
    "environment,body",
    [
        ({"SHELLOPTS": "noexec"}, "printf 'body\\n'\ntest failure = success\n"),
        ({"SHELLOPTS": "onecmd"}, "printf 'body\\n'\ntest failure = success\n"),
        ({"BASHOPTS": "nullglob"}, "shopt -q nullglob\n"),
        ({"BASH_FUNC_test%%": "() { return 0; }"}, "test failure = success\n"),
        ({"BASH_FUNC_false%%": "() { return 0; }"}, "false\n"),
    ],
)
def test_declared_shell_ignores_inherited_options_and_functions(
    tmp_path: Path, environment: dict[str, str], body: str
) -> None:
    script = tmp_path / "failing-step.sh"
    script.write_text(body, encoding="utf-8")
    legacy = _run(script, _LEGACY_SHELL, environment)
    assert legacy.returncode == 0, legacy.stderr
    for shell in set(_declared_shells()):
        result = _run(script, shell, environment)
        assert result.returncode == 1, result.stderr


@pytest.mark.parametrize("exit_code", [0, 7])
def test_declared_shell_ignores_startup_hook_and_preserves_body_status(
    tmp_path: Path, exit_code: int
) -> None:
    hook = tmp_path / "startup.sh"
    hook.write_text("printf 'hook\\n'\nexit 0\n", encoding="utf-8")
    script = tmp_path / "body.sh"
    script.write_text(f"printf 'body\\n'\nexit {exit_code}\n", encoding="utf-8")
    environment = {"BASH_ENV": str(hook), "SHELLOPTS": "noexec"}
    for shell in set(_declared_shells()):
        result = _run(script, shell, environment)
        assert (result.returncode, result.stdout) == (exit_code, "body\n")


@pytest.mark.parametrize("body", ["false\n", "false | cat\n"])
def test_declared_shell_retains_errexit_and_pipefail(tmp_path: Path, body: str) -> None:
    script = tmp_path / "fail-fast.sh"
    script.write_text(body + "printf 'must-not-execute\\n'\n", encoding="utf-8")
    for shell in set(_declared_shells()):
        result = _run(script, shell, {})
        assert (result.returncode, result.stdout) == (1, "")


def test_declared_shell_executable_cannot_be_shadowed_via_path(tmp_path: Path) -> None:
    binary = tmp_path / "bin"
    binary.mkdir()
    fake_bash = binary / "bash"
    fake_bash.write_text("#!/bin/sh\nprintf 'wrong-shell\\n'\nexit 0\n", encoding="utf-8")
    fake_bash.chmod(0o755)
    script = tmp_path / "fail.sh"
    script.write_text("test failure = success\n", encoding="utf-8")
    for shell in set(_declared_shells()):
        result = _run(script, shell, {"PATH": str(binary) + os.pathsep + os.defpath})
        assert (result.returncode, result.stdout) == (1, "")
