"""AST certification for high-impact CLI authorization delegation."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path

from constructionsight.governance_certification_core import (
    GovernanceFinding,
    _finding,
    _module_name,
)

_HIGH_IMPACT_CONFIRMATIONS = frozenset(
    {
        "authorize_persistence",
        "check_http",
        "execute_live",
        "execute_write",
    }
)
_AUTHORIZED_SERVICE_PREFIXES = (
    "build_authorized_",
    "execute_authorized_",
    "persist_authorized_",
)
_AUTHORIZED_SERVICE_NAMES = frozenset(
    {
        "execute_ceqanet_csv_evidence_request",
    }
)
_DIRECT_EFFECT_CALLS = frozenset(
    {
        "check_source_http_reachability",
        "create_database_engine",
        "execute_arcgis_bounded_probe",
        "execute_bounded_http",
        "execute_ceqanet_csv_live_request",
        "execute_ceqanet_listing_plan",
        "execute_ceqanet_write_plan",
        "store_arcgis_bounded_proof_bundle_chain",
    }
)


def _call_name(node: ast.Call) -> str | None:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _function_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = node.args
    return {
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }


def _approved_service_call(name: str) -> bool:
    return name in _AUTHORIZED_SERVICE_NAMES or name.startswith(
        _AUTHORIZED_SERVICE_PREFIXES
    )


def audit_semantic_authorization(
    root: Path,
    tracked_files: Sequence[Path],
    layer_by_module: Mapping[str, str],
    findings: list[GovernanceFinding],
) -> None:
    """Reject Boolean-only high-impact CLI execution and direct effect calls."""

    repository_root = root.resolve()
    for relative in sorted((Path(path) for path in tracked_files), key=Path.as_posix):
        if (
            not relative.as_posix().startswith("src/constructionsight/")
            or relative.suffix != ".py"
        ):
            continue
        module = _module_name(relative)
        if layer_by_module.get(module) != "cli":
            continue
        absolute = repository_root / relative
        try:
            tree = ast.parse(absolute.read_text(encoding="utf-8"), filename=str(relative))
        except (OSError, UnicodeError, SyntaxError) as exc:
            findings.append(
                _finding(
                    "AUTH-AST-001",
                    relative,
                    f"semantic authorization AST could not be parsed: {exc}",
                )
            )
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            confirmations = _function_parameters(node) & _HIGH_IMPACT_CONFIRMATIONS
            if not confirmations:
                continue
            call_names = {
                name
                for descendant in ast.walk(node)
                if isinstance(descendant, ast.Call)
                and (name := _call_name(descendant)) is not None
            }
            direct_effects = sorted(call_names & _DIRECT_EFFECT_CALLS)
            if direct_effects:
                findings.append(
                    _finding(
                        "AUTH-BYPASS-001",
                        relative,
                        "high-impact CLI directly invokes effect boundary: "
                        f"{direct_effects}",
                        node.lineno,
                    )
                )
            if not any(_approved_service_call(name) for name in call_names):
                findings.append(
                    _finding(
                        "AUTH-BOOLEAN-002",
                        relative,
                        "high-impact CLI confirmation lacks delegation to an "
                        "explicitly authorized application service; "
                        f"parameters={sorted(confirmations)}",
                        node.lineno,
                    )
                )
