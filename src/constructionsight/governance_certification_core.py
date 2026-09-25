"""Shared fail-closed semantic governance certification primitives."""

from __future__ import annotations

import ast
import re
import subprocess
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

SCHEMA_VERSION: Final = "constructionsight.governance-certification/v1"
_ARCHITECTURE_SCHEMA: Final = "constructionsight.architecture-contract/v1"
_CAPABILITY_SCHEMA: Final = "constructionsight.capability-contract/v1"
_DEPENDENCY_SCHEMA: Final = "constructionsight.dependency-contract/v1"
_NETWORK_SCHEMA: Final = "constructionsight.network-contract/v1"
_AUTHORIZATION_SCHEMA: Final = "constructionsight.authorization-contract/v1"
_TEST_SCHEMA: Final = "constructionsight.adversarial-test-contract/v1"
_ACTIVE_DEFECT_SCHEMA: Final = "constructionsight.active-defects/v1"
_RESOLVED_DEFECT_SCHEMA: Final = "constructionsight.resolved-defects/v1"
_ASSURANCE_CONTRACT_SCHEMA: Final = "constructionsight.assurance-contract/v1"
_ASSURANCE_REVIEW_SCHEMA: Final = "constructionsight.assurance-review/v1"

_NETWORK_IMPORTS: Final = {
    "aiohttp",
    "http.client",
    "httpx",
    "requests",
    "socket",
    "urllib.request",
}
_PERSISTENCE_IMPORTS: Final = {"sqlalchemy"}
_SUBPROCESS_IMPORTS: Final = {"subprocess"}
_FILESYSTEM_MUTATION_CALLS: Final = {
    "mkdir",
    "rename",
    "replace",
    "rmdir",
    "unlink",
    "write_bytes",
    "write_text",
}
_FILESYSTEM_RECEIVER_HINTS: Final = {
    "artifact",
    "checkpoint",
    "destination",
    "directory",
    "dir",
    "file",
    "folder",
    "output",
    "path",
    "root",
    "target",
    "temp",
    "tmp",
}
_PATH_CONSTRUCTORS: Final = {"Path", "PurePath", "PurePosixPath", "PureWindowsPath"}
_DATABASE_MUTATION_CALLS: Final = {"add", "commit", "delete", "execute", "flush", "merge"}
_DATABASE_RECEIVER_HINTS: Final = {"connection", "conn", "db", "repository", "session", "store"}


@dataclass(frozen=True)
class GovernanceFinding:
    code: str
    path: str
    line: int | None
    message: str


@dataclass(frozen=True)
class GovernanceMetrics:
    architecture_nodes: int = 0
    architecture_edges: int = 0
    architecture_cycles: int = 0
    capability_count: int = 0
    dependency_count: int = 0
    network_policy_count: int = 0
    authorization_operation_count: int = 0


@dataclass(frozen=True)
class GovernanceReport:
    schema_version: str
    finding_count: int
    findings: tuple[GovernanceFinding, ...]
    metrics: GovernanceMetrics

    @property
    def passed(self) -> bool:
        return self.finding_count == 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload


class GovernanceContractError(RuntimeError):
    """Raised when governance cannot be evaluated at all."""


def _finding(
    code: str,
    path: str | Path,
    message: str,
    line: int | None = None,
) -> GovernanceFinding:
    return GovernanceFinding(code, Path(path).as_posix(), line, message)


def _read_toml(
    root: Path,
    relative: str,
    schema: str,
    findings: list[GovernanceFinding],
) -> dict[str, Any]:
    try:
        _canonical, path = resolve_repository_file(root, relative)
    except RepositoryPathError:
        findings.append(
            _finding(
                "GOV-CONTRACT-001",
                relative,
                "required governance contract is missing or unsafe",
            )
        )
        return {}
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        findings.append(
            _finding("GOV-CONTRACT-002", relative, f"governance contract is malformed: {exc}")
        )
        return {}
    if payload.get("schema_version") != schema:
        findings.append(
            _finding(
                "GOV-CONTRACT-003",
                relative,
                f"unsupported schema_version; expected {schema!r}",
            )
        )
    return payload


def _compile_patterns(
    raw: object,
    *,
    path: str,
    field: str,
    findings: list[GovernanceFinding],
) -> tuple[re.Pattern[str], ...]:
    if not isinstance(raw, list) or not raw or not all(isinstance(value, str) for value in raw):
        findings.append(
            _finding("GOV-CONTRACT-004", path, f"{field} must be a nonempty string array")
        )
        return ()
    compiled: list[re.Pattern[str]] = []
    for value in raw:
        try:
            compiled.append(re.compile(value))
        except re.error as exc:
            findings.append(
                _finding("GOV-CONTRACT-005", path, f"invalid {field} regex {value!r}: {exc}")
            )
    return tuple(compiled)


def _module_name(path: Path) -> str:
    relative = path.relative_to("src").with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_import(current: str, node: ast.ImportFrom, known: set[str]) -> str | None:
    module = node.module or ""
    if node.level:
        package = current.split(".")[:-1]
        trim = max(node.level - 1, 0)
        if trim > len(package):
            return None
        base = package[: len(package) - trim]
        if module:
            base.extend(module.split("."))
        candidate = ".".join(base)
    else:
        candidate = module
    if not candidate.startswith("constructionsight"):
        return None
    while candidate and candidate not in known:
        candidate = candidate.rpartition(".")[0]
    return candidate or None


def _imports(tree: ast.Module, current: str, known: set[str]) -> tuple[set[str], set[str]]:
    internal: set[str] = set()
    external: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith("constructionsight"):
                    candidate = name
                    while candidate and candidate not in known:
                        candidate = candidate.rpartition(".")[0]
                    if candidate:
                        internal.add(candidate)
                else:
                    external.add(name)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import(current, node, known)
            if resolved is not None:
                internal.add(resolved)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    member = f"{resolved}.{alias.name}"
                    if member in known:
                        internal.add(member)
            else:
                base = node.module or ""
                if base:
                    external.add(base)
                    for alias in node.names:
                        if alias.name != "*":
                            external.add(f"{base}.{alias.name}")
    return internal, external


def _external_matches(imports: Iterable[str], candidates: set[str]) -> bool:
    for imported in imports:
        for candidate in candidates:
            if imported == candidate or imported.startswith(candidate + "."):
                return True
    return False


def _expression_names(node: ast.AST) -> tuple[str, ...]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return tuple(sorted(names))


def _looks_like_filesystem_receiver(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        function = node.func
        if isinstance(function, ast.Name) and function.id in _PATH_CONSTRUCTORS:
            return True
        if isinstance(function, ast.Attribute) and function.attr in {
            "absolute",
            "expanduser",
            "resolve",
            "with_name",
            "with_suffix",
        }:
            return _looks_like_filesystem_receiver(function.value)
    return any(
        hint in name.casefold()
        for name in _expression_names(node)
        for hint in _FILESYSTEM_RECEIVER_HINTS
    )


def _mutation_lines(tree: ast.Module) -> tuple[int, ...]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name: str | None = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if (
            name in _FILESYSTEM_MUTATION_CALLS
            and isinstance(node.func, ast.Attribute)
            and _looks_like_filesystem_receiver(node.func.value)
        ):
            lines.add(node.lineno)
        if name in _DATABASE_MUTATION_CALLS and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            receiver_name: str | None = None
            if isinstance(receiver, ast.Name):
                receiver_name = receiver.id
            elif isinstance(receiver, ast.Attribute):
                receiver_name = receiver.attr
            if receiver_name is not None and any(
                hint in receiver_name.casefold() for hint in _DATABASE_RECEIVER_HINTS
            ):
                lines.add(node.lineno)
        if name == "open" and len(node.args) >= 2:
            mode = node.args[1]
            if (
                isinstance(mode, ast.Constant)
                and isinstance(mode.value, str)
                and any(flag in mode.value for flag in "wax+")
            ):
                lines.add(node.lineno)
    return tuple(sorted(lines))


def _strongly_connected_components(
    graph: Mapping[str, set[str]],
) -> tuple[tuple[str, ...], ...]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(graph.get(node, set())):
            if target not in indices:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], indices[target])
        if low[node] != indices[node]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        components.append(tuple(sorted(component)))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return tuple(sorted(components))


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise GovernanceContractError(detail)
    return completed.stdout.strip()
