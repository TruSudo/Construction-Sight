from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
import subprocess
import sys
import tomllib
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

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


_DEFERRED_TERMS = (
    "TO" + "DO",
    "FIX" + "ME",
    "HA" + "CK",
    "X" * 3,
)
_SUPPRESSION_RULES = (
    ("lint suppression", re.compile(_joined(r"#\s*no", r"qa\b"), re.IGNORECASE)),
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
        re.compile(r"\b(?:" + "|".join(_DEFERRED_TERMS) + r")\b"),
    ),
)
_SECRET_RULES = (
    ("private key material", re.compile(_joined("BEGIN ", "(?:RSA |EC |OPENSSH )?PRIVATE KEY"))),
    ("GitHub token", re.compile(_joined(r"\bgh", r"[opsu]_[A-Za-z0-9]{20,}\b"))),
    (
        "GitHub fine-grained token",
        re.compile(_joined(r"\bgithub_pat_", r"[A-Za-z0-9_]{20,}\b")),
    ),
    ("AWS access key", re.compile(_joined(r"\bAKIA", r"[A-Z0-9]{16}\b"))),
    ("OpenAI-style secret", re.compile(_joined(r"\bsk-", r"[A-Za-z0-9_-]{20,}\b"))),
)
_REQUIRED_CI_SNIPPETS = (
    "git ls-files --stage",
    "python -m pip check",
    "python -m ruff check src tests",
    "python -m mypy src",
    "python -m compileall -q src tests",
    "python -m pytest --strict-config --strict-markers -ra",
    "constructionsight audit-adapters",
    "constructionsight audit-source-coverage data/source_registry.seed.json",
    "python -m constructionsight.repository_certification_v2",
    "git diff --check",
)
_CI_BLOCK_MARKERS = {"|", "|-", "|+", ">", ">-", ">+"}


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


def _finding(
    code: str,
    path: str | Path,
    message: str,
    line: int | None = None,
) -> CertificationFinding:
    display_path = path.as_posix() if isinstance(path, Path) else path
    return CertificationFinding(code=code, path=display_path, line=line, message=message)


def _run_git(root: Path, *arguments: str) -> str:
    command = ["git", "-C", str(root), *arguments]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode == 0:
        return completed.stdout
    detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
    raise CertificationError(f"git command failed: {' '.join(command)}: {detail}")


def _tracked_index_entries(root: Path) -> tuple[tuple[Path, str], ...]:
    output = _run_git(root, "ls-files", "--stage", "-z")
    entries: list[tuple[Path, str]] = []
    for raw_entry in output.split("\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise CertificationError("git index entry has an unexpected shape")
        mode, _object_id, stage = fields
        if stage != "0":
            raise CertificationError(f"git index contains unresolved stages: {raw_path}")
        entries.append((Path(raw_path), mode))
    if not entries:
        raise CertificationError("repository has no tracked files")
    return tuple(sorted(entries, key=lambda entry: entry[0].as_posix()))


def _tracked_files(root: Path) -> tuple[Path, ...]:
    return tuple(path for path, _mode in _tracked_index_entries(root))


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_text_path(path: Path) -> bool:
    return path.suffix.lower() in _TEXT_SUFFIXES or path.name in {
        ".gitattributes",
        ".gitignore",
        "LICENSE",
    }


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data:
        raise UnicodeError("contains a NUL byte")
    return data.decode("utf-8")


def _audit_text_hygiene(
    path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    if "\r" in text:
        findings.append(_finding("CERT-TEXT-001", path, "tracked text must use LF endings"))
    if text and not text.endswith("\n"):
        findings.append(_finding("CERT-TEXT-002", path, "tracked text must end with a newline"))
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.rstrip(" \t") != line:
            findings.append(
                _finding(
                    "CERT-TEXT-003",
                    path,
                    "trailing whitespace is not permitted",
                    line_number,
                )
            )


def _audit_suppressions(
    path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    if path.suffix.lower() not in _CODE_SUFFIXES:
        return
    for label, pattern in _SUPPRESSION_RULES:
        for match in pattern.finditer(text):
            findings.append(
                _finding(
                    "CERT-SUPPRESS-001",
                    path,
                    f"{label} is prohibited by certification doctrine",
                    _line_number(text, match.start()),
                )
            )


def _audit_secrets(
    path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    for label, pattern in _SECRET_RULES:
        for match in pattern.finditer(text):
            findings.append(
                _finding(
                    "CERT-SECRET-001",
                    path,
                    f"possible {label} is tracked in the repository",
                    _line_number(text, match.start()),
                )
            )


def _is_abstract(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        (isinstance(decorator, ast.Name) and decorator.id == "abstractmethod")
        or (isinstance(decorator, ast.Attribute) and decorator.attr == "abstractmethod")
        for decorator in node.decorator_list
    )


def _audit_python(
    path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    if path.suffix.lower() != ".py":
        return
    try:
        tree = ast.parse(text, filename=path.as_posix())
    except SyntaxError as exc:
        findings.append(
            _finding("CERT-PY-001", path, f"Python syntax error: {exc.msg}", exc.lineno)
        )
        return
    if not path.as_posix().startswith("src/"):
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or _is_abstract(node):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Raise):
                continue
            exception = child.exc
            named_placeholder = (
                isinstance(exception, ast.Name) and exception.id == "NotImplementedError"
            )
            called_placeholder = (
                isinstance(exception, ast.Call)
                and isinstance(exception.func, ast.Name)
                and exception.func.id == "NotImplementedError"
            )
            if named_placeholder or called_placeholder:
                findings.append(
                    _finding(
                        "CERT-PY-002",
                        path,
                        "non-abstract production code raises NotImplementedError",
                        child.lineno,
                    )
                )


def _audit_structured_file(
    path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    try:
        if path.suffix.lower() == ".json":
            json.loads(text)
        elif path.suffix.lower() == ".toml":
            tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        findings.append(
            _finding(
                "CERT-STRUCT-001",
                path,
                f"malformed structured file: {exc}",
                getattr(exc, "lineno", None),
            )
        )


def _link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if " " in target:
        target = target.split(" ", maxsplit=1)[0]
    return target.split("#", maxsplit=1)[0]


def _audit_markdown_links(
    root: Path,
    path: Path,
    text: str,
    findings: list[CertificationFinding],
) -> None:
    if path.suffix.lower() != ".md":
        return
    for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = _link_target(match.group(1))
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        relative_target = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath((path.parent / target).as_posix())
        )
        try:
            resolve_repository_file(root, relative_target)
        except RepositoryPathError:
            findings.append(
                _finding(
                    "CERT-DOC-001",
                    path,
                    f"local Markdown link target is missing or unsafe: {target}",
                    _line_number(text, match.start()),
                )
            )


def _defined_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _audit_pyproject(
    root: Path,
    tracked: set[Path],
    findings: list[CertificationFinding],
) -> None:
    path = Path("pyproject.toml")
    try:
        _relative, absolute_path = resolve_repository_file(root, path.as_posix())
    except RepositoryPathError:
        findings.append(_finding("CERT-CONFIG-001", path, "pyproject.toml is required"))
        return
    payload = tomllib.loads(absolute_path.read_text(encoding="utf-8"))
    ruff_lint = payload.get("tool", {}).get("ruff", {}).get("lint", {})
    if ruff_lint.get("ignore") != []:
        findings.append(
            _finding("CERT-CONFIG-002", path, "Ruff ignore must be an explicit empty list")
        )
    if ruff_lint.get("per-file-ignores"):
        findings.append(_finding("CERT-CONFIG-003", path, "Ruff per-file ignores are prohibited"))

    mypy = payload.get("tool", {}).get("mypy", {})
    for key in ("strict", "warn_return_any", "warn_unreachable", "warn_unused_ignores"):
        if mypy.get(key) is not True:
            findings.append(_finding("CERT-CONFIG-004", path, f"mypy {key} must be true"))
    for key in ("allow_untyped_defs", "ignore_errors", "ignore_missing_imports"):
        if mypy.get(key) is True:
            findings.append(_finding("CERT-CONFIG-005", path, f"mypy {key}=true is prohibited"))

    scripts = payload.get("project", {}).get("scripts", {})
    for name, raw_target in scripts.items():
        module_name, separator, attribute_name = str(raw_target).partition(":")
        if not separator or not module_name.startswith("constructionsight.") or not attribute_name:
            findings.append(
                _finding("CERT-SCRIPT-001", path, f"invalid script target for {name}: {raw_target}")
            )
            continue
        module_path = Path("src", *module_name.split(".")).with_suffix(".py")
        if module_path not in tracked:
            findings.append(
                _finding("CERT-SCRIPT-002", path, f"script module is not tracked: {module_path}")
            )
            continue
        try:
            _relative, source_path = resolve_repository_file(
                root,
                module_path.as_posix(),
                required_prefix="src/constructionsight",
                required_suffix=".py",
            )
        except RepositoryPathError:
            findings.append(
                _finding(
                    "CERT-SCRIPT-002",
                    path,
                    f"script module is not safely resolvable: {module_path}",
                )
            )
            continue
        source = source_path.read_text(encoding="utf-8")
        if attribute_name not in _defined_module_names(ast.parse(source)):
            findings.append(
                _finding(
                    "CERT-SCRIPT-003",
                    module_path,
                    f"script attribute is missing for {name}: {attribute_name}",
                )
            )


def _executable_ci_lines(workflow: str) -> tuple[str, ...]:
    lines = workflow.splitlines()
    executable: list[str] = []
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.lstrip()
        match = re.fullmatch(r"(?:-\s+)?run:\s*(.*)", stripped)
        if match is None:
            index += 1
            continue
        value = match.group(1).strip()
        indent = len(raw_line) - len(stripped)
        if value in _CI_BLOCK_MARKERS:
            index += 1
            while index < len(lines):
                candidate = lines[index]
                candidate_text = candidate.strip()
                if not candidate_text:
                    index += 1
                    continue
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if candidate_indent <= indent:
                    break
                if not candidate_text.startswith("#"):
                    executable.append(candidate_text)
                index += 1
            continue
        if value and not value.startswith("#"):
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1].strip()
            executable.append(value)
        index += 1
    return tuple(executable)


def _audit_ci(root: Path, findings: list[CertificationFinding]) -> None:
    path = Path(".github/workflows/ci.yml")
    try:
        _relative, absolute_path = resolve_repository_file(root, path.as_posix())
    except RepositoryPathError:
        findings.append(_finding("CERT-CI-001", path, "canonical CI workflow is required"))
        return
    workflow = absolute_path.read_text(encoding="utf-8")
    executable_lines = _executable_ci_lines(workflow)
    for snippet in _REQUIRED_CI_SNIPPETS:
        if not any(line.startswith(snippet) for line in executable_lines):
            findings.append(
                _finding(
                    "CERT-CI-002",
                    path,
                    f"required CI gate is missing: {snippet}",
                )
            )
    if "permissions:\n  contents: read" not in workflow:
        findings.append(_finding("CERT-CI-003", path, "CI permissions must remain read-only"))
    for version in ('"3.11"', '"3.12"'):
        if version not in workflow:
            findings.append(_finding("CERT-CI-004", path, f"CI matrix is missing {version}"))


def audit_repository(root: Path, *, require_clean_worktree: bool = False) -> CertificationReport:
    repository_root = root.resolve()
    tracked_entries = _tracked_index_entries(repository_root)
    tracked_files = tuple(path for path, _mode in tracked_entries)
    mode_by_path = dict(tracked_entries)
    tracked = set(tracked_files)
    findings: list[CertificationFinding] = []
    normalized_paths: dict[str, Path] = {}
    source_python_count = 0
    test_python_count = 0

    for path in tracked_files:
        display_path = path.as_posix()
        normalized_key = unicodedata.normalize("NFC", display_path).casefold()
        prior = normalized_paths.get(normalized_key)
        if prior is not None and prior != path:
            findings.append(
                _finding("CERT-PATH-001", path, f"case/Unicode path collision with {prior}")
            )
        normalized_paths[normalized_key] = path

        if any(part in _FORBIDDEN_PATH_PARTS for part in path.parts):
            findings.append(_finding("CERT-PATH-002", path, "transient directory is tracked"))
        if (
            path.name in _FORBIDDEN_FILE_NAMES
            or path.suffix.lower() in _FORBIDDEN_SUFFIXES
            or path.name.endswith("~")
        ):
            findings.append(_finding("CERT-PATH-003", path, "transient or backup file is tracked"))

        mode = mode_by_path[path]
        if mode == "120000":
            findings.append(
                _finding(
                    "CERT-PATH-005",
                    path,
                    "tracked symbolic links are prohibited",
                )
            )
            continue
        try:
            _relative, absolute_path = resolve_repository_file(
                repository_root,
                display_path,
            )
        except RepositoryPathError as exc:
            findings.append(
                _finding(
                    "CERT-PATH-006",
                    path,
                    f"tracked path is missing or unsafe: {exc}",
                )
            )
            continue
        if absolute_path.stat().st_size > _MAX_TRACKED_FILE_BYTES:
            findings.append(_finding("CERT-PATH-004", path, "tracked file exceeds 5 MiB"))
        if path.suffix.lower() == ".py":
            source_python_count += int(display_path.startswith("src/"))
            test_python_count += int(display_path.startswith("tests/"))
        if not _is_text_path(path):
            continue
        try:
            text = _read_text(absolute_path)
        except (OSError, UnicodeError) as exc:
            findings.append(_finding("CERT-TEXT-004", path, f"invalid tracked text: {exc}"))
            continue
        _audit_text_hygiene(path, text, findings)
        _audit_suppressions(path, text, findings)
        _audit_secrets(path, text, findings)
        _audit_python(path, text, findings)
        _audit_structured_file(path, text, findings)
        _audit_markdown_links(repository_root, path, text, findings)

    _audit_pyproject(repository_root, tracked, findings)
    _audit_ci(repository_root, findings)
    if source_python_count == 0:
        findings.append(_finding("CERT-INVENTORY-001", "src", "no production modules found"))
    if test_python_count == 0:
        findings.append(_finding("CERT-INVENTORY-002", "tests", "no Python tests found"))
    if require_clean_worktree:
        status = _run_git(repository_root, "status", "--porcelain=v1", "--untracked-files=all")
        if status.strip():
            findings.append(
                _finding(
                    "CERT-GIT-001",
                    ".",
                    f"worktree is not clean:\n{status.rstrip()}",
                )
            )

    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda item: (item.code, item.path, item.line or 0, item.message),
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit the complete tracked repository tree.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--require-clean-worktree", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
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
