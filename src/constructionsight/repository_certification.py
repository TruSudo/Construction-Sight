from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

SCHEMA_VERSION = "constructionsight.repository_certification.v1"

_TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_CODE_SUFFIXES = {".cfg", ".ini", ".py", ".sh", ".toml", ".yaml", ".yml"}
_FORBIDDEN_PATH_PARTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "htmlcov",
}
_FORBIDDEN_FILE_NAMES = {
    ".coverage",
    ".DS_Store",
    "coverage.xml",
    "pytest-results.xml",
    "ruff-results.json",
}
_FORBIDDEN_SUFFIXES = {".bak", ".orig", ".pyc", ".pyo", ".swp", ".tmp"}
_MAX_TRACKED_FILE_BYTES = 5 * 1024 * 1024


def _joined(*parts: str) -> str:
    return "".join(parts)


_SUPPRESSION_RULES = (
    (
        "lint suppression",
        re.compile(_joined(r"#\s*no", r"qa\b"), re.IGNORECASE),
    ),
    (
        "type-check suppression",
        re.compile(_joined(r"type\s*:\s*", r"ignore\b"), re.IGNORECASE),
    ),
    (
        "coverage suppression",
        re.compile(_joined(r"pragma\s*:\s*no\s*", r"cover\b"), re.IGNORECASE),
    ),
    (
        "pytest skip marker",
        re.compile(_joined(r"pytest\.mark\.", r"(?:skip|skipif|xfail)\b")),
    ),
    (
        "pytest runtime skip",
        re.compile(_joined(r"pytest\.", r"(?:skip|xfail)\s*\(")),
    ),
    (
        "unittest skip",
        re.compile(_joined(r"unittest\.", r"skip(?:If|Unless)?\s*\(")),
    ),
    (
        "deferred-work marker",
        re.compile(_joined(r"\b(?:TO", r"DO|FIX", r"ME|HACK|XXX)\b")),
    ),
)

_SECRET_RULES = (
    ("private key material", re.compile(_joined("BEGIN ", "(?:RSA |EC |OPENSSH )?PRIVATE KEY"))),
    ("GitHub token", re.compile(_joined(r"\bgh", r"[opsu]_[A-Za-z0-9]{20,}\b"))),
    ("GitHub fine-grained token", re.compile(_joined(r"\bgithub_pat_", r"[A-Za-z0-9_]{20,}\b"))),
    ("AWS access key", re.compile(_joined(r"\bAKIA", r"[A-Z0-9]{16}\b"))),
    ("OpenAI-style secret", re.compile(_joined(r"\bsk-", r"[A-Za-z0-9_-]{20,}\b"))),
)

_REQUIRED_CI_SNIPPETS = (
    "python -m ruff check src tests",
    "python -m mypy src",
    "python -m compileall -q src tests",
    "python -m pytest --strict-config --strict-markers -ra",
    "python -m pip check",
    "git diff --check",
    "python -m constructionsight.repository_certification --root . --require-clean-worktree",
    "constructionsight audit-adapters",
    "constructionsight audit-source-coverage data/source_registry.seed.json",
)


@dataclass(frozen=True)
class CertificationFinding:
    code: str
    path: str
    line: int | None
    message: str


@dataclass(frozen=True)
class CertificationReport:
    schema_version: str
    tracked_file_count: int
    source_python_count: int
    test_python_count: int
    finding_count: int
    findings: tuple[CertificationFinding, ...]

    @property
    def passed(self) -> bool:
        return self.finding_count == 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload


class CertificationError(RuntimeError):
    pass


def _run_git(root: Path, *arguments: str) -> str:
    command = ["git", "-C", str(root), *arguments]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise CertificationError(f"git command failed: {' '.join(command)}: {detail}")
    return completed.stdout


def _tracked_files(root: Path) -> tuple[Path, ...]:
    output = _run_git(root, "ls-files", "-z")
    paths = tuple(Path(value) for value in output.split("\0") if value)
    if not paths:
        raise CertificationError("repository has no tracked files")
    return tuple(sorted(paths, key=lambda value: value.as_posix()))


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_text_path(path: Path) -> bool:
    return path.suffix.lower() in _TEXT_SUFFIXES or path.name in {
        ".gitignore",
        ".gitattributes",
        "LICENSE",
    }


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data:
        raise UnicodeError("contains a NUL byte")
    return data.decode("utf-8")


def _add_text_hygiene_findings(
    relative_path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    display_path = relative_path.as_posix()
    if "\r\n" in text or "\r" in text:
        findings.append(
            CertificationFinding(
                code="CERT-TEXT-001",
                path=display_path,
                line=None,
                message="tracked text must use LF line endings",
            )
        )
    if text and not text.endswith("\n"):
        findings.append(
            CertificationFinding(
                code="CERT-TEXT-002",
                path=display_path,
                line=None,
                message="tracked text must end with a newline",
            )
        )
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.rstrip(" \t") != line:
            findings.append(
                CertificationFinding(
                    code="CERT-TEXT-003",
                    path=display_path,
                    line=line_number,
                    message="trailing whitespace is not permitted",
                )
            )


def _add_suppression_findings(
    relative_path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    if relative_path.suffix.lower() not in _CODE_SUFFIXES:
        return
    display_path = relative_path.as_posix()
    for label, pattern in _SUPPRESSION_RULES:
        for match in pattern.finditer(text):
            findings.append(
                CertificationFinding(
                    code="CERT-SUPPRESS-001",
                    path=display_path,
                    line=_line_number(text, match.start()),
                    message=f"{label} is prohibited by certification doctrine",
                )
            )


def _add_secret_findings(
    relative_path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    display_path = relative_path.as_posix()
    for label, pattern in _SECRET_RULES:
        for match in pattern.finditer(text):
            findings.append(
                CertificationFinding(
                    code="CERT-SECRET-001",
                    path=display_path,
                    line=_line_number(text, match.start()),
                    message=f"possible {label} is tracked in the repository",
                )
            )


def _function_is_abstract(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "abstractmethod":
            return True
    return False


def _add_python_findings(
    relative_path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    if relative_path.suffix.lower() != ".py":
        return
    display_path = relative_path.as_posix()
    try:
        tree = ast.parse(text, filename=display_path)
    except SyntaxError as exc:
        findings.append(
            CertificationFinding(
                code="CERT-PY-001",
                path=display_path,
                line=exc.lineno,
                message=f"Python syntax error: {exc.msg}",
            )
        )
        return
    if not display_path.startswith("src/"):
        return
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_abstract(node):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Raise):
                continue
            exception = child.exc
            if isinstance(exception, ast.Name) and exception.id == "NotImplementedError":
                findings.append(
                    CertificationFinding(
                        code="CERT-PY-002",
                        path=display_path,
                        line=child.lineno,
                        message="non-abstract production code raises NotImplementedError",
                    )
                )
            if (
                isinstance(exception, ast.Call)
                and isinstance(exception.func, ast.Name)
                and exception.func.id == "NotImplementedError"
            ):
                findings.append(
                    CertificationFinding(
                        code="CERT-PY-002",
                        path=display_path,
                        line=child.lineno,
                        message="non-abstract production code raises NotImplementedError",
                    )
                )


def _add_structured_file_findings(
    relative_path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    display_path = relative_path.as_posix()
    try:
        if relative_path.suffix.lower() == ".json":
            json.loads(text)
        elif relative_path.suffix.lower() == ".toml":
            tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        findings.append(
            CertificationFinding(
                code="CERT-STRUCT-001",
                path=display_path,
                line=getattr(exc, "lineno", None),
                message=f"malformed structured file: {exc}",
            )
        )


def _normalize_link_target(target: str) -> str:
    stripped = target.strip()
    if stripped.startswith("<") and stripped.endswith(">"):
        stripped = stripped[1:-1]
    if " " in stripped:
        stripped = stripped.split(" ", maxsplit=1)[0]
    return stripped.split("#", maxsplit=1)[0]


def _add_markdown_link_findings(
    root: Path,
    relative_path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    if relative_path.suffix.lower() != ".md":
        return
    display_path = relative_path.as_posix()
    pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for match in pattern.finditer(text):
        target = _normalize_link_target(match.group(1))
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if target.startswith("/"):
            candidate = root / target.lstrip("/")
        else:
            candidate = root / relative_path.parent / target
        if not candidate.exists():
            findings.append(
                CertificationFinding(
                    code="CERT-DOC-001",
                    path=display_path,
                    line=_line_number(text, match.start()),
                    message=f"local Markdown link target does not exist: {target}",
                )
            )


def _add_pyproject_policy_findings(
    root: Path,
    tracked_paths: set[Path],
    findings: list[CertificationFinding],
) -> None:
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        findings.append(
            CertificationFinding(
                code="CERT-CONFIG-001",
                path="pyproject.toml",
                line=None,
                message="pyproject.toml is required",
            )
        )
        return
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    ruff_lint = payload.get("tool", {}).get("ruff", {}).get("lint", {})
    if ruff_lint.get("ignore") != []:
        findings.append(
            CertificationFinding(
                code="CERT-CONFIG-002",
                path="pyproject.toml",
                line=None,
                message="Ruff ignore must remain an explicit empty list",
            )
        )
    if ruff_lint.get("per-file-ignores"):
        findings.append(
            CertificationFinding(
                code="CERT-CONFIG-003",
                path="pyproject.toml",
                line=None,
                message="Ruff per-file ignores are prohibited",
            )
        )
    mypy = payload.get("tool", {}).get("mypy", {})
    required_mypy = {
        "strict": True,
        "warn_return_any": True,
        "warn_unreachable": True,
        "warn_unused_ignores": True,
    }
    for key, expected in required_mypy.items():
        if mypy.get(key) is not expected:
            findings.append(
                CertificationFinding(
                    code="CERT-CONFIG-004",
                    path="pyproject.toml",
                    line=None,
                    message=f"mypy {key} must remain {expected!r}",
                )
            )
    forbidden_mypy = {
        "allow_untyped_defs": True,
        "ignore_errors": True,
        "ignore_missing_imports": True,
    }
    for key, forbidden in forbidden_mypy.items():
        if mypy.get(key) is forbidden:
            findings.append(
                CertificationFinding(
                    code="CERT-CONFIG-005",
                    path="pyproject.toml",
                    line=None,
                    message=f"mypy {key}={forbidden!r} weakens certification",
                )
            )
    scripts = payload.get("project", {}).get("scripts", {})
    for name, target in scripts.items():
        module_name, separator, attribute_name = str(target).partition(":")
        if not separator or not module_name.startswith("constructionsight.") or not attribute_name:
            findings.append(
                CertificationFinding(
                    code="CERT-SCRIPT-001",
                    path="pyproject.toml",
                    line=None,
                    message=f"invalid console script target for {name}: {target}",
                )
            )
            continue
        relative_module = Path("src", *module_name.split(".")).with_suffix(".py")
        if relative_module not in tracked_paths:
            findings.append(
                CertificationFinding(
                    code="CERT-SCRIPT-002",
                    path="pyproject.toml",
                    line=None,
                    message=f"console script module is not tracked for {name}: {relative_module}",
                )
            )
            continue
        source = (root / relative_module).read_text(encoding="utf-8")
        module_tree = ast.parse(source, filename=relative_module.as_posix())
        defined_names = {
            node.name
            for node in module_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        defined_names.update(
            target_node.id
            for node in module_tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target_node in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target_node, ast.Name)
        )
        if attribute_name not in defined_names:
            findings.append(
                CertificationFinding(
                    code="CERT-SCRIPT-003",
                    path=relative_module.as_posix(),
                    line=None,
                    message=f"console script attribute is missing for {name}: {attribute_name}",
                )
            )


def _add_ci_policy_findings(root: Path, findings: list[CertificationFinding]) -> None:
    workflow_path = root / ".github" / "workflows" / "ci.yml"
    if not workflow_path.exists():
        findings.append(
            CertificationFinding(
                code="CERT-CI-001",
                path=".github/workflows/ci.yml",
                line=None,
                message="canonical CI workflow is required",
            )
        )
        return
    workflow = workflow_path.read_text(encoding="utf-8")
    for snippet in _REQUIRED_CI_SNIPPETS:
        if snippet not in workflow:
            findings.append(
                CertificationFinding(
                    code="CERT-CI-002",
                    path=".github/workflows/ci.yml",
                    line=None,
                    message=f"required CI gate is missing: {snippet}",
                )
            )
    if "permissions:\n  contents: read" not in workflow:
        findings.append(
            CertificationFinding(
                code="CERT-CI-003",
                path=".github/workflows/ci.yml",
                line=None,
                message="CI permissions must remain read-only",
            )
        )
    for version in ('"3.11"', '"3.12"'):
        if version not in workflow:
            findings.append(
                CertificationFinding(
                    code="CERT-CI-004",
                    path=".github/workflows/ci.yml",
                    line=None,
                    message=f"CI matrix is missing Python {version.strip(chr(34))}",
                )
            )


def audit_repository(root: Path, *, require_clean_worktree: bool = False) -> CertificationReport:
    resolved_root = root.resolve()
    findings: list[CertificationFinding] = []
    tracked_files = _tracked_files(resolved_root)
    tracked_paths = set(tracked_files)

    normalized_paths: dict[str, Path] = {}
    source_python_count = 0
    test_python_count = 0

    for relative_path in tracked_files:
        display_path = relative_path.as_posix()
        normalized_key = unicodedata.normalize("NFC", display_path).casefold()
        prior_path = normalized_paths.get(normalized_key)
        if prior_path is not None and prior_path != relative_path:
            findings.append(
                CertificationFinding(
                    code="CERT-PATH-001",
                    path=display_path,
                    line=None,
                    message=f"case/Unicode path collision with {prior_path.as_posix()}",
                )
            )
        else:
            normalized_paths[normalized_key] = relative_path

        if any(part in _FORBIDDEN_PATH_PARTS for part in relative_path.parts):
            findings.append(
                CertificationFinding(
                    code="CERT-PATH-002",
                    path=display_path,
                    line=None,
                    message="transient cache or generated directory is tracked",
                )
            )
        if (
            relative_path.name in _FORBIDDEN_FILE_NAMES
            or relative_path.suffix.lower() in _FORBIDDEN_SUFFIXES
            or relative_path.name.endswith("~")
        ):
            findings.append(
                CertificationFinding(
                    code="CERT-PATH-003",
                    path=display_path,
                    line=None,
                    message="transient, diagnostic, or backup file is tracked",
                )
            )
        absolute_path = resolved_root / relative_path
        size = absolute_path.stat().st_size
        if size > _MAX_TRACKED_FILE_BYTES:
            findings.append(
                CertificationFinding(
                    code="CERT-PATH-004",
                    path=display_path,
                    line=None,
                    message=f"tracked file exceeds {_MAX_TRACKED_FILE_BYTES} bytes",
                )
            )
        if relative_path.suffix.lower() == ".py":
            if display_path.startswith("src/"):
                source_python_count += 1
            if display_path.startswith("tests/"):
                test_python_count += 1
        if not _is_text_path(relative_path):
            continue
        try:
            text = _read_text(absolute_path)
        except (OSError, UnicodeError) as exc:
            findings.append(
                CertificationFinding(
                    code="CERT-TEXT-004",
                    path=display_path,
                    line=None,
                    message=f"tracked text is not valid UTF-8 text: {exc}",
                )
            )
            continue
        _add_text_hygiene_findings(relative_path, text, findings)
        _add_suppression_findings(relative_path, text, findings)
        _add_secret_findings(relative_path, text, findings)
        _add_python_findings(relative_path, text, findings)
        _add_structured_file_findings(relative_path, text, findings)
        _add_markdown_link_findings(resolved_root, relative_path, text, findings)

    _add_pyproject_policy_findings(resolved_root, tracked_paths, findings)
    _add_ci_policy_findings(resolved_root, findings)

    if source_python_count == 0:
        findings.append(
            CertificationFinding(
                code="CERT-INVENTORY-001",
                path="src",
                line=None,
                message="no tracked production Python modules were found",
            )
        )
    if test_python_count == 0:
        findings.append(
            CertificationFinding(
                code="CERT-INVENTORY-002",
                path="tests",
                line=None,
                message="no tracked Python tests were found",
            )
        )
    if require_clean_worktree:
        status = _run_git(resolved_root, "status", "--porcelain=v1", "--untracked-files=all")
        if status.strip():
            findings.append(
                CertificationFinding(
                    code="CERT-GIT-001",
                    path=".",
                    line=None,
                    message=f"worktree is not clean:\n{status.rstrip()}",
                )
            )

    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.code,
                finding.path,
                finding.line if finding.line is not None else 0,
                finding.message,
            ),
        )
    )
    return CertificationReport(
        schema_version=SCHEMA_VERSION,
        tracked_file_count=len(tracked_files),
        source_python_count=source_python_count,
        test_python_count=test_python_count,
        finding_count=len(ordered_findings),
        findings=ordered_findings,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit the complete tracked repository tree.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--require-clean-worktree", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        report = audit_repository(
            arguments.root,
            require_clean_worktree=arguments.require_clean_worktree,
        )
    except CertificationError as exc:
        print(f"Certification audit could not run: {exc}", file=sys.stderr)
        return 2

    serialized = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(serialized, encoding="utf-8")
    if arguments.json_output:
        print(serialized, end="")
    elif report.passed:
        print(
            "Repository certification passed: "
            f"{report.tracked_file_count} tracked files, "
            f"{report.source_python_count} source modules, "
            f"{report.test_python_count} test modules, 0 findings."
        )
    else:
        print(f"Repository certification failed with {report.finding_count} finding(s).")
        for finding in report.findings:
            location = finding.path
            if finding.line is not None:
                location = f"{location}:{finding.line}"
            print(f"- {finding.code} {location}: {finding.message}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
